import csv
from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponse, HttpResponseNotAllowed
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q, F, Sum, Exists, OuterRef
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import EventoUso, AuditoriaAdmin
from .constants import (
    ANALYTICS_START_DATE_STR,
    ACCIONES_USO_REAL,
    obtener_analytics_start_date,
    obtener_analytics_start_date_str,
)
from .decorators import staff_required
from .services import (
    registrar_auditoria_admin,
    puede_eliminar_usuario,
    obtener_resumen_dependencias_usuario,
    eliminar_usuario_prueba,
    eliminar_orden_sandbox,
    limpiar_ordenes_sandbox,
    limpiar_actividad_usuario,
    limpiar_actividad_prueba,
    obtener_metricas_mantenimiento,
    obtener_dry_run_limpieza_usuarios,
    ejecutar_limpieza_masiva_usuarios_prueba,
)
from .metrics import (
    obtener_metricas_dashboard,
    obtener_metricas_canciones_detalle,
    obtener_metricas_fogatas_detalle,
    obtener_metricas_comerciales,
)
from apps.canciones.models import Cancion
from apps.fogatas.models import Fogata, SesionCompartida
from apps.core.models import PerfilPiloto
from apps.core.planes import obtener_estado_capacidad
from apps.pagos.models import OrdenPago

User = get_user_model()


def sanitizar_celda_csv(valor):
    """
    Protege contra ataques de Inyección de Fórmulas en Hojas de Cálculo (Criterio 21).
    Si un texto comienza con =, +, -, @, se le antepone una comilla simple (').
    """
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto and texto[0] in ('=', '+', '-', '@'):
        return f"'{texto}"
    return texto


@staff_required
def dashboard_view(request):
    """
    Portada simplificada de Fogata Control Center con los indicadores clave
    de adopción, uso real, embudo de activación y actividad reciente (máx 50).
    """
    metricas = obtener_metricas_dashboard()
    metricas_comerciales = obtener_metricas_comerciales()

    # Actividad reciente (máximo 50 eventos ordenados cronológicamente)
    eventos_recientes = (
        EventoUso.objects.select_related('usuario')
        .order_by('-fecha')[:50]
    )

    context = {
        'm': metricas,
        'c': metricas_comerciales,
        'eventos_recientes': eventos_recientes,
        'inicio_analitica': obtener_analytics_start_date_str(),
    }
    return render(request, 'gestion/dashboard.html', context)


@staff_required
def usuarios_lista_view(request):
    """
    Tabla de usuarios con búsqueda, filtros de adopción, métricas financieras y administración segura (Fase 10).
    """
    query = request.GET.get('q', '').strip()
    filtro_estado = request.GET.get('estado', 'todos').strip()
    filtro_tipo = request.GET.get('filtro', 'todos').strip()

    ahora = timezone.now()
    hace_7dias = ahora - timedelta(days=7)
    hace_30dias = ahora - timedelta(days=30)

    # Base con soporte para filtros de prueba y staff
    if filtro_tipo == 'staff':
        usuarios = User.objects.filter(is_staff=True)
    elif filtro_tipo == 'todos_incluyendo_staff':
        usuarios = User.objects.all()
    else:
        usuarios = User.objects.filter(is_staff=False)

    # Base con anotaciones optimizadas para evitar N+1 queries (Criterio 29 y Fase 10)
    usuarios = (
        usuarios
        .select_related('perfil_piloto')
        .annotate(
            num_canciones=Count('canciones', distinct=True),
            num_fogatas=Count('fogatas', distinct=True),
            num_sesiones=Count('fogatas__sesiones_compartidas', distinct=True),
            ultima_actividad=Max('eventos_uso__fecha'),
            pagos_sandbox=Count(
                'ordenes_pago',
                filter=Q(ordenes_pago__ambiente=OrdenPago.AMBIENTE_SANDBOX, ordenes_pago__estado=OrdenPago.ESTADO_PAGADA),
                distinct=True
            ),
            pagos_prod=Count(
                'ordenes_pago',
                filter=Q(ordenes_pago__ambiente=OrdenPago.AMBIENTE_PRODUCTION, ordenes_pago__estado=OrdenPago.ESTADO_PAGADA),
                distinct=True
            ),
            tiene_pagos_reales=Exists(
                OrdenPago.objects.filter(
                    usuario=OuterRef('pk'),
                    ambiente=OrdenPago.AMBIENTE_PRODUCTION,
                    estado=OrdenPago.ESTADO_PAGADA
                )
            )
        )
    )

    if query:
        usuarios = usuarios.filter(
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )

    # Filtro de estado
    if filtro_estado == 'activos':
        usuarios = usuarios.filter(is_active=True)
    elif filtro_estado == 'suspendidos':
        usuarios = usuarios.filter(is_active=False)

    # Filtros de adopción y tipos especiales (Fase 10)
    if filtro_tipo == 'prueba':
        usuarios = usuarios.filter(is_staff=False).exclude(
            ordenes_pago__ambiente=OrdenPago.AMBIENTE_PRODUCTION,
            ordenes_pago__estado=OrdenPago.ESTADO_PAGADA
        )
    elif filtro_tipo == 'con_pagos':
        usuarios = usuarios.filter(
            ordenes_pago__ambiente=OrdenPago.AMBIENTE_PRODUCTION,
            ordenes_pago__estado=OrdenPago.ESTADO_PAGADA
        ).distinct()
    elif filtro_tipo == 'piloto':
        usuarios = usuarios.filter(perfil_piloto__tipo_cuenta='PILOTO')
    elif filtro_tipo == 'reg_7d':
        usuarios = usuarios.filter(date_joined__gte=hace_7dias)
    elif filtro_tipo == 'reg_30d':
        usuarios = usuarios.filter(date_joined__gte=hace_30dias)
    elif filtro_tipo == 'activos_30d':
        usuarios = usuarios.filter(
            eventos_uso__tipo_evento__in=ACCIONES_USO_REAL,
            eventos_uso__fecha__gte=hace_30dias
        ).distinct()
    elif filtro_tipo == 'sin_actividad_30d':
        activos_ids = set(
            EventoUso.objects.filter(
                usuario__is_staff=False,
                tipo_evento__in=ACCIONES_USO_REAL,
                fecha__gte=hace_30dias
            ).values_list('usuario_id', flat=True)
        )
        usuarios = usuarios.exclude(id__in=activos_ids)
    elif filtro_tipo == 'activados':
        # Creó canción y usó modo tocar
        usuarios = usuarios.filter(
            canciones__isnull=False,
            eventos_uso__tipo_evento__in=['tocar_cancion', 'tocar_fogata']
        ).distinct()

    # Ordenar por defecto: Última actividad desc (con nulos al final)
    usuarios = usuarios.order_by(F('ultima_actividad').desc(nulls_last=True), '-date_joined')

    # Paginación (Criterio 30): 25 registros por página
    paginator = Paginator(usuarios, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
        'filtro_estado': filtro_estado,
        'filtro_tipo': filtro_tipo,
        'total_usuarios': paginator.count,
    }
    return render(request, 'gestion/usuarios_lista.html', context)


@staff_required
def usuario_detalle_view(request, pk):
    """
    Ficha de usuario 360°:
    - Información de cuenta
    - Checklist de activación
    - Métricas de repertorio (metadatos sin letras ni acordes)
    - Acciones operativas seguras
    - Historial de actividad y auditorías
    """
    usuario = get_object_or_404(User.objects.select_related('perfil_piloto'), pk=pk)

    # Métricas agregadas
    total_canciones = usuario.canciones.count()
    total_fogatas = usuario.fogatas.count()
    total_sesiones = SesionCompartida.objects.filter(fogata__propietario=usuario).count()

    veces_modo_tocar = EventoUso.objects.filter(
        usuario=usuario,
        tipo_evento__in=['tocar_cancion', 'tocar_fogata']
    ).count()

    ultima_fogata = usuario.fogatas.order_by('-created_at').first()

    # Última actividad registrada
    ultimo_evento_real = EventoUso.objects.filter(
        usuario=usuario,
        tipo_evento__in=ACCIONES_USO_REAL
    ).order_by('-fecha').first()

    ultima_actividad_fecha = ultimo_evento_real.fecha if ultimo_evento_real else None

    # Checklist de activación
    tiene_cancion = total_canciones > 0
    tiene_modo_tocar = veces_modo_tocar > 0
    tiene_fogata = total_fogatas > 0
    tiene_fogata_tocada = EventoUso.objects.filter(usuario=usuario, tipo_evento='tocar_fogata').exists()
    tiene_sesion_compartida = total_sesiones > 0
    es_activado = tiene_cancion and tiene_modo_tocar

    checklist = [
        {'etiqueta': 'Cuenta creada', 'cumplido': True},
        {'etiqueta': 'Primera canción', 'cumplido': tiene_cancion},
        {'etiqueta': 'Primer Modo Tocar', 'cumplido': tiene_modo_tocar},
        {'etiqueta': 'Primera Fogata', 'cumplido': tiene_fogata},
        {'etiqueta': 'Fogata tocada', 'cumplido': tiene_fogata_tocada},
        {'etiqueta': 'Primera sesión compartida', 'cumplido': tiene_sesion_compartida},
    ]

    # Metadatos de canciones (estrictamente sin letra ni acordes)
    canciones_meta = usuario.canciones.only('id', 'titulo', 'artista', 'tonalidad', 'capo', 'created_at').order_by('-created_at')[:20]

    # Eventos recientes del usuario
    eventos_usuario = EventoUso.objects.filter(usuario=usuario).order_by('-fecha')[:20]

    # Auditorías administrativas aplicadas a este usuario
    auditorias = AuditoriaAdmin.objects.filter(usuario_afectado=usuario).select_related('admin').order_by('-fecha')

    # Órdenes de pago del usuario (Fase 9)
    ordenes_usuario = usuario.ordenes_pago.all().order_by('-creada_el')[:10]

    tiene_pagos_reales = usuario.ordenes_pago.filter(
        ambiente=OrdenPago.AMBIENTE_PRODUCTION,
        estado=OrdenPago.ESTADO_PAGADA
    ).exists()

    context = {
        'u': usuario,
        'capacidad': obtener_estado_capacidad(usuario),
        'total_canciones': total_canciones,
        'total_fogatas': total_fogatas,
        'total_sesiones': total_sesiones,
        'veces_modo_tocar': veces_modo_tocar,
        'ultima_fogata': ultima_fogata,
        'ultima_actividad_fecha': ultima_actividad_fecha,
        'checklist': checklist,
        'es_activado': es_activado,
        'canciones_meta': canciones_meta,
        'eventos_usuario': eventos_usuario,
        'auditorias': auditorias,
        'ordenes_usuario': ordenes_usuario,
        'tiene_pagos_reales': tiene_pagos_reales,
        'inicio_analitica': obtener_analytics_start_date_str(),
    }
    return render(request, 'gestion/usuario_detalle.html', context)


@staff_required
@require_POST
def usuario_suspender_view(request, pk):
    """
    Suspende la cuenta del usuario (is_active=False) y registra en auditoría administrativa.
    """
    usuario = get_object_or_404(User, pk=pk)
    next_url = request.POST.get('next') or reverse('gestion:usuario_detalle', kwargs={'pk': usuario.pk})

    if usuario == request.user:
        messages.error(request, "No puedes suspender tu propia cuenta de administrador.")
        return redirect(next_url)

    if not usuario.is_active:
        messages.info(request, "La cuenta ya se encuentra suspendida.")
        return redirect(next_url)

    usuario.is_active = False
    usuario.save(update_fields=['is_active'])

    registrar_auditoria_admin(
        admin=request.user,
        usuario_afectado=usuario,
        accion='suspender_usuario',
        detalles=f"Cuenta suspendida por {request.user.email}"
    )

    messages.warning(request, f"La cuenta de {usuario.email} ha sido suspendida. No podrá acceder a Fogata.")
    return redirect(next_url)


@staff_required
@require_POST
def usuario_reactivar_view(request, pk):
    """
    Reactiva una cuenta previamente suspendida (is_active=True) y registra en auditoría.
    """
    usuario = get_object_or_404(User, pk=pk)
    next_url = request.POST.get('next') or reverse('gestion:usuario_detalle', kwargs={'pk': usuario.pk})

    if usuario.is_active:
        messages.info(request, "La cuenta ya está activa.")
        return redirect(next_url)

    usuario.is_active = True
    usuario.save(update_fields=['is_active'])

    registrar_auditoria_admin(
        admin=request.user,
        usuario_afectado=usuario,
        accion='reactivar_usuario',
        detalles=f"Cuenta reactivada por {request.user.email}"
    )

    messages.success(request, f"La cuenta de {usuario.email} ha sido reactivada exitosamente.")
    return redirect(next_url)


@staff_required
def usuario_eliminar_view(request, pk):
    """
    Vista administrativa para eliminar un usuario de prueba (Fase 10).
    GET: Muestra pantalla de confirmación o bloqueo si posee pagos Production PAGADA.
    POST: Valida confirmación explícita 'ELIMINAR' y ejecuta eliminación segura.
    """
    usuario = get_object_or_404(User, pk=pk)
    puede, motivo = puede_eliminar_usuario(usuario, admin_usuario=request.user)

    if request.method == 'POST':
        if not puede:
            messages.error(request, f"Acción denegada: {motivo}")
            return redirect('gestion:usuario_detalle', pk=usuario.pk)

        confirmacion = request.POST.get('confirmacion', '').strip()
        if confirmacion != 'ELIMINAR':
            messages.error(request, 'Debes escribir exactamente "ELIMINAR" para confirmar la eliminación.')
            resumen = obtener_resumen_dependencias_usuario(usuario)
            return render(request, 'gestion/usuario_eliminar_confirmar.html', {
                'u': usuario,
                'puede': True,
                'resumen': resumen,
            })

        try:
            eliminar_usuario_prueba(usuario, admin_responsable=request.user)
            messages.success(request, f"Usuario {usuario.email} y todos sus datos dependientes fueron eliminados exitosamente.")
            return redirect('gestion:usuarios_lista')
        except Exception as e:
            messages.error(request, str(e))
            return redirect('gestion:usuario_detalle', pk=usuario.pk)

    # GET
    resumen = obtener_resumen_dependencias_usuario(usuario) if puede else None
    return render(request, 'gestion/usuario_eliminar_confirmar.html', {
        'u': usuario,
        'puede': puede,
        'motivo': motivo,
        'resumen': resumen,
    })


@staff_required
@require_POST
def usuario_enviar_reset_view(request, pk):
    """
    Dispara el envío seguro del correo de recuperación de contraseña estándar de Django
    sin exponer ni manipular contraseñas visibles. Registra en auditoría.
    """
    usuario = get_object_or_404(User, pk=pk)
    form = PasswordResetForm({'email': usuario.email})
    if form.is_valid():
        form.save(
            request=request,
            use_https=request.is_secure(),
            email_template_name='core/password_reset_email.html',
            subject_template_name='core/password_reset_subject.txt',
        )

        registrar_auditoria_admin(
            admin=request.user,
            usuario_afectado=usuario,
            accion='enviar_reset_password',
            detalles=f"Enlace de restablecimiento enviado al correo {usuario.email}"
        )
        messages.success(request, f"Correo de recuperación enviado exitosamente a {usuario.email}.")
    else:
        messages.error(request, "No se pudo generar el correo de recuperación.")

    return redirect('gestion:usuario_detalle', pk=usuario.pk)


@staff_required
@require_POST
def usuario_cambiar_plan_view(request, pk):
    """
    Modifica administrativamente el plan de una cuenta de usuario (GRATIS, PRO, PILOTO)
    y registra auditoría administrativa 'cambiar_plan' (Criterios 17 y 18).
    """
    usuario = get_object_or_404(User.objects.select_related('perfil_piloto'), pk=pk)
    nuevo_plan = request.POST.get('nuevo_plan', '').strip().upper()

    planes_validos = ['GRATIS', 'PRO', 'PILOTO']
    if nuevo_plan not in planes_validos:
        messages.error(request, f"Plan '{nuevo_plan}' no es válido. Opciones: {', '.join(planes_validos)}.")
        return redirect('gestion:usuario_detalle', pk=usuario.pk)

    perfil, _ = PerfilPiloto.objects.get_or_create(user=usuario)
    plan_anterior = perfil.tipo_cuenta or 'PILOTO'

    if plan_anterior == nuevo_plan:
        messages.info(request, f"El usuario ya posee el plan {nuevo_plan}.")
        return redirect('gestion:usuario_detalle', pk=usuario.pk)

    perfil.tipo_cuenta = nuevo_plan
    perfil.save(update_fields=['tipo_cuenta'])

    registrar_auditoria_admin(
        admin=request.user,
        usuario_afectado=usuario,
        accion='cambiar_plan',
        detalles=f"Cambio de plan: {plan_anterior} → {nuevo_plan} (por {request.user.email})"
    )

    messages.success(request, f"Plan de {usuario.email} actualizado exitosamente: {plan_anterior} → {nuevo_plan}.")
    return redirect('gestion:usuario_detalle', pk=usuario.pk)


@staff_required
def actividad_lista_view(request):
    """
    Historial cronológico completo de eventos con paginación, filtros avanzados y acciones de limpieza (Fase 10).
    """
    q_usuario = request.GET.get('q', '').strip()
    tipo_filtro = request.GET.get('tipo', '').strip()
    fecha_desde = request.GET.get('desde', '').strip()
    fecha_hasta = request.GET.get('hasta', '').strip()
    filtro_piloto = request.GET.get('piloto', '').strip()
    filtro_staff = request.GET.get('staff', '').strip()

    eventos = EventoUso.objects.select_related('usuario', 'usuario__perfil_piloto').order_by('-fecha')

    usuario_filtrado = None
    usuario_filtrado_puede_limpiar = False

    if q_usuario:
        eventos = eventos.filter(usuario__email__icontains=q_usuario)
        u_match = User.objects.filter(email__iexact=q_usuario).first()
        if not u_match:
            matches = list(User.objects.filter(email__icontains=q_usuario)[:2])
            if len(matches) == 1:
                u_match = matches[0]
        if u_match:
            usuario_filtrado = u_match
            tiene_pagos_prod = OrdenPago.objects.filter(
                usuario=u_match,
                ambiente=OrdenPago.AMBIENTE_PRODUCTION,
                estado=OrdenPago.ESTADO_PAGADA
            ).exists()
            usuario_filtrado_puede_limpiar = not tiene_pagos_prod and not u_match.is_superuser

    if tipo_filtro:
        eventos = eventos.filter(tipo_evento=tipo_filtro)

    if fecha_desde:
        eventos = eventos.filter(fecha__date__gte=fecha_desde)

    if fecha_hasta:
        eventos = eventos.filter(fecha__date__lte=fecha_hasta)

    if filtro_piloto == 'si':
        eventos = eventos.filter(usuario__perfil_piloto__tipo_cuenta='PILOTO')
    elif filtro_piloto == 'no':
        eventos = eventos.exclude(usuario__perfil_piloto__tipo_cuenta='PILOTO')

    if filtro_staff == 'si':
        eventos = eventos.filter(usuario__is_staff=True)
    elif filtro_staff == 'no':
        eventos = eventos.filter(Q(usuario__is_staff=False) | Q(usuario__isnull=True))

    paginator = Paginator(eventos, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'tipo_filtro': tipo_filtro,
        'tipos_evento': EventoUso.TIPOS_EVENTO,
        'total_eventos': paginator.count,
        'q_usuario': q_usuario,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'filtro_piloto': filtro_piloto,
        'filtro_staff': filtro_staff,
        'usuario_filtrado': usuario_filtrado,
        'usuario_filtrado_puede_limpiar': usuario_filtrado_puede_limpiar,
    }
    return render(request, 'gestion/actividad_lista.html', context)


@staff_required
@require_POST
def actividad_limpiar_usuario_view(request, pk):
    """
    Elimina la actividad operativa de un usuario específico sin pagos reales (Fase 10).
    """
    usuario = get_object_or_404(User, pk=pk)
    try:
        cant = limpiar_actividad_usuario(usuario, admin_responsable=request.user)
        messages.success(request, f"Se eliminaron {cant} eventos de actividad de {usuario.email}.")
    except Exception as e:
        messages.error(request, str(e))
    return redirect(f"{reverse('gestion:actividad_lista')}?q={usuario.email}")


@staff_required
def actividad_limpiar_prueba_view(request):
    """
    Limpieza de actividad operativa de cuentas de prueba (Fase 10).
    GET: Muestra resumen de eventos a eliminar vs protegidos.
    POST: Valida confirmación explícita 'ELIMINAR' y ejecuta limpieza.
    """
    # Cuentas protegidas: con pagos Production PAGADA
    usuarios_prod_ids = set(OrdenPago.objects.filter(
        ambiente=OrdenPago.AMBIENTE_PRODUCTION,
        estado=OrdenPago.ESTADO_PAGADA
    ).values_list('usuario_id', flat=True))

    # Eventos eliminables: producto de cuentas sin pagos reales ni auditoría sensible
    qs_eliminables = EventoUso.objects.exclude(
        usuario_id__in=usuarios_prod_ids
    ).exclude(
        tipo_evento__in=['pago_produccion', 'activacion_pro', 'orden_produccion_pagada']
    )
    eventos_eliminables = qs_eliminables.count()

    qs_protegidos = EventoUso.objects.filter(
        Q(usuario_id__in=usuarios_prod_ids) |
        Q(tipo_evento__in=['pago_produccion', 'activacion_pro', 'orden_produccion_pagada'])
    )
    eventos_protegidos = qs_protegidos.count()

    if request.method == 'POST':
        confirmacion = request.POST.get('confirmacion', '').strip()
        if confirmacion != 'ELIMINAR':
            messages.error(request, 'Debes escribir exactamente "ELIMINAR" para confirmar la limpieza de actividad.')
            return render(request, 'gestion/actividad_limpiar_confirmar.html', {
                'eventos_eliminables': eventos_eliminables,
                'eventos_protegidos': eventos_protegidos,
            })

        try:
            cant = limpiar_actividad_prueba(admin_responsable=request.user)
            messages.success(request, f"Se eliminaron {cant} eventos de actividad de prueba exitosamente.")
        except Exception as e:
            messages.error(request, str(e))
        return redirect('gestion:actividad_lista')

    return render(request, 'gestion/actividad_limpiar_confirmar.html', {
        'eventos_eliminables': eventos_eliminables,
        'eventos_protegidos': eventos_protegidos,
    })


@staff_required
def fogatas_metricas_view(request):
    """
    Panel analítico específico de setlists (Fogatas) y sesiones compartidas.
    """
    metricas = obtener_metricas_fogatas_detalle()
    context = {
        'm': metricas,
        'inicio_analitica': obtener_analytics_start_date_str(),
    }
    return render(request, 'gestion/fogatas_metricas.html', context)


@staff_required
def metricas_detalladas_view(request):
    """
    Vista detallada de repertorios (distribución en buckets), retención 7 y 30 días,
    embudo de adopción e indicadores comerciales Freemium (Fase 8).
    """
    periodo = request.GET.get('periodo', 'todo')
    metricas_canciones = obtener_metricas_canciones_detalle(periodo)
    metricas_generales = obtener_metricas_dashboard()
    metricas_comerciales = obtener_metricas_comerciales()

    context = {
        'periodo': periodo,
        'mc': metricas_canciones,
        'mg': metricas_generales,
        'comercial': metricas_comerciales,
        'inicio_analitica': obtener_analytics_start_date_str(),
    }
    return render(request, 'gestion/metricas.html', context)


@staff_required
def exportar_usuarios_csv_view(request):
    """
    Exportación administrativa segura de usuarios a CSV (Criterios 21 y 22).
    - Sanitización contra Spreadsheet Formula Injection.
    - Exclusivamente metadatos agregados de cuenta y uso.
    - CERO letras, acordes, notas, passwords o tokens.
    """
    ahora = timezone.now()
    timestamp_str = ahora.strftime('%Y%m%d_%H%M')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="fogata_usuarios_{timestamp_str}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'ID',
        'Email',
        'Nombre',
        'Fecha Registro',
        'Ultimo Login',
        'Ultima Actividad',
        'Codigo Invitacion',
        'Tipo Cuenta',
        'Total Canciones',
        'Total Fogatas',
        'Sesiones Compartidas',
        'Usuario Activado',
        'Estado',
    ])

    usuarios = (
        User.objects.filter(is_staff=False)
        .select_related('perfil_piloto')
        .annotate(
            num_canciones=Count('canciones', distinct=True),
            num_fogatas=Count('fogatas', distinct=True),
            num_sesiones=Count('fogatas__sesiones_compartidas', distinct=True),
            ultima_actividad=Max('eventos_uso__fecha'),
            toco_count=Count('eventos_uso', filter=Q(eventos_uso__tipo_evento__in=['tocar_cancion', 'tocar_fogata']), distinct=True)
        )
        .order_by('-date_joined')
    )

    for u in usuarios:
        perfil = getattr(u, 'perfil_piloto', None)
        codigo_inv = perfil.codigo_invitacion if perfil else ""
        tipo_cuenta = perfil.tipo_cuenta if perfil else "PILOTO"
        estado = "ACTIVO" if u.is_active else "SUSPENDIDO"
        es_activado = "SI" if (u.num_canciones > 0 and u.toco_count > 0) else "NO"

        fecha_reg = u.date_joined.strftime('%Y-%m-%d %H:%M') if u.date_joined else ""
        ultimo_log = u.last_login.strftime('%Y-%m-%d %H:%M') if u.last_login else ""
        ult_act = u.ultima_actividad.strftime('%Y-%m-%d %H:%M') if u.ultima_actividad else "Sin eventos"

        writer.writerow([
            sanitizar_celda_csv(u.id),
            sanitizar_celda_csv(u.email),
            sanitizar_celda_csv(u.first_name),
            sanitizar_celda_csv(fecha_reg),
            sanitizar_celda_csv(ultimo_log),
            sanitizar_celda_csv(ult_act),
            sanitizar_celda_csv(codigo_inv),
            sanitizar_celda_csv(tipo_cuenta),
            sanitizar_celda_csv(u.num_canciones),
            sanitizar_celda_csv(u.num_fogatas),
            sanitizar_celda_csv(u.num_sesiones),
            sanitizar_celda_csv(es_activado),
            sanitizar_celda_csv(estado),
        ])

    return response


@staff_required
def pagos_lista_view(request):
    """
    Módulo de Pagos de Fogata Control Center (Fase 9).
    Despliega órdenes de pago con filtros por estado, ambiente, búsqueda
    y métricas clave de recaudación. Inmutable (sin edición arbitraria desde UI).
    """
    from apps.pagos.models import OrdenPago

    query = request.GET.get('q', '').strip()
    filtro_estado = request.GET.get('estado', 'todos').strip()
    filtro_ambiente = request.GET.get('ambiente', 'todos').strip()

    ordenes_qs = OrdenPago.objects.select_related('usuario').order_by('-creada_el')

    if query:
        ordenes_qs = ordenes_qs.filter(
            Q(commerce_order__icontains=query) |
            Q(usuario__email__icontains=query) |
            Q(flow_order__icontains=query)
        )

    if filtro_estado != 'todos':
        if filtro_estado == 'ERROR':
            ordenes_qs = ordenes_qs.filter(estado__in=[OrdenPago.ESTADO_ERROR_TECNICO, OrdenPago.ESTADO_ERROR_VALIDACION])
        else:
            ordenes_qs = ordenes_qs.filter(estado=filtro_estado)

    if filtro_ambiente != 'todos':
        ordenes_qs = ordenes_qs.filter(ambiente=filtro_ambiente)

    # Resumen rápido
    total_ordenes = ordenes_qs.count()
    pagadas_prod_count = OrdenPago.objects.filter(
        ambiente=OrdenPago.AMBIENTE_PRODUCTION,
        estado=OrdenPago.ESTADO_PAGADA
    ).count()
    pagadas_count = OrdenPago.objects.filter(estado=OrdenPago.ESTADO_PAGADA).count()
    pendientes_count = OrdenPago.objects.filter(estado=OrdenPago.ESTADO_PENDIENTE).count()
    ingresos_reales = OrdenPago.objects.filter(
        ambiente=OrdenPago.AMBIENTE_PRODUCTION,
        estado=OrdenPago.ESTADO_PAGADA
    ).aggregate(s=Sum('monto'))['s'] or 0
    ingresos_reales_fmt = f"{ingresos_reales:,}".replace(",", ".")

    paginator = Paginator(ordenes_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'ordenes': page_obj.object_list,
        'query': query,
        'filtro_estado': filtro_estado,
        'filtro_ambiente': filtro_ambiente,
        'total_ordenes': total_ordenes,
        'pagadas_prod_count': pagadas_prod_count,
        'pagadas_count': pagadas_count,
        'pendientes_count': pendientes_count,
        'ingresos_reales': ingresos_reales,
        'ingresos_reales_fmt': ingresos_reales_fmt,
    }
    return render(request, 'gestion/pagos.html', context)


@staff_required
def pago_eliminar_sandbox_view(request, pk):
    """
    Eliminación de una orden individual de Flow Sandbox (Fase 10).
    Bloquea terminantemente órdenes de Producción.
    """
    from apps.pagos.models import OrdenPago
    orden = get_object_or_404(OrdenPago, pk=pk)

    if orden.ambiente != OrdenPago.AMBIENTE_SANDBOX:
        messages.error(request, "Las órdenes de Producción son inmutables y no se pueden eliminar.")
        return redirect('gestion:pagos_lista')

    if request.method == 'POST':
        try:
            eliminar_orden_sandbox(orden, admin_responsable=request.user)
            messages.success(request, f"Orden de prueba Sandbox {orden.commerce_order} eliminada exitosamente.")
        except Exception as e:
            messages.error(request, str(e))
        return redirect('gestion:pagos_lista')

    return render(request, 'gestion/pago_eliminar_confirmar.html', {'orden': orden})


@staff_required
def pagos_limpiar_sandbox_view(request):
    """
    Limpieza masiva de todas las órdenes de prueba Sandbox (Fase 10).
    Exige confirmación explícita 'ELIMINAR'.
    """
    from apps.pagos.models import OrdenPago
    total_sandbox = OrdenPago.objects.filter(ambiente=OrdenPago.AMBIENTE_SANDBOX).count()
    prod_qs = OrdenPago.objects.filter(ambiente=OrdenPago.AMBIENTE_PRODUCTION, estado=OrdenPago.ESTADO_PAGADA)
    total_prod = prod_qs.count()
    ingresos_prod = prod_qs.aggregate(s=Sum('monto'))['s'] or 0
    ingresos_prod_fmt = f"{ingresos_prod:,}".replace(",", ".")

    if request.method == 'POST':
        confirmacion = request.POST.get('confirmacion', '').strip()
        if confirmacion != 'ELIMINAR':
            messages.error(request, 'Debes escribir exactamente "ELIMINAR" para confirmar la limpieza de órdenes Sandbox.')
            return render(request, 'gestion/pagos_limpiar_sandbox_confirmar.html', {
                'total_sandbox': total_sandbox,
                'total_prod': total_prod,
                'ingresos_prod_fmt': ingresos_prod_fmt,
            })

        try:
            cant = limpiar_ordenes_sandbox(admin_responsable=request.user)
            messages.success(request, f"Se eliminaron {cant} órdenes Sandbox exitosamente. Los pagos de Producción se mantuvieron intactos.")
        except Exception as e:
            messages.error(request, str(e))
        return redirect('gestion:pagos_lista')

    return render(request, 'gestion/pagos_limpiar_sandbox_confirmar.html', {
        'total_sandbox': total_sandbox,
        'total_prod': total_prod,
        'ingresos_prod_fmt': ingresos_prod_fmt,
    })


@staff_required
def mantenimiento_view(request):
    """
    Panel central de mantenimiento de datos y depuración controlada (Fase 10).
    """
    m = obtener_metricas_mantenimiento()
    return render(request, 'gestion/mantenimiento.html', {'m': m})


@staff_required
def mantenimiento_dry_run_view(request):
    """
    Simulación Dry Run de limpieza masiva y ejecución controlada con confirmación (Fase 10).
    """
    dry_run = obtener_dry_run_limpieza_usuarios()

    if request.method == 'POST':
        confirmacion = request.POST.get('confirmacion', '').strip()
        if confirmacion != 'CONFIRMAR LIMPIEZA':
            messages.error(request, 'Debes escribir exactamente "CONFIRMAR LIMPIEZA" para ejecutar la depuración masiva.')
            return render(request, 'gestion/mantenimiento_dry_run.html', {'dry_run': dry_run})

        try:
            res = ejecutar_limpieza_masiva_usuarios_prueba(admin_responsable=request.user)
            messages.success(
                request,
                f"Limpieza masiva completada: {res['total_usuarios']} usuarios, {res['total_canciones']} canciones y {res['total_sandbox']} órdenes Sandbox eliminadas."
            )
            return redirect('gestion:mantenimiento')
        except Exception as e:
            messages.error(request, str(e))
            return redirect('gestion:mantenimiento_dry_run')

    return render(request, 'gestion/mantenimiento_dry_run.html', {'dry_run': dry_run})


