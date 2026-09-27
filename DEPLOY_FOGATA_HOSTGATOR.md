# INFORME DE DESPLIEGUE SEGURO EN HOSTGATOR
## fogata.humm.cl — Piloto Multiusuario

**Fecha de Ejecución:** Septiembre 2026  
**Servidor:** HostGator (shared16 / humm.cl)  
**Dominio Objetivo:** [https://fogata.humm.cl](https://fogata.humm.cl)  
**Estado General:** **DESPLIEGUE EXITOSO — APROBADO PARA PILOTO EXTERNO**  

---

## 1. Arquitectura de Aislamiento en el Servidor

Siguiendo el estándar de seguridad y los patrones de las plataformas Humm existentes, el código, el entorno virtual, la base de datos persistente y los secretos se ubicaron **estrictamente fuera** del árbol web público (`public_html`):

```text
/home1/paulocis/
│
├── apps/
│   └── fogata/
│       ├── app/                          <- Código fuente Django (rsync limpio, sin git)
│       │   ├── apps/
│       │   ├── config/
│       │   ├── templates/
│       │   ├── static/
│       │   ├── staticfiles/              <- Salida de collectstatic (138 archivos)
│       │   ├── manage.py
│       │   └── requirements.txt
│       │
│       ├── venv/                         <- Entorno virtual dedicado Python 3.12.14 (uv)
│       ├── var/
│       │   └── db.sqlite3                <- Base de datos persistente (chmod 600, permisos 700)
│       ├── logs/                         <- Directorio de logs de ejecución (chmod 700)
│       └── secrets/
│           ├── .env                      <- Variables de entorno de producción (chmod 600)
│           └── admin_creds.txt           <- Credenciales del superusuario (chmod 600)
│
├── fogata.humm.cl/                       <- Document Root público exclusivo del subdominio
│   ├── .htaccess                         <- Reglas Apache, forzado HTTPS y bloqueo perimetral
│   ├── passenger_wsgi.py                 <- Punto de entrada Phusion Passenger WSGI
│   ├── static -> /home1/paulocis/apps/fogata/app/staticfiles
│   └── tmp/
│       └── restart.txt                   <- Control de recarga de Passenger (bloqueado vía HTTP)
│
└── public_html/                          <- Sitio principal Humm (TOTALMENTE INTACTO)
```

---

## 2. Parámetros Técnicos del Entorno

| Componente | Configuración de Producción | Estado |
| :--- | :--- | :---: |
| **Subdominio** | `fogata.humm.cl` (y alias `www.fogata.humm.cl`) | **CONFIGURADO** |
| **DNS Autoritativo** | Registro A apuntando a `162.241.60.177` (ns16/ns17.hostgator.cl) | **ACTIVO** |
| **Document Root** | `/home1/paulocis/fogata.humm.cl` | **CONFIGURADO** |
| **Directorio de Código** | `/home1/paulocis/apps/fogata/app` | **CONFIGURADO** |
| **Versión Python** | CPython 3.12.14 | **VERIFICADO** |
| **Entorno Virtual** | `/home1/paulocis/apps/fogata/venv` | **AISLADO** |
| **Mecanismo WSGI** | Phusion Passenger vía `passenger_wsgi.py` | **OPERATIVO** |
| **Servidor Web** | Apache 2.4 con soporte HTTP/2 | **OPERATIVO** |
| **Certificado SSL** | Let's Encrypt Wildcard (`*.humm.cl`), TLS 1.3 | **VÁLIDO Y ACTIVO** |
| **Redirección HTTPS** | HTTP 301 permanente obligatorio en `.htaccess` | **FORZADO** |
| **Base de Datos** | SQLite persistente en `/home1/paulocis/apps/fogata/var/db.sqlite3` | **CONFIGURADO (600)** |
| **Migraciones** | 26 migraciones aplicadas (`auth`, `admin`, `canciones`, `core`, `fogatas`, etc.) | **APLICADAS (100%)** |
| **Archivos Estáticos** | `collectstatic`: 138 archivos procesados en `staticfiles/` | **CONFIGURADO** |
| **Service Worker** | `/sw.js` servido con scope `/`, MIME `application/javascript`, no cachea HTML | **OPERATIVO** |
| **Web App Manifest** | `/manifest.webmanifest` con MIME `application/manifest+json` | **OPERATIVO** |

---

## 3. Matriz de Variables de Entorno y Secretos

> **Principio de Confidencialidad:**  
> Ningún secreto ni credencial real es divulgado en este informe. Todos los valores residen exclusivamente en `/home1/paulocis/apps/fogata/secrets/.env` con permisos `chmod 600`.

| Variable | Descripción | Estado de Configuración |
| :--- | :--- | :---: |
| `DJANGO_DEBUG` | Modo depuración desactivado en producción (`False`) | **CONFIGURADO** |
| `DJANGO_SECRET_KEY` | Clave criptográfica única e independiente para Fogata (50+ bytes aleatorios) | **CONFIGURADO** |
| `DJANGO_ALLOWED_HOSTS` | Restringido exclusivamente a `fogata.humm.cl,www.fogata.humm.cl` | **CONFIGURADO** |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Restringido a `https://fogata.humm.cl,https://www.fogata.humm.cl` | **CONFIGURADO** |
| `DJANGO_DB_PATH` | Ruta absoluta a `/home1/paulocis/apps/fogata/var/db.sqlite3` | **CONFIGURADO** |
| `DJANGO_EMAIL_BACKEND` | Backend SMTP estándar (`django.core.mail.backends.smtp.EmailBackend`) | **CONFIGURADO** |
| `EMAIL_HOST` | Servidor de correo HostGator (`mail.humm.cl`) | **CONFIGURADO** |
| `EMAIL_PORT` | Puerto SSL seguro (465) | **CONFIGURADO** |
| `EMAIL_USE_SSL` | Cifrado SSL nativo obligatorio (`True`) | **CONFIGURADO** |
| `EMAIL_HOST_USER` | Cuenta de correo dedicada creada en cPanel (`fogata@humm.cl`) | **CONFIGURADO** |
| `EMAIL_HOST_PASSWORD` | Contraseña aleatoria independiente para SMTP | **CONFIGURADO** |
| `DEFAULT_FROM_EMAIL` | Remitente visible `Fogata <fogata@humm.cl>` | **CONFIGURADO** |

---

## 4. Auditoría Perimetral y Seguridad de Exposición (Smoke Tests)

Se realizaron pruebas adversariales externas directas por HTTP/HTTPS probing desde el exterior contra `fogata.humm.cl`:

| Recurso Probadol | Código Esperado | Código Obtenido | Leak Check | Veredicto |
| :--- | :---: | :---: | :---: | :---: |
| `GET /` (Landing pública) | 200 | **200 OK** | CLEAN | **PASS** |
| `GET /login/` | 200 | **200 OK** | CLEAN | **PASS** |
| `GET /registro/` | 200 | **200 OK** | CLEAN | **PASS** |
| `GET /manifest.webmanifest` | 200 | **200 OK** | CLEAN | **PASS** |
| `GET /sw.js` | 200 | **200 OK** | CLEAN | **PASS** |
| `GET /static/css/fogata.css` | 200 | **200 OK** | CLEAN | **PASS** |
| `GET /static/icons/icon-192.png` | 200 | **200 OK** | CLEAN | **PASS** |
| `GET /.env` | 403 / 404 | **403 Forbidden** | CLEAN | **PASS** |
| `GET /.env.production` | 403 / 404 | **403 Forbidden** | CLEAN | **PASS** |
| `GET /.git` | 403 / 404 | **403 Forbidden** | CLEAN | **PASS** |
| `GET /.git/config` | 403 / 404 | **403 Forbidden** | CLEAN | **PASS** |
| `GET /db.sqlite3` | 403 / 404 | **403 Forbidden** | CLEAN | **PASS** |
| `GET /var/db.sqlite3` | 403 / 404 | **403 Forbidden** | CLEAN | **PASS** |
| `GET /secrets/` | 403 / 404 | **404 Not Found** | CLEAN | **PASS** |
| `GET /logs/` | 403 / 404 | **404 Not Found** | CLEAN | **PASS** |
| `GET /manage.py` | 403 / 404 | **403 Forbidden** | CLEAN | **PASS** |
| `GET /settings.py` | 403 / 404 | **403 Forbidden** | CLEAN | **PASS** |
| `GET /debug/` (Ruta inexistente) | 404 | **404 Not Found** | CLEAN (Sin traceback) | **PASS** |
| `GET /tmp/restart.txt` | 403 / 404 | **403 Forbidden** | CLEAN | **PASS** |

---

## 5. Validación del Flujo Real de Usuario en Producción

Se ejecutó la prueba de ciclo de vida completo de un usuario nuevo mediante peticiones HTTPS de navegador sobre el servidor real:

1. **Landing:** Carga inicial rápida en `/` (HTTP 200).
2. **Invitación:** Consumo de cupo desde la base de datos de producción mediante código aleatorio.
3. **Registro:** Creación de cuenta, normalización de correo y autenticación automática.
4. **Primera Canción ("Guardar y Tocar"):** Carga de acordes bracket `[Sol]`, guardado instantáneo y redirección directa al atril (`/canciones/<id>/tocar/`).
5. **Crear Fogata:** Creación de setlist propio e incorporación de la canción con nota de interpretación.
6. **Modo Tocar Fogata:** Ejecución continua de repertorio en pantalla única (`/fogatas/<id>/tocar/?pos=1`).
7. **Compartir Sesión:** Generación de enlace temporal criptográficamente seguro (`/s/<token>/`).
8. **Navegador Incógnito (Invitado Anónimo):** Visualización en modo solo lectura de la Fogata y de la letra de la canción sin acordes ni botones de músico, con cabeceras `Cache-Control: no-store, private` y `X-Robots-Tag: noindex, nofollow`.
9. **Logout y Re-login:** Salida segura por POST y posterior inicio de sesión con correo en mayúsculas, recuperando la biblioteca intacta.
10. **Recuperación de Contraseña por Correo:** Envío real de token de recuperación a través de `mail.humm.cl:465` (SSL) completado con entrega verificada.

---

## 6. Integridad de Otras Plataformas Humm

Se verificó el estado operacional de todas las plataformas hermanas alojadas en el mismo servidor:
- **`fondos.humm.cl`:** HTTP 200 (Operacional)
- **`control.humm.cl`:** HTTP 302 (Operacional, redirigiendo a login)
- **`reloop.humm.cl`:** HTTP 200 (Operacional)
- **`humm.cl` (Sitio principal):** Totalmente preservado y sin modificaciones.

---

## 7. Protocolo de Rollback y Mantenimiento

En caso de requerirse desactivar o revertir Fogata sin afectar ningún otro servicio:

1. **Desactivación Inmediata del Servicio:**
   ```bash
   # Renombrar temporalmente el despachador en el Document Root
   mv /home1/paulocis/fogata.humm.cl/passenger_wsgi.py /home1/paulocis/fogata.humm.cl/passenger_wsgi.py.disabled
   touch /home1/paulocis/fogata.humm.cl/tmp/restart.txt
   ```
2. **Reversión de Subdominio (si fuera necesario):**
   ```bash
   cpapi2 SubDomain delsubdomain domain=fogata.humm.cl
   ```
3. **Preservación de Datos:**
   La base de datos SQLite en `/home1/paulocis/apps/fogata/var/db.sqlite3` y las credenciales en `/home1/paulocis/apps/fogata/secrets/` son independientes y persistentes. Un rollback del código o la web nunca borra la base ni los datos de los usuarios.
4. **Futuros Despliegues de Código:**
   Utilizar siempre `.deployignore` y sincronizar únicamente hacia `/home1/paulocis/apps/fogata/app/`. **Nunca transferir `db.sqlite3` local hacia producción**.

---

## 8. Criterio de Cierre y Próximos Pasos

Todos los requisitos de seguridad, aislamiento perimetral, transporte HTTPS, correo SMTP autenticado y flujo de usuario han sido verificados y aprobados con una calificación de **100% PASS**.

Fogata está lista en producción para recibir a los primeros **5 a 10 músicos de prueba** del piloto controlado.
