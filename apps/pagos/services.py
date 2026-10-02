"""
Servicios comerciales y de orquestación de pagos Flow para Fogata.
Implementa idempotencia atómica condicional para SQLite, cálculo exacto
de meses calendario, defensa en profundidad y sanitización estricta de metadatos.
"""

import calendar
import logging
import secrets
from datetime import datetime
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import OrdenPago
from .flow import FlowClient, FlowNetworkError, FlowAPIError

logger = logging.getLogger(__name__)


def sumar_meses_calendario(dt: datetime, meses: int) -> datetime:
    """
    Suma 'meses' calendario a un datetime manteniendo la zona horaria y
    ajustando al último día válido del mes de destino si este tiene menos días.
    Ej: 31 de Agosto + 6 meses -> 28 de Febrero (o 29 en año bisiesto).
    """
    mes_destino = dt.month - 1 + meses
    anio_destino = dt.year + mes_destino // 12
    mes_destino = mes_destino % 12 + 1
    dia_maximo = calendar.monthrange(anio_destino, mes_destino)[1]
    dia_destino = min(dt.day, dia_maximo)
    return dt.replace(year=anio_destino, month=mes_destino, day=dia_destino)


def generar_commerce_order(plan: str) -> str:
    """
    Genera un identificador único, aleatorio y legible para soporte:
    Formato: FOG-{6M|12M}-{AAAAMMDD}-{HEX16}
    """
    prefix = '6M' if plan == OrdenPago.PLAN_PRO_6M else '12M'
    fecha_str = timezone.now().strftime('%Y%m%d')
    random_hex = secrets.token_hex(8).upper()  # 16 caracteres hexadecimales
    return f"FOG-{prefix}-{fecha_str}-{random_hex}"


def obtener_precio_plan(plan: str) -> int:
    """
    Resuelve el monto oficial exclusivamente desde la configuración central del servidor.
    Nunca confía en datos enviados por el navegador.
    """
    if plan == OrdenPago.PLAN_PRO_6M:
        return getattr(settings, 'FOGATA_PRO_SEMESTRAL_PRICE_CLP', 5990)
    elif plan == OrdenPago.PLAN_PRO_12M:
        return getattr(settings, 'FOGATA_PRO_ANUAL_PRICE_CLP', 9990)
    else:
        raise ValueError(f"Plan comercial no reconocido: {plan}")


def obtener_asunto_plan(plan: str) -> str:
    if plan == OrdenPago.PLAN_PRO_6M:
        return "Fogata Pro — 6 meses"
    elif plan == OrdenPago.PLAN_PRO_12M:
        return "Fogata Pro — 12 meses"
    return "Fogata Pro"


def iniciar_checkout_pago(usuario, plan: str, url_confirmation: str, url_return: str,
                          checkout_request_id: str = '', client: FlowClient = None) -> tuple[OrdenPago, str]:
    """
    Inicia el flujo de compra:
    1. Verifica que los pagos estén habilitados.
    2. Resuelve el precio server-side.
    3. Previene doble submit accidental mediante checkout_request_id.
    4. Crea OrdenPago en base de datos.
    5. Invoca /payment/create en Flow fuera de transacciones abiertas.
    6. Actualiza la orden con el token y redirige.
    """
    pagos_habilitados = getattr(settings, 'FOGATA_PAYMENTS_ENABLED', False)
    if not pagos_habilitados:
        raise ValueError("Los pagos en línea no están habilitados actualmente en la plataforma.")

    monto = obtener_precio_plan(plan)
    subject = obtener_asunto_plan(plan)
    ambiente = getattr(settings, 'FLOW_ENVIRONMENT', 'sandbox').upper()
    timeout_segundos = getattr(settings, 'FLOW_PAYMENT_TIMEOUT', 3600)

    # Prevención de doble creación accidental (Ajuste 11)
    if checkout_request_id:
        limite_tiempo = timezone.now() - timezone.timedelta(minutes=15)
        orden_existente = OrdenPago.objects.filter(
            usuario=usuario,
            checkout_request_id=checkout_request_id,
            plan=plan,
            estado__in=[OrdenPago.ESTADO_CREADA, OrdenPago.ESTADO_PENDIENTE],
            creada_el__gte=limite_tiempo,
            flow_token__isnull=False
        ).first()

        if orden_existente and orden_existente.flow_token:
            # Reutilizar la sesión existente si aún no expira
            flow_client = client or FlowClient()
            redirect_url = f"{flow_client.base_url.replace('/api', '')}/app/web/pay.php?token={orden_existente.flow_token}"
            # O si guardamos la URL oficial devuelta
            return orden_existente, redirect_url

    commerce_order = generar_commerce_order(plan)

    # 1. Crear registro local en estado CREADA
    orden = OrdenPago.objects.create(
        usuario=usuario,
        commerce_order=commerce_order,
        plan=plan,
        monto=monto,
        moneda='CLP',
        estado=OrdenPago.ESTADO_CREADA,
        ambiente=ambiente,
        checkout_request_id=checkout_request_id
    )

    # 2. Llamada a Flow FUERA de transacción
    flow_client = client or FlowClient()
    try:
        resp = flow_client.crear_pago(
            commerce_order=commerce_order,
            subject=subject,
            amount=monto,
            email=usuario.email,
            url_confirmation=url_confirmation,
            url_return=url_return,
            timeout_orden=timeout_segundos
        )
    except Exception as e:
        orden.estado = OrdenPago.ESTADO_ERROR_TECNICO
        orden.detalles_error = str(e)
        orden.save(update_fields=['estado', 'detalles_error', 'actualizada_el'])
        logger.error("Error al crear pago en Flow para orden %s: %s", commerce_order, str(e))
        raise

    # 3. Guardar token y pasar a PENDIENTE
    orden.flow_token = resp['token']
    orden.flow_order = resp.get('flowOrder')
    orden.estado = OrdenPago.ESTADO_PENDIENTE
    orden.save(update_fields=['flow_token', 'flow_order', 'estado', 'actualizada_el'])

    # 4. Registrar evento de inicio de pago (metadatos limpios)
    try:
        from apps.gestion.services import registrar_evento
        registrar_evento(
            usuario=usuario,
            tipo_evento='iniciar_pago',
            metadata={'plan': plan, 'monto': monto}
        )
    except Exception:
        pass

    checkout_url = f"{resp['url']}?token={resp['token']}"
    return orden, checkout_url


def aplicar_extension_pro(usuario, plan: str) -> tuple[datetime, datetime, bool]:
    """
    Calcula y aplica la vigencia de Fogata Pro en PerfilPiloto.
    - Soporta meses calendario exactos.
    - Si es renovación anticipada, la extensión comienza desde fecha_fin actual (cero días perdidos).
    - Retorna (fecha_inicio, fecha_fin, es_renovacion).
    """
    from apps.core.models import PerfilPiloto
    from apps.gestion.services import registrar_evento

    perfil, _ = PerfilPiloto.objects.get_or_create(user=usuario)
    meses = 6 if plan == OrdenPago.PLAN_PRO_6M else 12
    ahora = timezone.now()

    # Si ya es PRO vigente, extender desde fecha_fin existente
    if perfil.tipo_cuenta == 'PRO' and perfil.fecha_fin_plan and perfil.fecha_fin_plan > ahora:
        es_renovacion = True
        inicio = perfil.fecha_inicio_plan or ahora
        fin = sumar_meses_calendario(perfil.fecha_fin_plan, meses)
    else:
        es_renovacion = False
        inicio = ahora
        fin = sumar_meses_calendario(ahora, meses)

    perfil.tipo_cuenta = 'PRO'
    perfil.estado_suscripcion = 'ACTIVA'
    perfil.fecha_inicio_plan = inicio
    perfil.fecha_fin_plan = fin
    perfil.save(update_fields=['tipo_cuenta', 'estado_suscripcion', 'fecha_inicio_plan', 'fecha_fin_plan'])

    # Registrar eventos limpios
    try:
        registrar_evento(
            usuario=usuario,
            tipo_evento='pago_confirmado',
            metadata={'plan': plan}
        )
        registrar_evento(
            usuario=usuario,
            tipo_evento='renovacion_pro' if es_renovacion else 'upgrade_pro',
            metadata={'plan': plan, 'meses': meses}
        )
    except Exception:
        pass

    return inicio, fin, es_renovacion


def procesar_confirmacion_flow(token: str, client: FlowClient = None) -> OrdenPago:
    """
    Procesa de manera segura e idempotente la confirmación de un pago:
    A. Valida existencia de la orden por flow_token.
    B. Si ya tiene pro_aplicado=True, retorna sin efectos colaterales (idempotencia).
    C. Consulta Flow payment/getStatus FUERA de transacción SQLite.
    D. Valida status, monto, moneda y commerceOrder.
    E. Abre transacción atómica corta con UPDATE condicional sobre pro_aplicado.
    F. Si rows_updated == 1, aplica vigencia Pro.
    G. Retorna la orden actualizada.
    """
    if not token:
        raise ValueError("Token de Flow no proporcionado.")

    orden = OrdenPago.objects.filter(flow_token=token).first()
    if not orden:
        logger.warning("Intento de confirmación con token desconocido: %s", token[:10])
        raise ValueError(f"Orden no encontrada para el token indicado.")

    # Idempotencia inmediata si ya está pagada y aplicada
    if orden.pro_aplicado and orden.estado == OrdenPago.ESTADO_PAGADA:
        logger.info("Orden %s ya fue procesada y aplicada previamente. Retornando no-op.", orden.commerce_order)
        return orden

    # B. Consulta a Flow FUERA de la transacción de base de datos (Ajuste 2)
    flow_client = client or FlowClient()
    try:
        flow_data = flow_client.obtener_estado_pago(token)
    except FlowNetworkError as e:
        # Error transitorio de red: mantener PENDIENTE para reconciliación posterior (Ajuste 4 y 14)
        logger.warning("Fallo temporal de red consultando Flow para orden %s: %s", orden.commerce_order, str(e))
        orden.detalles_error = f"Fallo temporal de red en consulta de confirmación: {str(e)}"
        orden.save(update_fields=['detalles_error', 'actualizada_el'])
        return orden
    except FlowAPIError as e:
        logger.error("Error de API Flow consultando estado para orden %s: %s", orden.commerce_order, str(e))
        orden.detalles_error = f"Error devuelto por Flow: {str(e)}"
        orden.save(update_fields=['detalles_error', 'actualizada_el'])
        return orden

    status = flow_data.get('status')
    commerce_order_flow = flow_data.get('commerceOrder')
    amount_flow = flow_data.get('amount')
    currency_flow = flow_data.get('currency')
    flow_order = flow_data.get('flowOrder')

    # Sanitización estricta de metadatos (Ajuste 6: whitelist técnica, NO raw, NO payer, NO paymentData)
    media_pago = None
    if isinstance(flow_data.get('paymentData'), dict):
        media_pago = flow_data['paymentData'].get('media')

    flow_metadata_sanitizada = {
        'status': status,
        'flowOrder': flow_order,
        'commerceOrder': commerce_order_flow,
        'amount': amount_flow,
        'currency': currency_flow,
        'paymentMethod': media_pago,
    }

    # C. Validaciones técnicas obligatorias antes de activar Pro (Ajuste 15)
    # Status oficial Flow: 1=Pendiente, 2=Pagada, 3=Rechazada, 4=Anulada
    if status == 2:
        # Validar consistencia contable
        discrepancia = None
        if str(commerce_order_flow) != str(orden.commerce_order):
            discrepancia = f"commerceOrder no coincide: local={orden.commerce_order}, flow={commerce_order_flow}"
        elif int(amount_flow) != orden.monto:
            discrepancia = f"amount no coincide: local={orden.monto}, flow={amount_flow}"
        elif str(currency_flow).upper() != str(orden.moneda).upper():
            discrepancia = f"currency no coincide: local={orden.moneda}, flow={currency_flow}"

        if discrepancia:
            logger.critical("ALERTA DE SEGURIDAD en orden %s: %s", orden.commerce_order, discrepancia)
            orden.estado = OrdenPago.ESTADO_ERROR_VALIDACION
            orden.detalles_error = discrepancia
            orden.flow_metadata = flow_metadata_sanitizada
            orden.save(update_fields=['estado', 'detalles_error', 'flow_metadata', 'actualizada_el'])
            return orden

        # D. Transacción atómica corta con UPDATE condicional compatible con SQLite (Ajuste 1 y 2)
        ahora = timezone.now()
        with transaction.atomic():
            # Operación atómica condicional: Solo una confirmación concurrentemente puede pasar pro_aplicado de False a True
            filas_actualizadas = OrdenPago.objects.filter(
                id=orden.id,
                pro_aplicado=False
            ).update(
                pro_aplicado=True,
                estado=OrdenPago.ESTADO_PAGADA,
                pagada_el=ahora,
                flow_order=flow_order,
                flow_metadata=flow_metadata_sanitizada,
                actualizada_el=ahora
            )

            if filas_actualizadas == 1:
                # Solo el hilo ganador extiende el plan
                inicio, fin, es_renovacion = aplicar_extension_pro(orden.usuario, orden.plan)
                OrdenPago.objects.filter(id=orden.id).update(
                    fecha_inicio_plan=inicio,
                    fecha_fin_plan=fin
                )
                orden.refresh_from_db()
                logger.info("Pago confirmado exitosamente para orden %s (Usuario: %s). Pro vigente hasta %s.",
                            orden.commerce_order, orden.usuario.email, fin)
            else:
                # Ya fue aplicado por otro proceso concurrente
                orden.refresh_from_db()
                logger.info("Orden %s ya fue aplicada concurrentemente por otra petición. No-op.", orden.commerce_order)

        return orden

    elif status == 3:
        # Rechazada por el medio de pago
        orden.estado = OrdenPago.ESTADO_RECHAZADA
        orden.flow_order = flow_order
        orden.flow_metadata = flow_metadata_sanitizada
        orden.save(update_fields=['estado', 'flow_order', 'flow_metadata', 'actualizada_el'])
        try:
            from apps.gestion.services import registrar_evento_uso
            registrar_evento_uso(usuario=orden.usuario, tipo_evento='pago_rechazado', metadata={'plan': orden.plan})
        except Exception:
            pass
        return orden

    elif status == 4:
        # Anulada o cancelada
        orden.estado = OrdenPago.ESTADO_ANULADA
        orden.flow_order = flow_order
        orden.flow_metadata = flow_metadata_sanitizada
        orden.save(update_fields=['estado', 'flow_order', 'flow_metadata', 'actualizada_el'])
        return orden

    elif status == 1:
        # Permanece pendiente
        orden.estado = OrdenPago.ESTADO_PENDIENTE
        orden.flow_order = flow_order
        orden.flow_metadata = flow_metadata_sanitizada
        orden.save(update_fields=['estado', 'flow_order', 'flow_metadata', 'actualizada_el'])
        return orden

    else:
        # Estado desconocido
        orden.estado = OrdenPago.ESTADO_ERROR_TECNICO
        orden.detalles_error = f"Estado Flow no documentado: {status}"
        orden.flow_metadata = flow_metadata_sanitizada
        orden.save(update_fields=['estado', 'detalles_error', 'flow_metadata', 'actualizada_el'])
        return orden
