# IMPLEMENTATION PLAN — FASE 9: INTEGRACIÓN COMERCIAL REAL CON FLOW (AJUSTADO)
## Fogata Pro Commercial Engine & Flow Chile Gateway

> **Fecha:** 02 de Octubre de 2026  
> **Estado:** **APROBADO CON AJUSTES (RELEASE GATE SANDBOX)**  
> **Principio rector:** *Una orden puede llegar muchas veces. Un pago debe otorgar acceso Pro exactamente una vez.*  
> **Modelo comercial:** *Pago único anticipado por período (Semestral 6 meses / Anual 12 meses). Sin suscripción autorrenovable en esta versión.*

---

## 1. Modelo `OrdenPago` (`apps/pagos/models.py`)

Se crea la aplicación dedicada `apps/pagos/` con el modelo `OrdenPago`. Representa el ciclo de vida contable y transaccional de cada intención de compra.

### 1.1 Estructura del Modelo:
```python
from django.db import models
from django.conf import settings
from django.utils import timezone


class OrdenPago(models.Model):
    PLAN_PRO_6M = 'PRO_6M'
    PLAN_PRO_12M = 'PRO_12M'
    PLAN_CHOICES = [
        (PLAN_PRO_6M, 'Fogata Pro Semestral (6 meses)'),
        (PLAN_PRO_12M, 'Fogata Pro Anual (12 meses)'),
    ]

    ESTADO_CREADA = 'CREADA'
    ESTADO_PENDIENTE = 'PENDIENTE'
    ESTADO_PAGADA = 'PAGADA'
    ESTADO_RECHAZADA = 'RECHAZADA'
    ESTADO_ANULADA = 'ANULADA'
    ESTADO_ERROR_TECNICO = 'ERROR_TECNICO'
    ESTADO_ERROR_VALIDACION = 'ERROR_VALIDACION'
    ESTADO_CHOICES = [
        (ESTADO_CREADA, 'Creada localmente'),
        (ESTADO_PENDIENTE, 'En espera de pago (Checkout Flow)'),
        (ESTADO_PAGADA, 'Pagada y confirmada'),
        (ESTADO_RECHAZADA, 'Rechazada por medio de pago'),
        (ESTADO_ANULADA, 'Anulada o expirada por usuario'),
        (ESTADO_ERROR_TECNICO, 'Error de conectividad transitorio'),
        (ESTADO_ERROR_VALIDACION, 'Discrepancia en monto/moneda/orden'),
    ]

    AMBIENTE_SANDBOX = 'SANDBOX'
    AMBIENTE_PRODUCTION = 'PRODUCTION'
    AMBIENTE_CHOICES = [
        (AMBIENTE_SANDBOX, 'Sandbox (Pruebas)'),
        (AMBIENTE_PRODUCTION, 'Producción (Real)'),
    ]

    # Relación de usuario con PROTECT para preservar historial financiero
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='ordenes_pago',
        verbose_name='Usuario'
    )

    # Identificadores de orden
    commerce_order = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name='Orden de Comercio (Fogata)'
    )
    flow_order = models.BigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Orden oficial Flow'
    )
    flow_token = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        verbose_name='Token de sesión Flow'
    )
    checkout_request_id = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        verbose_name='ID de solicitud de checkout (Prevención doble submit)'
    )

    # Ambiente de ejecución registrado al momento de creación
    ambiente = models.CharField(
        max_length=20,
        choices=AMBIENTE_CHOICES,
        default=AMBIENTE_SANDBOX,
        db_index=True,
        verbose_name='Ambiente'
    )

    # Parámetros comerciales (determinados exclusivamente por el servidor)
    plan = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        verbose_name='Plan contratado'
    )
    monto = models.PositiveIntegerField(
        verbose_name='Monto en CLP'
    )
    moneda = models.CharField(
        max_length=5,
        default='CLP',
        verbose_name='Moneda'
    )

    # Máquina de estados
    estado = models.CharField(
        max_length=25,
        choices=ESTADO_CHOICES,
        default=ESTADO_CREADA,
        db_index=True,
        verbose_name='Estado'
    )

    # Bandera atómica de idempotencia estricta para SQLite
    pro_aplicado = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Beneficio Pro aplicado'
    )

    # Marcas temporales
    creada_el = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Creada el'
    )
    actualizada_el = models.DateTimeField(
        auto_now=True,
        verbose_name='Actualizada el'
    )
    pagada_el = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Pagada el'
    )

    # Vigencia asignada por esta orden específica
    fecha_inicio_plan = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha inicio del período'
    )
    fecha_fin_plan = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha fin del período'
    )

    # Diagnóstico técnico y auditoría interna (sin secretos ni datos de tarjeta)
    detalles_error = models.TextField(
        blank=True,
        verbose_name='Detalles técnicos / Discrepancias'
    )
    # Whitelist estricta de metadatos técnicos devueltos por Flow (NUNCA raw response, ni payer, ni paymentData completo)
    flow_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadatos técnicos sanitizados de Flow'
    )

    class Meta:
        verbose_name = 'Orden de Pago'
        verbose_name_plural = 'Órdenes de Pago'
        ordering = ['-creada_el']
        indexes = [
            models.Index(fields=['usuario', 'estado']),
            models.Index(fields=['ambiente', 'estado']),
            models.Index(fields=['estado', 'creada_el']),
        ]
```

### 1.2 Generación de `commerce_order`:
- Formato: `FOG-{PLAN_PREFIX}-{AAAAMMDD}-{HEX16}`
  - Ejemplo: `FOG-6M-20261002-3F9A1B2C8D4E5071`
  - Longitud aleatoria ampliada (16 caracteres hexadecimales) + índice `unique=True` en base de datos.

---

## 2. Cliente API Flow (`apps/pagos/flow.py`)

- **Cero dependencias externas:** Librería estándar de Python (`urllib.request`, `urllib.parse`, `json`, `hmac`, `hashlib`).
- **Timeouts controlados:** 5 a 7 segundos para llamadas críticas de confirmación/webhook, evitando colgar procesos y cumpliendo holgadamente el límite de Flow (<15s).
- **Parámetro `timeout` en `payment/create`:** Configurado por defecto en 3600 segundos (60 minutos) para evitar órdenes impagas indefinidamente abiertas.
- **Fail-safe en Producción:** Si `FOGATA_PAYMENTS_ENABLED=True` y `FLOW_ENVIRONMENT=production`, pero faltan credenciales o URLs, lanza excepción segura sin degradar jamás a Sandbox de manera silenciosa.

---

## 3. Firmado HMAC Flow (`apps/pagos/signing.py`)

Algoritmo oficial Flow:
1. Filtrar parámetros (excluir `s`).
2. Ordenar claves alfabéticamente.
3. Concatenar `clave + str(valor)`.
4. Resumen HMAC SHA-256 usando `FLOW_SECRET_KEY` en UTF-8.
5. Hexdigest en minúsculas enviado como parámetro `s`.

---

## 4. Creación de Orden y Prevención de Doble Checkout

- Endpoint: `POST /pagos/crear/` (Autenticado).
- Interruptor general: Si `not FOGATA_PAYMENTS_ENABLED`, deniega la creación e informa estado no disponible.
- Resolución autoritativa de precio en servidor:
  - `PRO_6M`: $5.990 CLP (settings.FOGATA_PRO_SEMESTRAL_PRICE_CLP).
  - `PRO_12M`: $9.990 CLP (settings.FOGATA_PRO_ANUAL_PRICE_CLP).
  - Cualquier campo `amount`, `monto` o `precio` en POST es ignorado o rechazado.
- **Prevención de doble click accidental:**
  - El formulario envía `checkout_request_id`.
  - Si el usuario reenvía el mismo `checkout_request_id` dentro de una ventana de tiempo reciente para una orden en estado `CREADA` o `PENDIENTE`, se reutiliza la redirección existente sin crear una orden duplicada.
- Flow `payment/create` es invocado fuera de transacciones abiertas.
- Al obtener `url`, `token`, `flowOrder`, se guarda `flow_token` (único) y se pasa la orden a `PENDIENTE`.

---

## 5. Webhook Servidor a Servidor (`POST /pagos/flow/confirmacion/`)

- `@csrf_exempt`, `@require_POST`, público.
- Recibe `token = request.POST.get('token')`.
- Ejecuta el flujo fuera de transacciones largas:
  1. Recibe token.
  2. Consulta a Flow `payment/getStatus` (HTTP GET con timeout de 5-7s) **fuera de `transaction.atomic()`**.
  3. Valida respuesta (estado, monto, moneda, orden).
  4. Si Flow reporta error transitorio de red: deja la orden en `PENDIENTE` con registro técnico para reconciliación posterior. No marca rechazo bancario definitivo.
  5. Si Flow reporta `status == 2`:
     Abre transacción SQLite corta:
     ```python
     with transaction.atomic():
         rows = OrdenPago.objects.filter(id=orden.id, pro_aplicado=False).update(
             pro_aplicado=True,
             estado=OrdenPago.ESTADO_PAGADA,
             pagada_el=ahora,
             flow_order=flow_order,
             # ...
         )
         if rows == 1:
             # Solo este proceso extiende Pro
             aplicar_extension_pro(orden.usuario, orden.plan)
     ```
  6. Responde HTTP 200 de inmediato.

---

## 6. Retorno de Usuario (`POST /pagos/flow/retorno/` y `GET /pagos/resultado/<order>/`)

Flow redirige mediante `POST application/x-www-form-urlencoded` con `token=<token>`.

### Separación de Responsabilidades:
1. `POST /pagos/flow/retorno/`:
   - `@csrf_exempt`
   - Recibe `token`.
   - Localiza la orden. Si aún está `PENDIENTE`, ejecuta `obtener_estado_pago(token)` como salvaguarda síncrona.
   - Redirige mediante `HttpResponseRedirect` a:
     `GET /pagos/resultado/<commerce_order>/`
2. `GET /pagos/resultado/<commerce_order>/`:
   - Vista protegida para el usuario dueño de la orden.
   - Es una página normal de Fogata que el usuario puede refrescar libremente sin reenvío de formularios.
   - **NUNCA concede Pro desde la petición GET.** Solo lee el estado persistido por el servidor.
   - Muestra las tarjetas oficiales:
     - **Pagado:** 🔥 ¡Ya eres Fogata Pro!
     - **Pendiente:** Estamos confirmando tu pago.
     - **Rechazado:** El pago no pudo completarse.
     - **Anulado:** El pago fue cancelado.

---

## 7. Reconciliación de Pagos (`reconciliar_pagos_flow`)

Comando de gestión:
```bash
python manage.py reconciliar_pagos_flow [--dias=3]
```
- Busca órdenes con `estado = 'PENDIENTE'` que tengan `flow_token` asignado.
- Consulta `payment/getStatus` en Flow.
- Si el pago fue aprobado: ejecuta la reclamación atómica e idempotente (`pro_aplicado=False -> True`) y activa Pro.
- Si fue rechazado o anulado: actualiza los estados oficiales.
- Recupera automáticamente callbacks perdidos, caídas de red o demoras en medios de pago asíncronos.

---

## 8. Privacidad Estricta de Datos Financieros

- **No persistir raw response:** En `OrdenPago.flow_metadata` solo se almacenan claves sanitizadas (`status`, `flowOrder`, `commerceOrder`, `amount`, `currency`).
- **NUNCA persistir:** `payer`, `paymentData` completo, datos de tarjeta, números de cuenta, RUT ni secretos.
- `flow_token` permanece interno en base de datos; nunca se envía a plantillas, eventos ni Control Center visible.
- En la validación de pago: **NO se exige que `payer == user.email`**, permitiendo que un usuario pague legítimamente con una tarjeta o cuenta asociada a otro email.

---

## 9. Métricas y Control Center

- **Métricas comerciales:**
  - `PRO activos totales` (todos los usuarios Pro vigentes, incluidos manuales/staff).
  - `PRO pagados activos` (usuarios que poseen al menos una `OrdenPago` con `estado='PAGADA'` y `ambiente='PRODUCTION'`).
  - Ventas e Ingresos: Calculados **exclusivamente sobre órdenes `PAGADA` en `ambiente='PRODUCTION'`**.
  - Las órdenes de `SANDBOX` y los cambios manuales en admin jamás suman ingresos ni ventas reales.
- **Control Center (`/gestion/pagos/`):**
  - Tabla paginada de órdenes con badge de ambiente (`Sandbox` / `Producción`), filtros por estado y buscador por comercio/orden.

---

## 10. Estrategia de Pruebas

Se amplía la suite de pruebas a más de 35 casos específicos cubriendo:
- Idempotencia con actualización condicional en SQLite (`rows == 1`).
- Dos confirmaciones concurrentes sobre la misma orden.
- Callback con Flow invocado fuera de `transaction.atomic()`.
- Prevención de doble checkout accidental mediante `checkout_request_id`.
- Órdenes Sandbox no computan en ingresos reales.
- Manejo de timeout de red sin marcar pago como rechazado.
- Reconciliación vía management command.
- Retorno vía POST redirigiendo a GET de resultado.
- Verificación de que `flow_metadata` no guarda `payer` ni `paymentData`.
- Interruptor de pagos y validación estricta de credenciales en producción.
