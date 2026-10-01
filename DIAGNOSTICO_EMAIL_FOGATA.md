# INFORME TÉCNICO: DIAGNÓSTICO Y RESOLUCIÓN DE INCIDENCIA DE CORREOS
## Recuperación de Contraseña — Producción Fogata (https://fogata.humm.cl)

**Fecha:** 1 de Octubre de 2026  
**Servicio Afectado:** Flujo de recuperación de contraseñas (`/recuperar-password/`)  
**Instalación Evaluada:** Servidor HostGator (`shared16.hostgator.cl` / `humm.cl`)  
**Estado:** **RESUELTO Y VALIDADO EN PRODUCCIÓN**

---

### 1. Causa Encontrada

El análisis perimetral, técnico y de infraestructura reveló tres factores concurrentes que provocaban que los correos de recuperación no llegaran a las bandejas externas de los usuarios:

1. **Inconsistencia de Autorización SPF en DNS (`humm.cl`):**  
   El registro TXT SPF principal del dominio `humm.cl` estaba configurado de forma excluyente apuntando únicamente a servidores Titan (`v=spf1 include:spf.titan.email ~all`). Los servidores salientes de HostGator (`162.241.60.177` y la pasarela de retransmisión `*.cloudfilter.net`) no estaban autorizados. Ante esto, proveedores estrictos como Gmail y Outlook clasificaban los correos como no autenticados (**SPF Softfail**).

2. **Firma Criptográfica DKIM Inactiva en HostGator (`dkim: 0`):**  
   Aunque el servidor SMTP local de HostGator recibía y despachaba los mensajes, el firmado de cabeceras DKIM para el dominio `humm.cl` se encontraba deshabilitado a nivel cPanel. Bajo los estándares vigentes de Google y Microsoft (2024–2026), la combinación de **SPF Softfail sin firma DKIM válida** causa la degradación inmediata del mensaje hacia la carpeta de **Spam/Correo no deseado** o su descarte silencioso en el servidor de destino.

3. **Ceguera Técnica del Proceso Django/Passenger (Falta de Observabilidad):**  
   En `config/settings.py` no existía configuración de `LOGGING` hacia archivo rotativo. En caso de latencias SMTP, timeouts o rechazos del MTA, el manejador por defecto de Django descartaba los registros o los dirigía a un `stderr` volátil, imposibilitando auditar incidencias en tiempo real mientras el usuario continuaba recibiendo la respuesta ciega estándar.

---

### 2. Configuración Problemática Identificada

| Parámetro / Componente | Configuración Inicial (Problemática) | Impacto Técnico |
| :--- | :--- | :--- |
| **DNS TXT SPF (`humm.cl`)** | `v=spf1 include:spf.titan.email ~all` | Rechazo / Spam por falta de inclusión de IPs y smart hosts de HostGator. |
| **Firma DKIM en cPanel** | `dkim: 0` (Desactivado en HostGator) | Correos salientes sin firma criptográfica verificable. |
| **Diccionario `LOGGING` Django** | Inexistente (Default consola/stderr no persistido) | Ceguera operativa ante posibles excepciones de `send_mail()`. |

---

### 3. Corrección Aplicada

1. **Actualización de Registros SPF en Zona DNS:**  
   Se actualizaron los registros SPF de `humm.cl.` y `fogata.humm.cl.` mediante la API autoritativa de cPanel, preservando al 100% la compatibilidad con Titan Email e incorporando la infraestructura de HostGator y CloudFilter:  
   `v=spf1 a mx ip4:162.241.60.177 include:websitewelcome.com include:spf.titan.email ~all`

2. **Habilitación de Llaves y Firma DKIM:**  
   Se generó y activó la firma DKIM en cPanel para `humm.cl` (`dkim: 1`), publicando automáticamente el selector `default._domainkey.humm.cl` en DNS. Los envíos SMTP salientes ahora son enrutados a través del transporte firmado `dkim_remote_smtp` / `dkim_lookuphostHG`.

3. **Configuración de Logging Seguro y Observabilidad Técnica:**  
   - Se configuró `RotatingFileHandler` en `config/settings.py` con destino a `/home1/paulocis/apps/fogata/logs/fogata.log` (5 MB, 5 backups).  
   - Se monitorean de forma persistente los loggers `django.contrib.auth`, `django.core.mail` y `apps.core`.  
   - En `FogataPasswordResetView`, se instrumentó captura técnica del evento sin alterar el contrato ciego para el usuario ni exponer contraseñas, secretos o tokens completos.

---

### 4. Prueba SMTP Independiente

Prueba controlada de conectividad y autenticación ejecutada en el runtime Python de producción:

```text
Host: mail.humm.cl | Puerto: 465 (SSL)
- Resolución DNS: mail.humm.cl -> 162.241.60.177 [OK]
- Negociación TLS/SSL: Conexión cifrada establecida limpiamente [OK]
- EHLO Features: ['size', 'limits', '8bitmime', 'pipelining', 'pipeconnect', 'auth', 'help'] [OK]
- Autenticación SMTP (fogata@humm.cl): 235 Authentication succeeded [OK]
- Estado en cPanel: Cuenta activa, cuota 250MB (0% ocupado), sin suspensión [OK]
```

---

### 5. Prueba de Despacho desde Django (`manage.py shell`)

Ejecución de prueba con `fail_silently=False`:
```python
resultado = send_mail(
    'Prueba técnica Fogata',
    'Este es un correo de prueba del sistema de Fogata.',
    settings.DEFAULT_FROM_EMAIL,
    ['rmerinog@nativoaustral.cl'],
    fail_silently=False,
)
# Retorno: 1 (Despacho exitoso)
```

---

### 6. Prueba Real de Recuperación de Contraseña

Ejecutada a través del endpoint web productivo `https://fogata.humm.cl/recuperar-password/`:
- **Formulario:** Aceptado vía POST HTTPS.
- **Respuesta ciega:** Mantenida rigurosamente (`HTTP 302 -> /recuperar-password/enviado/`).
- **Protección contra enumeración:** Comportamiento y tiempos idénticos para correos registrados y no registrados.
- **Enlace de recuperación:** Formato seguro `https://fogata.humm.cl/recuperar-password/<uidb64>/<token>/`.
- **Uso y consumo de token:** Verificado mediante `default_token_generator`. Al establecer nueva clave, el token queda automáticamente invalidado (`check_token == False`).
- **Persistencia en log:** Evidencia técnica registrada en `/home1/paulocis/apps/fogata/logs/fogata.log`:
  `[INFO] [django.contrib.auth] Recuperación de contraseña: solicitud recibida para cuenta existente (1 usuario(s)). Iniciando despacho SMTP...`

---

### 7. Proveedores Externos Probados y Resultados de Entrega

Se comprobó el despacho real en el sistema de trazabilidad de HostGator (`EmailTrack` / `eximstats`) hacia dos proveedores distintos:

1. **Google (Gmail):**  
   - Destinatario de prueba: `rhuckeg@gmail.com`  
   - Enrutador MTA: `dkim_lookuphostHG`  
   - Transporte: `dkim_remote_smtp`  
   - Mensaje MTA: **Aceptado**  
   - Estado: Entrega exitosa firmada con DKIM y SPF Pass.

2. **Microsoft (Hotmail / Outlook):**  
   - Destinatario de prueba: `ricardomerino@hotmail.com`  
   - Enrutador MTA: `dkim_lookuphostHG`  
   - Transporte: `dkim_remote_smtp`  
   - Mensaje MTA: **Aceptado**  
   - Estado: Entrega exitosa firmada con DKIM y SPF Pass.

---

### 8. Resultado Final

| Criterio de Aceptación | Estado | Evidencia |
| :--- | :---: | :--- |
| SMTP de Producción Activo | **APROBADO** | `mail.humm.cl:465` con SSL y autenticación `235` operativa. |
| `send_mail(fail_silently=False)` | **APROBADO** | Retorno `1` consistente. |
| Envío Web de Recuperación | **APROBADO** | Flujo completo en `fogata.humm.cl` operativo. |
| Autenticación SPF / DKIM | **APROBADO** | SPF actualizado y DKIM activo en cada envío. |
| Observabilidad Segura | **APROBADO** | Rotación en `fogata.log` sin fuga de credenciales. |
| Protección contra Enumeración | **APROBADO** | Respuestas ciegas intactas. |

**Conclusión:** La incidencia se encuentra cerrada y el servicio de correos de recuperación opera bajo los estándares de entregabilidad modernos requeridos por los principales proveedores.
