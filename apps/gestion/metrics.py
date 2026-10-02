from datetime import timedelta
from django.db.models import Count, Max, Q, F, Sum
from django.db.models.functions import TruncDate
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.canciones.models import Cancion
from apps.fogatas.models import Fogata, SesionCompartida
from .models import EventoUso
from .constants import ACCIONES_USO_REAL, obtener_analytics_start_date

User = get_user_model()


def obtener_metricas_dashboard():
    """
    Calcula los indicadores principales para la portada de Fogata Control Center.
    Distingue estado de la base histórica de métricas de comportamiento real (Fase 7).
    """
    ahora = timezone.now()
    ahora_local = timezone.localtime(ahora)
    inicio_dia = ahora_local.replace(hour=0, minute=0, second=0, microsecond=0)
    hace_7_dias = ahora - timedelta(days=7)
    hace_30_dias = ahora - timedelta(days=30)
    start_analytics = obtener_analytics_start_date()

    # Base usuarios no-staff
    usuarios_non_staff = User.objects.filter(is_staff=False)
    usuarios_totales = usuarios_non_staff.count()

    usuarios_reg_7d = usuarios_non_staff.filter(date_joined__gte=hace_7_dias).count()
    usuarios_reg_30d = usuarios_non_staff.filter(date_joined__gte=hace_30_dias).count()

    # Eventos de uso real (excluyen login y registro)
    eventos_reales = EventoUso.objects.filter(
        usuario__is_staff=False,
        tipo_evento__in=ACCIONES_USO_REAL
    )

    # DAU, WAU, MAU basados estrictamente en acciones reales de producto
    # Se utiliza .order_by() explícito para evitar que Meta.ordering=['-fecha'] interfiera en DISTINCT/GROUP BY
    dau = eventos_reales.filter(fecha__gte=inicio_dia).order_by().values('usuario').distinct().count()
    wau = eventos_reales.filter(fecha__gte=hace_7_dias).order_by().values('usuario').distinct().count()
    mau = eventos_reales.filter(fecha__gte=hace_30_dias).order_by().values('usuario').distinct().count()

    # Usuarios sin actividad reciente en los últimos 30 días
    ids_activos_30d = set(eventos_reales.filter(fecha__gte=hace_30_dias).values_list('usuario_id', flat=True))
    usuarios_sin_actividad_30d = usuarios_non_staff.exclude(id__in=ids_activos_30d).count()

    # Usuario Recurrente 30 días: al menos 2 días distintos de actividad real en 30 días
    usuarios_recurrentes_30d = (
        eventos_reales.filter(fecha__gte=hace_30_dias)
        .order_by()
        .annotate(dia=TruncDate('fecha'))
        .values('usuario')
        .annotate(dias_activos=Count('dia', distinct=True))
        .filter(dias_activos__gte=2)
        .count()
    )

    # Usuarios Activados (Creó al menos 1 canción y utilizó Modo Tocar al menos 1 vez)
    ids_con_cancion = set(Cancion.objects.filter(propietario__is_staff=False).values_list('propietario_id', flat=True))
    ids_con_tocar = set(
        EventoUso.objects.filter(
            usuario__is_staff=False,
            tipo_evento__in=['tocar_cancion', 'tocar_fogata']
        ).values_list('usuario_id', flat=True)
    )
    ids_activados = ids_con_cancion.intersection(ids_con_tocar)
    usuarios_activados_total = len(ids_activados)
    tasa_activacion_total = round((usuarios_activados_total / usuarios_totales * 100), 1) if usuarios_totales > 0 else 0.0

    # Contenido (Estado actual)
    canciones_totales = Cancion.objects.count()
    canciones_7d = Cancion.objects.filter(created_at__gte=hace_7_dias).count()
    fogatas_totales = Fogata.objects.count()
    fogatas_7d = Fogata.objects.filter(created_at__gte=hace_7_dias).count()
    sesiones_compartidas_totales = SesionCompartida.objects.count()
    sesiones_compartidas_7d = SesionCompartida.objects.filter(creado_el__gte=hace_7_dias).count()

    # Uso en atriles y sesiones
    sesiones_tocar_cancion = EventoUso.objects.filter(tipo_evento='tocar_cancion').count()
    sesiones_tocar_fogata = EventoUso.objects.filter(tipo_evento='tocar_fogata').count()
    fogatas_tocadas_ids = set(
        EventoUso.objects.filter(tipo_evento='tocar_fogata', objeto_id__isnull=False)
        .values_list('objeto_id', flat=True)
    )
    fogatas_tocadas_count = len(fogatas_tocadas_ids)

    aperturas_sesion_compartida = EventoUso.objects.filter(tipo_evento='abrir_sesion_compartida').count()
    sesiones_abiertas_ids = set(
        EventoUso.objects.filter(tipo_evento='abrir_sesion_compartida', objeto_id__isnull=False)
        .values_list('objeto_id', flat=True)
    )
    sesiones_con_apertura_count = len(sesiones_abiertas_ids)
    pct_sesiones_abiertas = round((sesiones_con_apertura_count / sesiones_compartidas_totales * 100), 1) if sesiones_compartidas_totales > 0 else 0.0

    # Retención 7 y 30 días
    retencion_7d = calcular_retencion_7_dias()
    retencion_30d = calcular_retencion_30_dias()

    # Funnel de nuevos usuarios (Cohorte >= ANALYTICS_START_DATE)
    funnel = calcular_funnel_nuevos_usuarios()

    return {
        'usuarios_totales': usuarios_totales,
        'usuarios_reg_7d': usuarios_reg_7d,
        'usuarios_reg_30d': usuarios_reg_30d,
        'dau': dau,
        'wau': wau,
        'mau': mau,
        'usuarios_sin_actividad_30d': usuarios_sin_actividad_30d,
        'usuarios_recurrentes_30d': usuarios_recurrentes_30d,
        'usuarios_activados_total': usuarios_activados_total,
        'tasa_activacion_total': tasa_activacion_total,
        'canciones_totales': canciones_totales,
        'canciones_7d': canciones_7d,
        'fogatas_totales': fogatas_totales,
        'fogatas_7d': fogatas_7d,
        'sesiones_compartidas_totales': sesiones_compartidas_totales,
        'sesiones_compartidas_7d': sesiones_compartidas_7d,
        'sesiones_tocar_cancion': sesiones_tocar_cancion,
        'sesiones_tocar_fogata': sesiones_tocar_fogata,
        'fogatas_tocadas_count': fogatas_tocadas_count,
        'aperturas_sesion_compartida': aperturas_sesion_compartida,
        'sesiones_con_apertura_count': sesiones_con_apertura_count,
        'pct_sesiones_abiertas': pct_sesiones_abiertas,
        'retencion_7d': retencion_7d,
        'retencion_30d': retencion_30d,
        'funnel': funnel,
    }


def calcular_funnel_nuevos_usuarios():
    """
    Funnel estricto de activación para usuarios registrados a partir de ANALYTICS_START_DATE.
    Mide: Registro -> Primera canción -> Primer Modo Tocar -> Primera Fogata -> Fogata tocada -> Sesión compartida.
    """
    start_date = obtener_analytics_start_date()
    usuarios_cohorte = User.objects.filter(is_staff=False, date_joined__gte=start_date)
    total_registrados = usuarios_cohorte.count()

    if total_registrados == 0:
        return {
            'total_registrados': 0,
            'con_cancion': 0,
            'pct_cancion': 0.0,
            'con_modo_tocar': 0,
            'pct_modo_tocar': 0.0,
            'con_fogata': 0,
            'pct_fogata': 0.0,
            'con_fogata_tocada': 0,
            'pct_fogata_tocada': 0.0,
            'con_sesion_compartida': 0,
            'pct_sesion_compartida': 0.0,
        }

    con_cancion = usuarios_cohorte.filter(canciones__isnull=False).distinct().count()
    con_modo_tocar = usuarios_cohorte.filter(
        eventos_uso__tipo_evento__in=['tocar_cancion', 'tocar_fogata']
    ).distinct().count()
    con_fogata = usuarios_cohorte.filter(fogatas__isnull=False).distinct().count()
    con_fogata_tocada = usuarios_cohorte.filter(
        eventos_uso__tipo_evento='tocar_fogata'
    ).distinct().count()
    con_sesion_compartida = usuarios_cohorte.filter(
        fogatas__sesiones_compartidas__isnull=False
    ).distinct().count()

    return {
        'total_registrados': total_registrados,
        'con_cancion': con_cancion,
        'pct_cancion': round((con_cancion / total_registrados * 100), 1),
        'con_modo_tocar': con_modo_tocar,
        'pct_modo_tocar': round((con_modo_tocar / total_registrados * 100), 1),
        'con_fogata': con_fogata,
        'pct_fogata': round((con_fogata / total_registrados * 100), 1),
        'con_fogata_tocada': con_fogata_tocada,
        'pct_fogata_tocada': round((con_fogata_tocada / total_registrados * 100), 1),
        'con_sesion_compartida': con_sesion_compartida,
        'pct_sesion_compartida': round((con_sesion_compartida / total_registrados * 100), 1),
    }


def calcular_retencion_7_dias():
    """
    Retención 7 días:
    Usuarios no-staff registrados hace al menos 7 días (y desde inicio de analítica)
    que tuvieron alguna actividad real entre el día 1 y el día 7 posterior al registro.
    Retorna: {'retenidos': int, 'elegibles': int, 'porcentaje': float, 'texto': str}
    """
    ahora = timezone.now()
    limite_7d = ahora - timedelta(days=7)
    start_date = obtener_analytics_start_date()

    elegibles = User.objects.filter(
        is_staff=False,
        date_joined__gte=start_date,
        date_joined__lte=limite_7d
    )
    total_elegibles = elegibles.count()

    if total_elegibles == 0:
        return {'retenidos': 0, 'elegibles': 0, 'porcentaje': 0.0, 'texto': '0 de 0 (0,0%)'}

    retenidos_count = 0
    for u in elegibles:
        inicio_ventana = u.date_joined + timedelta(days=1)
        fin_ventana = u.date_joined + timedelta(days=7)
        tuvo_actividad = EventoUso.objects.filter(
            usuario=u,
            tipo_evento__in=ACCIONES_USO_REAL,
            fecha__gte=inicio_ventana,
            fecha__lte=fin_ventana
        ).exists()
        if tuvo_actividad:
            retenidos_count += 1

    pct = round((retenidos_count / total_elegibles * 100), 1)
    return {
        'retenidos': retenidos_count,
        'elegibles': total_elegibles,
        'porcentaje': pct,
        'texto': f"{retenidos_count} de {total_elegibles} ({str(pct).replace('.', ',')}%)"
    }


def calcular_retencion_30_dias():
    """
    Retención 30 días:
    Usuarios no-staff registrados hace al menos 30 días (y desde inicio de analítica)
    que tuvieron alguna actividad real entre el día 8 y el día 30 posterior al registro.
    Retorna: {'retenidos': int, 'elegibles': int, 'porcentaje': float, 'texto': str}
    """
    ahora = timezone.now()
    limite_30d = ahora - timedelta(days=30)
    start_date = obtener_analytics_start_date()

    elegibles = User.objects.filter(
        is_staff=False,
        date_joined__gte=start_date,
        date_joined__lte=limite_30d
    )
    total_elegibles = elegibles.count()

    if total_elegibles == 0:
        return {'retenidos': 0, 'elegibles': 0, 'porcentaje': 0.0, 'texto': '0 de 0 (0,0%)'}

    retenidos_count = 0
    for u in elegibles:
        inicio_ventana = u.date_joined + timedelta(days=8)
        fin_ventana = u.date_joined + timedelta(days=30)
        tuvo_actividad = EventoUso.objects.filter(
            usuario=u,
            tipo_evento__in=ACCIONES_USO_REAL,
            fecha__gte=inicio_ventana,
            fecha__lte=fin_ventana
        ).exists()
        if tuvo_actividad:
            retenidos_count += 1

    pct = round((retenidos_count / total_elegibles * 100), 1)
    return {
        'retenidos': retenidos_count,
        'elegibles': total_elegibles,
        'porcentaje': pct,
        'texto': f"{retenidos_count} de {total_elegibles} ({str(pct).replace('.', ',')}%)"
    }


def obtener_metricas_canciones_detalle(periodo='todo'):
    """
    Calcula métricas detalladas de repertorio:
    - Distribución en buckets: 0 canciones, 1-5, 6-20, >20 canciones.
    - Promedio por usuario activo y registrado.
    - Totales por periodo.
    """
    usuarios_non_staff = User.objects.filter(is_staff=False).annotate(
        num_canciones=Count('canciones', distinct=True)
    )
    total_usuarios = usuarios_non_staff.count()

    bucket_0 = usuarios_non_staff.filter(num_canciones=0).count()
    bucket_1_5 = usuarios_non_staff.filter(num_canciones__gte=1, num_canciones__lte=5).count()
    bucket_6_20 = usuarios_non_staff.filter(num_canciones__gte=6, num_canciones__lte=20).count()
    bucket_mas_20 = usuarios_non_staff.filter(num_canciones__gt=20).count()

    total_canciones = Cancion.objects.count()
    promedio_por_usuario = round(total_canciones / total_usuarios, 1) if total_usuarios > 0 else 0.0

    return {
        'total_canciones': total_canciones,
        'promedio_por_usuario': promedio_por_usuario,
        'bucket_0': bucket_0,
        'bucket_1_5': bucket_1_5,
        'bucket_6_20': bucket_6_20,
        'bucket_mas_20': bucket_mas_20,
        'pct_0': round(bucket_0 / total_usuarios * 100, 1) if total_usuarios > 0 else 0.0,
        'pct_1_5': round(bucket_1_5 / total_usuarios * 100, 1) if total_usuarios > 0 else 0.0,
        'pct_6_20': round(bucket_6_20 / total_usuarios * 100, 1) if total_usuarios > 0 else 0.0,
        'pct_mas_20': round(bucket_mas_20 / total_usuarios * 100, 1) if total_usuarios > 0 else 0.0,
    }


def obtener_metricas_fogatas_detalle():
    """
    Calcula métricas detalladas de Fogatas y sesiones compartidas.
    """
    ahora = timezone.now()
    hace_7_dias = ahora - timedelta(days=7)
    hace_30_dias = ahora - timedelta(days=30)

    fogatas_totales = Fogata.objects.count()
    fogatas_7d = Fogata.objects.filter(created_at__gte=hace_7_dias).count()
    fogatas_30d = Fogata.objects.filter(created_at__gte=hace_30_dias).count()

    ids_tocadas = set(
        EventoUso.objects.filter(tipo_evento='tocar_fogata', objeto_id__isnull=False)
        .values_list('objeto_id', flat=True)
    )
    fogatas_tocadas_count = Fogata.objects.filter(id__in=ids_tocadas).count()
    fogatas_nunca_tocadas = fogatas_totales - fogatas_tocadas_count
    pct_fogatas_tocadas = round((fogatas_tocadas_count / fogatas_totales * 100), 1) if fogatas_totales > 0 else 0.0

    fogatas_compartidas_count = Fogata.objects.filter(sesiones_compartidas__isnull=False).distinct().count()

    sesiones_totales = SesionCompartida.objects.count()
    sesiones_activas = SesionCompartida.objects.filter(activa=True, expira_el__gt=ahora).count()
    sesiones_revocadas = SesionCompartida.objects.filter(activa=False).count()
    sesiones_expiradas = SesionCompartida.objects.filter(activa=True, expira_el__lte=ahora).count()

    aperturas_totales = EventoUso.objects.filter(tipo_evento='abrir_sesion_compartida').count()
    sesiones_con_apertura_ids = set(
        EventoUso.objects.filter(tipo_evento='abrir_sesion_compartida', objeto_id__isnull=False)
        .values_list('objeto_id', flat=True)
    )
    sesiones_con_apertura = len(sesiones_con_apertura_ids)
    pct_sesiones_con_apertura = round((sesiones_con_apertura / sesiones_totales * 100), 1) if sesiones_totales > 0 else 0.0
    promedio_aperturas_por_sesion = round((aperturas_totales / sesiones_totales), 1) if sesiones_totales > 0 else 0.0

    return {
        'fogatas_totales': fogatas_totales,
        'fogatas_7d': fogatas_7d,
        'fogatas_30d': fogatas_30d,
        'fogatas_tocadas_count': fogatas_tocadas_count,
        'fogatas_nunca_tocadas': fogatas_nunca_tocadas,
        'pct_fogatas_tocadas': pct_fogatas_tocadas,
        'fogatas_compartidas_count': fogatas_compartidas_count,
        'sesiones_totales': sesiones_totales,
        'sesiones_activas': sesiones_activas,
        'sesiones_revocadas': sesiones_revocadas,
        'sesiones_expiradas': sesiones_expiradas,
        'aperturas_totales': aperturas_totales,
        'sesiones_con_apertura': sesiones_con_apertura,
        'pct_sesiones_con_apertura': pct_sesiones_con_apertura,
        'promedio_aperturas_por_sesion': promedio_aperturas_por_sesion,
    }


def obtener_metricas_comerciales():
    """
    Calcula indicadores comerciales del modelo Freemium (Fase 8):
    - Conteo por planes: GRATIS, PRO, PILOTO
    - Monitoreo de límites en cuentas GRATIS: 8-9 canciones, 10 canciones, 1 Fogata
    - Intención comercial y eventos comerciales:
        * vieron /pro/
        * alcanzaron límite de canciones
        * alcanzaron límite de Fogatas
    - Señales de conversión
    - Funnel comercial de conversión
    """
    from apps.core.models import PerfilPiloto
    from django.conf import settings

    max_canciones_gratis = getattr(settings, 'FOGATA_FREE_MAX_SONGS', 10)
    max_fogatas_gratis = getattr(settings, 'FOGATA_FREE_MAX_FOGATAS', 1)
    ahora = timezone.now()

    # Base usuarios no-staff
    usuarios_non_staff = User.objects.filter(is_staff=False)
    total_usuarios = usuarios_non_staff.count()

    # Identificación por planes
    cuentas_gratis_ids = set(
        PerfilPiloto.objects.filter(user__is_staff=False, tipo_cuenta='GRATIS')
        .values_list('user_id', flat=True)
    )
    cuentas_pro_ids = set(
        PerfilPiloto.objects.filter(user__is_staff=False, tipo_cuenta='PRO')
        .values_list('user_id', flat=True)
    )
    # PILOTO: cuentas explícitamente PILOTO o pre-existentes sin tipo_cuenta
    cuentas_piloto_ids = set(
        usuarios_non_staff.exclude(id__in=cuentas_gratis_ids.union(cuentas_pro_ids))
        .values_list('id', flat=True)
    )

    total_gratis = len(cuentas_gratis_ids)
    total_pro = len(cuentas_pro_ids)
    total_piloto = len(cuentas_piloto_ids)

    # Usuarios gratis con conteos de canciones y fogatas
    usuarios_gratis_qs = usuarios_non_staff.filter(id__in=cuentas_gratis_ids).annotate(
        num_canciones=Count('canciones', distinct=True),
        num_fogatas=Count('fogatas', distinct=True)
    )

    # Límites
    gratis_8_9_canciones = usuarios_gratis_qs.filter(num_canciones__gte=8, num_canciones__lt=max_canciones_gratis).count()
    gratis_10_canciones = usuarios_gratis_qs.filter(num_canciones__gte=max_canciones_gratis).count()
    gratis_1_fogata = usuarios_gratis_qs.filter(num_fogatas__gte=max_fogatas_gratis).count()

    # Intención: usuarios únicos con eventos comerciales (order_by() limpia el Meta.ordering para DISTINCT)
    usuarios_vieron_pro_ids = set(
        EventoUso.objects.filter(tipo_evento='ver_pro', usuario__isnull=False)
        .order_by().values_list('usuario_id', flat=True).distinct()
    )
    usuarios_limite_canciones_ids = set(
        EventoUso.objects.filter(tipo_evento='alcanzar_limite_canciones', usuario__isnull=False)
        .order_by().values_list('usuario_id', flat=True).distinct()
    )
    usuarios_limite_fogatas_ids = set(
        EventoUso.objects.filter(tipo_evento='alcanzar_limite_fogatas', usuario__isnull=False)
        .order_by().values_list('usuario_id', flat=True).distinct()
    )

    total_vieron_pro = len(usuarios_vieron_pro_ids)
    total_limite_canciones_evento = len(usuarios_limite_canciones_ids)
    total_limite_fogatas_evento = len(usuarios_limite_fogatas_ids)

    # Señales de conversión (Criterio 23):
    # Usuario Gratis que cumple al menos una:
    # - 10 canciones
    # - intenta crear canción 11 (evento alcanzar_limite_canciones)
    # - intenta crear segunda Fogata (evento alcanzar_limite_fogatas)
    # - visita página Pro después de alcanzar límite
    ids_gratis_10 = set(usuarios_gratis_qs.filter(num_canciones__gte=max_canciones_gratis).values_list('id', flat=True))
    ids_gratis_limite_canciones_evento = cuentas_gratis_ids.intersection(usuarios_limite_canciones_ids)
    ids_gratis_limite_fogatas_evento = cuentas_gratis_ids.intersection(usuarios_limite_fogatas_ids)
    ids_gratis_vieron_pro = cuentas_gratis_ids.intersection(usuarios_vieron_pro_ids)
    ids_gratis_vieron_pro_en_limite = ids_gratis_vieron_pro.intersection(
        ids_gratis_10.union(ids_gratis_limite_canciones_evento, ids_gratis_limite_fogatas_evento)
    )

    ids_senales_conversion = ids_gratis_10.union(
        ids_gratis_limite_canciones_evento,
        ids_gratis_limite_fogatas_evento,
        ids_gratis_vieron_pro_en_limite
    )
    total_senales_conversion = len(ids_senales_conversion)
    pct_senales_conversion = round(total_senales_conversion / total_gratis * 100, 1) if total_gratis > 0 else 0.0

    # Funnel comercial (Criterio 28):
    # 1. Usuario Gratis
    # 2. Usuario activado (canción + modo tocar)
    # 3. 8+ canciones
    # 4. Límite alcanzado
    # 5. Visitó Pro
    # 6. PRO
    ids_con_tocar = set(
        EventoUso.objects.filter(tipo_evento__in=['tocar_cancion', 'tocar_fogata'])
        .order_by().values_list('usuario_id', flat=True).distinct()
    )
    ids_gratis_con_cancion = set(usuarios_gratis_qs.filter(num_canciones__gt=0).values_list('id', flat=True))
    ids_gratis_activados = ids_gratis_con_cancion.intersection(ids_con_tocar)

    ids_gratis_8_mas = set(usuarios_gratis_qs.filter(num_canciones__gte=8).values_list('id', flat=True))
    ids_gratis_limite_alcanzado = ids_gratis_10.union(ids_gratis_limite_canciones_evento, ids_gratis_limite_fogatas_evento)
    ids_gratis_funnel_visito_pro = ids_gratis_limite_alcanzado.intersection(ids_gratis_vieron_pro)

    funnel = [
        {'etapa': 'Usuario Gratis', 'cantidad': total_gratis, 'pct': 100.0},
        {'etapa': 'Usuario activado', 'cantidad': len(ids_gratis_activados), 'pct': round(len(ids_gratis_activados) / total_gratis * 100, 1) if total_gratis > 0 else 0.0},
        {'etapa': '8+ canciones', 'cantidad': len(ids_gratis_8_mas), 'pct': round(len(ids_gratis_8_mas) / total_gratis * 100, 1) if total_gratis > 0 else 0.0},
        {'etapa': 'Límite alcanzado', 'cantidad': len(ids_gratis_limite_alcanzado), 'pct': round(len(ids_gratis_limite_alcanzado) / total_gratis * 100, 1) if total_gratis > 0 else 0.0},
        {'etapa': 'Visitó Pro', 'cantidad': len(ids_gratis_funnel_visito_pro), 'pct': round(len(ids_gratis_funnel_visito_pro) / total_gratis * 100, 1) if total_gratis > 0 else 0.0},
        {'etapa': 'PRO', 'cantidad': total_pro, 'pct': round(total_pro / total_usuarios * 100, 1) if total_usuarios > 0 else 0.0},
    ]

    # Métricas de pagos y suscripciones comerciales reales (Fase 9)
    from apps.pagos.models import OrdenPago

    # Órdenes de pago reales confirmadas en ambiente de PRODUCCIÓN (Ajuste 8 y 25)
    ordenes_pagadas_prod = OrdenPago.objects.filter(
        ambiente=OrdenPago.AMBIENTE_PRODUCTION,
        estado=OrdenPago.ESTADO_PAGADA
    )

    ventas_totales = ordenes_pagadas_prod.count()
    hace_30_dias = ahora - timedelta(days=30)
    ventas_30d = ordenes_pagadas_prod.filter(pagada_el__gte=hace_30_dias).count()

    ingresos_totales = ordenes_pagadas_prod.aggregate(s=Sum('monto'))['s'] or 0
    ingresos_30d = ordenes_pagadas_prod.filter(pagada_el__gte=hace_30_dias).aggregate(s=Sum('monto'))['s'] or 0

    # Distinción de planes: Semestral vs Anual
    ventas_semestral = ordenes_pagadas_prod.filter(plan=OrdenPago.PLAN_PRO_6M).count()
    ventas_anual = ordenes_pagadas_prod.filter(plan=OrdenPago.PLAN_PRO_12M).count()
    pct_ventas_semestral = round(ventas_semestral / ventas_totales * 100, 1) if ventas_totales > 0 else 0.0
    pct_ventas_anual = round(ventas_anual / ventas_totales * 100, 1) if ventas_totales > 0 else 0.0

    # Distinción estricta: PRO activo total vs PRO pagado activo (Ajuste 10)
    pro_activos_totales = PerfilPiloto.objects.filter(
        tipo_cuenta='PRO',
        user__is_staff=False
    ).filter(
        Q(fecha_fin_plan__isnull=True) | Q(fecha_fin_plan__gt=ahora)
    ).count()

    ids_usuarios_con_pago_activo = set(
        ordenes_pagadas_prod.filter(
            fecha_fin_plan__gt=ahora
        ).values_list('usuario_id', flat=True)
    )
    pro_pagados_activos = len(ids_usuarios_con_pago_activo)

    pro_vencidos = PerfilPiloto.objects.filter(
        tipo_cuenta='PRO',
        fecha_fin_plan__isnull=False,
        fecha_fin_plan__lte=ahora,
        user__is_staff=False
    ).count()

    ingresos_totales_fmt = f"{ingresos_totales:,}".replace(",", ".")
    ingresos_30d_fmt = f"{ingresos_30d:,}".replace(",", ".")

    return {
        'total_usuarios': total_usuarios,
        'total_gratis': total_gratis,
        'total_pro': total_pro,
        'total_piloto': total_piloto,
        'gratis_8_9_canciones': gratis_8_9_canciones,
        'gratis_10_canciones': gratis_10_canciones,
        'gratis_1_fogata': gratis_1_fogata,
        'total_vieron_pro': total_vieron_pro,
        'total_limite_canciones_evento': total_limite_canciones_evento,
        'total_limite_fogatas_evento': total_limite_fogatas_evento,
        'total_senales_conversion': total_senales_conversion,
        'pct_senales_conversion': pct_senales_conversion,
        'funnel': funnel,
        # Nuevas métricas comerciales Fase 9
        'ventas_totales': ventas_totales,
        'ventas_30d': ventas_30d,
        'ingresos_totales': ingresos_totales,
        'ingresos_totales_fmt': ingresos_totales_fmt,
        'ingresos_30d': ingresos_30d,
        'ingresos_30d_fmt': ingresos_30d_fmt,
        'pro_activos_totales': pro_activos_totales,
        'pro_pagados_activos': pro_pagados_activos,
        'pro_vencidos': pro_vencidos,
        'conversion_gratis_pro': conversion_gratis_pro,
        'ventas_semestral': ventas_semestral,
        'ventas_anual': ventas_anual,
        'pct_ventas_semestral': pct_ventas_semestral,
        'pct_ventas_anual': pct_ventas_anual,
    }
