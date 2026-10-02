import csv
from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseNotAllowed
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q, F, Sum
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
from .services import registrar_auditoria_admin
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
    Tabla de usuarios con búsqueda, filtros de adopción, ordenación y prevención estricta de N+1 queries.
    """
    query = request.GET.get('q', '').strip()
    filtro_estado = request.GET.get('estado', 'todos').strip()
    filtro_tipo = request.GET.get('filtro', 'todos').strip()

    ahora = timezone.now()
    hace_7dias = ahora - timedelta(days=7)
    hace_30dias = ahora - timedelta(days=30)

    # Base con anotaciones optimizadas para evitar N+1 queries (Criterio 29)
    usuarios = (
        User.objects.filter(is_staff=False)
        .select_related('perfil_piloto')
        .annotate(
            num_canciones=Count('canciones', distinct=True),
            num_fogatas=Count('fogatas', distinct=True),
            num_sesiones=Count('fogatas__sesiones_compartidas', distinct=True),
            ultima_actividad=Max('eventos_uso__fecha')
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

    # Filtro de adopción / comportamiento
    if filtro_tipo == 'reg_7d':
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
    if usuario == request.user:
        messages.error(request, "No puedes suspender tu propia cuenta de administrador.")
        return redirect('gestion:usuario_detalle', pk=usuario.pk)

    if not usuario.is_active:
        messages.info(request, "La cuenta ya se encuentra suspendida.")
        return redirect('gestion:usuario_detalle', pk=usuario.pk)

    usuario.is_active = False
    usuario.save(update_fields=['is_active'])

    registrar_auditoria_admin(
        admin=request.user,
        usuario_afectado=usuario,
        accion='suspender_usuario',
        detalles=f"Cuenta suspendida por {request.user.email}"
    )

    messages.warning(request, f"La cuenta de {usuario.email} ha sido suspendida. No podrá acceder a Fogata.")
    return redirect('gestion:usuario_detalle', pk=usuario.pk)


@staff_required
@require_POST
def usuario_reactivar_view(request, pk):
    """
    Reactiva una cuenta previamente suspendida (is_active=True) y registra en auditoría.
    """
    usuario = get_object_or_404(User, pk=pk)
    if usuario.is_active:
        messages.info(request, "La cuenta ya está activa.")
        return redirect('gestion:usuario_detalle', pk=usuario.pk)

    usuario.is_active = True
    usuario.save(update_fields=['is_active'])

    registrar_auditoria_admin(
        admin=request.user,
        usuario_afectado=usuario,
        accion='reactivar_usuario',
        detalles=f"Cuenta reactivada por {request.user.email}"
    )

    messages.success(request, f"La cuenta de {usuario.email} ha sido reactivada exitosamente.")
    return redirect('gestion:usuario_detalle', pk=usuario.pk)


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
    Historial cronológico completo de eventos con paginación y filtro por tipo.
    """
    tipo_filtro = request.GET.get('tipo', '').strip()
    eventos = EventoUso.objects.select_related('usuario').order_by('-fecha')

    if tipo_filtro:
        eventos = eventos.filter(tipo_evento=tipo_filtro)

    paginator = Paginator(eventos, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'tipo_filtro': tipo_filtro,
        'tipos_evento': EventoUso.TIPOS_EVENTO,
        'total_eventos': paginator.count,
    }
    return render(request, 'gestion/actividad_lista.html', context)


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

