# FOGATA — RELEASE GATE FINAL FLOW ANTES DE PRODUCCIÓN
**Fecha:** 2 de Octubre de 2026  
**Ambiente Verificado:** Sandbox (`https://sandbox.flow.cl/api`) en producción HTTPS (`https://fogata.humm.cl`)  
**Servidor:** HostGator (`shared16.hostgator.cl` / `humm.cl`)  
**Estado:** **TODAS LAS PRUEBAS APROBADAS (12/12 PASS)**

---

## 1. Matriz de Resultados del Release Gate

| Ítem de Validación | Estado | Evidencia Técnica Observada |
| :--- | :---: | :--- |
| **Payment Create real Sandbox** | **PASS** | Creación exitosa en `sandbox.flow.cl/api/payment/create`. Orden: `FOG-6M-20261002-E264DC1521794B14`, Flow Order: `10808543`, Monto: $5.990 CLP, Estado: `PENDIENTE`. |
| **Checkout Sandbox** | **PASS** | Sesión de pago aprovisionada y cargada en pasarela Flow: `https://sandbox.flow.cl/app/web/pay.php`. |
| **urlConfirmation pública** | **PASS** | Callback servidor a servidor invocado por Flow desde Internet recibido con éxito en `https://fogata.humm.cl/pagos/flow/confirmacion/` vía HTTPS TLS 1.3 / HTTP/2. |
| **payment/getStatus real** | **PASS** | Consulta autenticada y firmada con HMAC SHA-256 hacia `https://sandbox.flow.cl/api/payment/getStatus`. Retorno verificado: `status: 2` (Pagada), `amount: 5990`, `currency: CLP`. |
| **status 2 activa PRO** | **PASS** | Cuenta de prueba (`test_sandbox_flow@fogata.cl`) actualizada a `tipo_cuenta = 'PRO'`. Vigencia asignada por 6 meses calendario exactos: del `02/10/2026 21:48` al `02/04/2027 21:48`. |
| **urlReturn POST** | **PASS** | Retorno del navegador procesado mediante `POST /pagos/flow/retorno/` con parámetro `token`. Respuesta: HTTP 302 hacia `/pagos/resultado/FOG-6M-20261002-E264DC1521794B14/`. |
| **resultado GET** | **PASS** | Vista informativa GET `/pagos/resultado/<commerce_order>/` responde HTTP 200 con confirmación de activación Pro. No concede permisos en recarga. |
| **callback duplicado idempotente** | **PASS** | Reprocesamiento del mismo token ejecutado en base de datos. Operación condicional atómica detecta `pro_aplicado=True`, retorna `no-op` y mantiene `fecha_fin_plan` idéntica al microsegundo. Cero extensiones duplicadas. |
| **reconciliación** | **PASS** | `python manage.py reconciliar_pagos_flow` ejecutado en HostGator. Consultó y mantuvo orden pendiente `FOG-6M-20261002-1A4055C5B8A8243C` de forma limpia y sin errores. |
| **métricas Sandbox excluidas de ingresos** | **PASS** | `obtener_metricas_comerciales()` en Control Center registra: `ingresos_totales_clp: $0`, `ventas_totales_pagadas: 0`, `pro_pagados_activos: 0`. Órdenes `SANDBOX` quedan 100% aisladas de la contabilidad real. |
| **cron ejecutado manualmente** | **PASS** | Comandos `reconciliar_pagos_flow` y `procesar_vencimientos_planes` ejecutados manualmente en HostGator con rutas absolutas `/home1/paulocis/...` completando con código de salida 0. |
| **suite completa** | **PASS** | Suite automatizada general ejecutada: **189 de 189 pruebas pasando al 100% OK** (`Ran 189 tests in 36.800s`). |

---

## 2. Evidencia de Ejecución Extremo a Extremo en Servidor

### A. Registro en Logs de Producción (`/home1/paulocis/apps/fogata/logs/fogata.log`)
```text
[2026-10-02 18:48:19] INFO [apps.pagos.services] Pago confirmado exitosamente para orden FOG-6M-20261002-E264DC1521794B14 (Usuario: test_sandbox_flow@fogata.cl). Pro vigente hasta 2027-04-02 21:48:19.359202+00:00.
[2026-10-02 18:48:19] INFO [apps.pagos.views] Confirmación procesada exitosamente para orden FOG-6M-20261002-E264DC1521794B14 (Estado: PAGADA).
```

### B. Medición de Tiempos Reales de Callback
- **Latencia de consulta Flow `payment/getStatus`:** `0.605 segundos`.
- **Tiempo total de respuesta del webhook:** `< 1.0 segundo`.
- **Margen de seguridad:** Ampliamente inferior al límite estricto de 15 segundos requerido por Flow.

### C. Prueba de Idempotencia ante Reintentos
- **Fecha fin antes del reprocesamiento:** `2027-04-02 21:48:19.359202+00:00`
- **Fecha fin después del reprocesamiento:** `2027-04-02 21:48:19.359202+00:00`
- **Registro en log:** `INFO: Orden FOG-6M-20261002-E264DC1521794B14 ya fue procesada y aplicada previamente. Retornando no-op.`

### D. Aislamiento Contable en Control Center
- `ingresos_totales_clp`: `$0` (o `None`)
- `ventas_totales_pagadas`: `0`
- `pro_activos_totales`: `1` (Cuenta de prueba Sandbox)
- `pro_pagados_activos`: `0` (Cero ventas comerciales reales contabilizadas)

### E. Rutas Reales de HostGator para Crontab
Las tareas de mantenimiento en segundo plano han sido verificadas con las rutas absolutas del entorno HostGator:
```cron
# Reconciliación de pagos pendientes (cada 15 minutos):
*/15 * * * * /home1/paulocis/apps/fogata/venv/bin/python /home1/paulocis/apps/fogata/app/manage.py reconciliar_pagos_flow >> /home1/paulocis/apps/fogata/logs/reconciliacion.log 2>&1

# Procesamiento diario de vencimientos Pro (03:00 AM):
0 3 * * * /home1/paulocis/apps/fogata/venv/bin/python /home1/paulocis/apps/fogata/app/manage.py procesar_vencimientos_planes >> /home1/paulocis/apps/fogata/logs/vencimientos.log 2>&1
```

---

## 3. Estado de Protección y Próximos Pasos

En cumplimiento estricto del protocolo de seguridad:
- Las credenciales de Producción **NO** han sido configuradas.
- La plataforma continúa con `FLOW_ENVIRONMENT=sandbox`.
- Los cobros reales permanecen inactivos para usuarios generales.
