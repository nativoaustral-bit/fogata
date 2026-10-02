"""
Vistas para el flujo comercial y de integración con Flow Chile.
Cumple con la separación estricta entre el POST técnico de Flow
y el GET de resultado recargable para el usuario final.
"""

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.conf import settings

from .models import OrdenPago
from .services import iniciar_checkout_pago, procesar_confirmacion_flow
from .flow import FlowError

logger = logging.getLogger(__name__)


@login_required
@require_POST
def crear_pago_view(request):
    """
    Inicia la creación de una orden y redirige al checkout de Flow.
    El precio es resuelto exclusivamente en el servidor según el plan solicitado.
    """
    plan = request.POST.get('plan', '').strip()
    checkout_request_id = request.POST.get('checkout_request_id', '').strip()

    if plan not in [OrdenPago.PLAN_PRO_6M, OrdenPago.PLAN_PRO_12M]:
        messages.error(request, "El plan seleccionado no es válido.")
        return redirect('pro')

    url_confirmation = request.build_absolute_uri(reverse('pagos:flow_confirmacion'))
    url_return = request.build_absolute_uri(reverse('pagos:flow_retorno'))

    try:
        orden, checkout_url = iniciar_checkout_pago(
            usuario=request.user,
            plan=plan,
            url_confirmation=url_confirmation,
            url_return=url_return,
            checkout_request_id=checkout_request_id
        )
        return redirect(checkout_url)
    except ValueError as e:
        messages.warning(request, str(e))
        return redirect('pro')
    except FlowError as e:
        messages.error(request, f"No pudimos conectar con la pasarela de pagos en este momento. Por favor reintenta en unos instantes. ({str(e)})")
        return redirect('pro')
    except Exception as e:
        logger.exception("Error inesperado en checkout: %s", str(e))
        messages.error(request, "Ocurrió un error inesperado al procesar tu solicitud. Intenta nuevamente.")
        return redirect('pro')


@csrf_exempt
@require_POST
def flow_confirmacion_view(request):
    """
    Webhook público servidor a servidor invocado por Flow.
    Responde HTTP 200 de forma oportuna tras procesar e identificar la orden.
    """
    token = request.POST.get('token', '').strip()
    if not token:
        logger.warning("Confirmación Flow recibida sin parámetro token.")
        return HttpResponseBadRequest("Token requerido.")

    try:
        orden = procesar_confirmacion_flow(token)
        logger.info("Confirmación procesada exitosamente para orden %s (Estado: %s).", orden.commerce_order, orden.estado)
        return HttpResponse("OK", status=200)
    except ValueError as e:
        logger.warning("Token inválido o no encontrado en confirmación Flow: %s", str(e))
        return HttpResponseBadRequest("Token no válido o no encontrado.")
    except Exception as e:
        logger.exception("Error interno procesando confirmación Flow: %s", str(e))
        # Retornar 200 o 500 según corresponda; Flow reintentará si es 500
        return HttpResponse("Error interno procesando callback", status=500)


@csrf_exempt
def flow_retorno_view(request):
    """
    Recepción técnica del retorno de Flow tras el checkout.
    Flow envía POST application/x-www-form-urlencoded con token=<token>.
    Esta vista consulta o verifica el estado técnico y redirige mediante
    un HTTP 302 hacia un GET limpio de resultado (GET /pagos/resultado/<commerce_order>/).
    """
    token = (request.POST.get('token') or request.GET.get('token') or '').strip()

    if not token:
        messages.warning(request, "No se recibió un identificador de pago desde la pasarela.")
        return redirect('pro')

    orden = OrdenPago.objects.filter(flow_token=token).first()
    if not orden:
        messages.error(request, "No encontramos una orden asociada a la sesión de pago indicada.")
        return redirect('pro')

    # Si la orden aún está PENDIENTE (porque el webhook servidor-servidor viene con latencia),
    # intentamos una confirmación síncrona aquí para mayor fluidez.
    if orden.estado == OrdenPago.ESTADO_PENDIENTE and not orden.pro_aplicado:
        try:
            orden = procesar_confirmacion_flow(token)
        except Exception as e:
            logger.warning("Fallo al verificar síncronamente en retorno para orden %s: %s", orden.commerce_order, str(e))

    # Redirección a la vista GET amigable y recargable
    return redirect('pagos:resultado', commerce_order=orden.commerce_order)


@login_required
def resultado_pago_view(request, commerce_order):
    """
    Página de resultado del pago para el usuario final.
    Es una vista GET idempotente y recargable que NUNCA concede privilegios Pro por sí misma.
    Solo lee el estado persistido por el servidor.
    """
    orden = get_object_or_404(OrdenPago, commerce_order=commerce_order, usuario=request.user)

    context = {
        'orden': orden,
        'es_pagada': orden.estado == OrdenPago.ESTADO_PAGADA,
        'es_pendiente': orden.estado == OrdenPago.ESTADO_PENDIENTE,
        'es_rechazada': orden.estado == OrdenPago.ESTADO_RECHAZADA,
        'es_anulada': orden.estado == OrdenPago.ESTADO_ANULADA,
        'es_error': orden.estado in (OrdenPago.ESTADO_ERROR_TECNICO, OrdenPago.ESTADO_ERROR_VALIDACION),
    }
    return render(request, 'pagos/resultado.html', context)


@login_required
def mi_cuenta_view(request):
    """
    Vista de perfil y resumen de cuenta del usuario:
    - Estado de su plan comercial activo y vigencia.
    - Historial personal de órdenes de pago.
    Protección estricta: el usuario solo ve sus propias compras.
    """
    from apps.core.planes import obtener_estado_capacidad, obtener_tipo_cuenta

    perfil = getattr(request.user, 'perfil_piloto', None)
    capacidad = obtener_estado_capacidad(request.user)
    tipo_cuenta = obtener_tipo_cuenta(request.user)

    # Solo las órdenes propias del usuario autenticado
    ordenes = OrdenPago.objects.filter(usuario=request.user).order_by('-creada_el')

    context = {
        'perfil': perfil,
        'capacidad': capacidad,
        'tipo_cuenta': tipo_cuenta,
        'ordenes': ordenes,
    }
    return render(request, 'core/mi_cuenta.html', context)
