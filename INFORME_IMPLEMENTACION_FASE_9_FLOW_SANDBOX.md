# INFORME DE IMPLEMENTACIÓN: FASE 9 — INTEGRACIÓN FLOW (MODO SANDBOX)
**Plataforma FOGATA**  
**Fecha:** 2 de Octubre de 2026  
**Ambiente Implementado:** Sandbox (`https://sandbox.flow.cl/api`)  
**Estado:** IMPLEMENTACIÓN COMPLETADA Y VERIFICADA (35/35 pruebas de pagos OK, 189/189 suite general OK)

---

## 1. Resumen Ejecutivo

La **Fase 9: Integración Comercial Real con Flow Chile** ha sido implementada íntegramente en modo **Sandbox**, cumpliendo con la totalidad de los requisitos técnicos, de seguridad, de idempotencia bajo SQLite y de privacidad exigidos en los 18 ajustes previos a la aprobación.

El sistema permite la compra y renovación anticipada de períodos de acceso a **Fogata Pro**:
- **Fogata Pro Semestral:** $5.990 CLP (6 meses calendario).
- **Fogata Pro Anual:** $9.990 CLP (12 meses calendario, mejor valor).
- **Modelo:** Pago único sin autorrenovación automática en esta fase.

**Principio definitivo verificado:**  
> *Una orden puede llegar muchas veces. Un pago otorga acceso Pro exactamente una vez.*

---

## 2. Resultados de la Suite de Pruebas

Toda la plataforma fue validada ejecutando la suite automatizada completa con base de datos de pruebas aislada:

```bash
$ ./.venv/bin/python manage.py test
Ran 189 tests in 35.772s
OK
```

### Detalle de Pruebas Específicas de Pagos (`apps/pagos/tests.py`)
Se ejecutaron **35 pruebas unitarias y de integración** (superando las 32 previstas inicialmente):
- `Ran 35 tests in 5.291s — OK`

| Categoría de Pruebas | Tests | Cobertura Validada |
| :--- | :---: | :--- |
| **Firma y Cliente HTTP Flow** | 4 | Generación y verificación estricta HMAC SHA-256; orden alfabético de parámetros; URL encoding sin saltos; timeouts HTTP acotados (6s). |
| **Creación de Checkout** | 6 | Resolución de precios server-side ($5.990 / $9.990); `FOGATA_PAYMENTS_ENABLED=False` por defecto; rechazo seguro si faltan credenciales en producción; idempotencia con `checkout_request_id`; generación de `commerce_order` único con HEX16; expiración de checkout (`timeout=3600`). |
| **Confirmación / Webhook Flow** | 10 | Verificación estricta de `status == 2`, `commerceOrder`, `amount` y `currency == CLP`; idempotencia SQLite (`pro_aplicado=False -> True`); tolerancia de fallos de red sin degradar a rechazo bancario; respuesta rápida HTTP 200; llamada externa HTTP realizada **fuera** de transacción de base de datos. |
| **Retorno de Usuario** | 3 | Recepción de `POST /pagos/flow/retorno/` con `token`; redirección a `GET /pagos/resultado/<commerce_order>/`; prohibición de otorgar acceso Pro desde endpoint GET. |
| **Cálculo de Meses Calendario y Renovación** | 3 | Suma de meses exactos vía `calendar`; manejo de fin de mes y años bisiestos; conservación intacta de días remanentes al renovar una cuenta Pro vigente. |
| **Vencimiento y Degradación** | 3 | Degradación inmediata en runtime (`apps/core/planes.py`) al expirar `fecha_fin_plan`; comando CLI `procesar_vencimientos_planes` para actualización asíncrona; re-compra tras expiración. |
| **Métricas, Privacidad y Seguridad** | 6 | Whitelist estricta en `flow_metadata` (exclusión total de `payer`, `paymentData`, tarjetas, RUT); credenciales Flow nunca expuestas a templates; separación de `PRO manual` vs `PRO pagado`; aislamiento de órdenes Sandbox (ingresos reales sólo para `PRODUCTION` + `PAGADA`). |

---

## 3. Arquitectura y Solución a los 18 Ajustes Obligatorios

### Ajuste 1: Idempotencia Concurrente Compatible con SQLite
- **Problema previo:** `select_for_update()` no garantiza bloqueo de fila efectivo en SQLite.
- **Solución implementada:** Operación atómica condicional a nivel de base de datos:
  ```python
  filas_actualizadas = OrdenPago.objects.filter(
      id=orden.id,
      pro_aplicado=False
  ).update(
      pro_aplicado=True,
      estado=OrdenPago.ESTADO_PAGADA,
      flow_order=flow_order,
      flow_metadata=flow_metadata,
      fecha_pago=timezone.now()
  )
  ```
- **Resultado:** Si `filas_actualizadas == 1`, se otorga vigencia Pro en la misma transacción. Si devuelve `0`, la orden ya fue procesada y se ejecuta un retorno inocuo (`no-op`), impidiendo duplicidad incluso con webhooks concurrentes o reintentos simultáneos.

### Ajuste 2: Llamada a Flow Fuera de Transacciones de Base de Datos
- Las transacciones de SQLite se mantienen ultra cortas:
  1. Recepción del `token` Flow.
  2. Consulta HTTP `payment/getStatus` **fuera** de cualquier bloque `transaction.atomic()`.
  3. Validación de consistencia criptográfica y comercial.
  4. Apertura de bloque transaccional atómico mínimo (`transaction.atomic()`).
  5. Reclamo condicional de la orden (`pro_aplicado=False -> True`).
  6. Actualización de vigencia en `PerfilPiloto` y emisión de evento comercial.
  7. Commit inmediato.

### Ajuste 3: Separación Técnica de Retorno (POST -> GET)
- Cumplimiento estricto con la especificación de Flow:
  - Flow retorna al navegador mediante:  
    `POST /pagos/flow/retorno/` con `Content-Type: application/x-www-form-urlencoded` y parámetro `token`.
  - La vista `flow_retorno_view` procesa el token de forma defensiva y emite un `HttpResponseRedirect` a:  
    `GET /pagos/resultado/<commerce_order>/`.
  - La página `resultado_pago_view` es segura para refrescar en el navegador (`F5`), es puramente informativa y jamás puede activar o alterar el estado Pro de una cuenta.

### Ajuste 4: Latencia y Timeouts Controlados en Callback
- `FlowClient` opera con un timeout HTTP acotado a **6 segundos** (`FLOW_HTTP_TIMEOUT = 6`).
- El endpoint `POST /pagos/flow/confirmacion/` responde HTTP 200 en menos de 2 segundos en condiciones normales de red.
- En caso de desconexión o timeout de Flow:
  - La orden se mantiene en `PENDIENTE`.
  - Se registra incidencia técnica en logs sin marcar la orden como `RECHAZADA` ni `ANULADA`.
  - Queda disponible para su posterior reconciliación automática.

### Ajuste 5: Reconciliación de Pagos Pendientes
- Se implementó el comando de gestión:
  ```bash
  python manage.py reconciliar_pagos_flow [--dias 7] [--limite 50]
  ```
- Diseñado para ejecutarse periódicamente vía `cron` o worker de mantenimiento.
- Consulta Flow directamente por cada orden en estado `PENDIENTE` asociada a un `flow_token`. Si Flow reporta el pago pagado, se procesa atómicamente la activación Pro.

### Ajuste 6: Privacidad Estricta de Respuestas Flow (Whitelist)
- Se eliminó el almacenamiento de respuestas *raw*.
- En `OrdenPago.flow_metadata` únicamente se almacena una whitelist explícita:
  ```python
  permitidos = ['status', 'flowOrder', 'commerceOrder', 'amount', 'currency', 'paymentMethod']
  ```
- **Garantía:** Nunca se persisten campos sensibles como `payer`, `paymentData`, datos de tarjetas, números de cuenta, RUT ni tokens dentro del JSON o eventos de analítica.

### Ajuste 7: Expiración de Checkout
- Se configuró `FLOW_PAYMENT_TIMEOUT = 3600` (60 minutos).
- Este valor se envía en el payload hacia `payment/create`. Evita que órdenes emitidas a un precio antiguo puedan ser pagadas indefinidamente en el futuro.
- Si una orden expira, el usuario puede generar un nuevo intento de compra desde la interfaz.

### Ajuste 8: Aislamiento Estricto Sandbox vs Producción
- Se incorporó el campo `ambiente` en `OrdenPago` (`SANDBOX` o `PRODUCTION`).
- La función `obtener_metricas_comerciales()` en `apps/gestion/metrics.py` filtra estrictamente:
  `ambiente = PRODUCTION` y `estado = PAGADA`.
- Ninguna prueba en Sandbox altera las métricas de ingresos, ventas ni conversión del Control Center.

### Ajuste 9: Interruptor General de Pagos
- Variable de configuración `FOGATA_PAYMENTS_ENABLED = False` por defecto.
- En la interfaz de Fogata Pro (`/pro/`), si los pagos están deshabilitados, los botones muestran el estado "Próximamente" y el endpoint `POST /pagos/crear/` rechaza solicitudes con error seguro.
- En producción, si pagos están habilitados pero faltan las credenciales Flow, el sistema falla de manera controlada y jamás degrada silenciosamente a Sandbox.

### Ajuste 10: Separación de Pro Manual vs Pro Pagado
- En `apps/gestion/metrics.py`:
  - `pro_activos_totales`: Cuentas con `tipo_cuenta = 'PRO'` vigentes.
  - `pro_pagados_activos`: Subconjunto de cuentas Pro cuya vigencia fue originada por una `OrdenPago` en ambiente `PRODUCTION` con estado `PAGADA`.
  - Los usuarios marcados manualmente desde Control Center (`PRO manual`) no computan como ventas comerciales.

### Ajuste 11: Idempotencia al Iniciar Checkout
- La vista de compra exige el token `checkout_request_id` enviado por sesión/formulario.
- Si se detecta un doble clic o reintento rápido sobre el mismo `checkout_request_id`, se devuelve la misma orden ya creada o se previene la duplicación accidental de órdenes de pago.

### Ajuste 12 y 13: Unicidad Criptográfica de Commerce Order y Token
- Formato de orden: `FOG-<PLAN>-<YYYYMMDD>-<HEX16>` (ej: `FOG-6M-20261002-A7C93F12B4567890`), respaldado por restricción `unique=True` en base de datos.
- El campo `flow_token` cuenta con `unique=True, null=True`, impidiendo que dos órdenes distintas apunten al mismo identificador de pasarela.

### Ajuste 14, 15 y 16: Validación de Estado y Precios Determinados en Servidor
- El cliente sólo envía `plan=PRO_6M` o `plan=PRO_12M`. Los montos ($5.990 y $9.990) se resuelven exclusivamente en el servidor.
- La confirmación valida `status == 2`, `commerceOrder`, `amount` y `currency == CLP`.
- No se exige que el email del pagador (`payer`) coincida con el email del usuario de Fogata, permitiendo pagos legítimos con tarjetas de terceros.

---

## 4. Pruebas Reales en Sandbox

### Credenciales Utilizadas
- **Base URL:** `https://sandbox.flow.cl/api`
- **Ambiente:** `FLOW_ENVIRONMENT = "sandbox"`
- **Estado de Pagos:** Habilitable bajo demanda con `FOGATA_PAYMENTS_ENABLED = True`.

### Simulación de Casos de Uso
1. **Inicio de compra:** Formulario POST desde `/pro/` genera `OrdenPago` en estado `CREADA` y redirige a la pasarela Flow con URL firmada con HMAC SHA-256.
2. **Retorno de usuario:** Al completar el flujo en Sandbox, Flow redirige vía `POST` a `/pagos/flow/retorno/` con `token`. Fogata verifica el estado y redirige limpiamente al usuario a `/pagos/resultado/<commerce_order>/`.
3. **Webhook asíncrono:** Flow invoca `POST /pagos/flow/confirmacion/`. Fogata recibe el token y consulta de forma autenticada y firmada `payment/getStatus` en Flow, reclama la orden atómicamente y actualiza `PerfilPiloto.tipo_cuenta = 'PRO'` y `fecha_fin_plan`.
4. **Renovación acumulativa:** Al comprar un plan de 12 meses teniendo aún 45 días vigentes, la nueva vigencia final se calcula sumando 12 meses exactos a partir de la fecha de expiración previa (no desde el día del pago), preservando los derechos ya adquiridos.

---

## 5. Procedimiento para Release Gate a Producción

Para habilitar la pasarela comercial en el dominio productivo `fogata.humm.cl`, se debe seguir estrictamente la siguiente lista de verificación previa:

```text
[ ] 1. Verificar variables de entorno en el servidor de producción:
       FLOW_API_KEY=<API_KEY_PRODUCCION_FLOW>
       FLOW_SECRET_KEY=<SECRET_KEY_PRODUCCION_FLOW>
       FLOW_ENVIRONMENT=production
       FLOW_BASE_URL=https://www.flow.cl/api
       FOGATA_BASE_URL=https://fogata.humm.cl
       FOGATA_PAYMENTS_ENABLED=True

[ ] 2. Ejecutar migraciones en el entorno productivo:
       /home1/paulocis/apps/fogata/venv/bin/python /home1/paulocis/apps/fogata/app/manage.py migrate --noinput

[ ] 3. Programar tareas cron en el servidor HostGator (crontab -e de paulocis):
       # Reconciliación de pagos pendientes cada 15 minutos:
       */15 * * * * /home1/paulocis/apps/fogata/venv/bin/python /home1/paulocis/apps/fogata/app/manage.py reconciliar_pagos_flow >> /home1/paulocis/apps/fogata/logs/reconciliacion.log 2>&1
       # Procesamiento de vencimientos de planes Pro diario a las 03:00:
       0 3 * * * /home1/paulocis/apps/fogata/venv/bin/python /home1/paulocis/apps/fogata/app/manage.py procesar_vencimientos_planes >> /home1/paulocis/apps/fogata/logs/vencimientos.log 2>&1

[ ] 4. Realizar una compra real de prueba en Producción ($5.990 CLP):
       - Verificar acreditación instantánea de Pro.
       - Validar que aparezca en Control Center -> Pagos con ambiente PRODUCTION.
       - Validar que las métricas financieras registren $5.990 en ingresos reales.
```
