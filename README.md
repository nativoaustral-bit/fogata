# FOGATA

> **Tus canciones. Tus acordes. Tu sesión.**

Fogata es una plataforma web y atril digital interactivo diseñado para músicos en vivo. Permite a cada usuario incorporar sus propias canciones, letras y acordes, organizarlas en Fogatas (repertorios y setlists ordenados) y utilizarlas en ensayos, eventos y tocatas mediante una interfaz inmersiva optimizada para lectura a distancia.

*Nota:* Fogata es una herramienta para músicos; cada usuario incorpora y gestiona su propio repertorio personal. La plataforma no provee ni distribuye canciones de terceros.

[![Django](https://img.shields.io/badge/Django-5.2%20LTS-092E20?style=flat-square&logo=django)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-209%20passed%20(100%25)-brightgreen?style=flat-square)](#-validación-rápida)
[![Producción](https://img.shields.io/badge/Producción-fogata.humm.cl-success?style=flat-square)](https://fogata.humm.cl)

---

## 📌 Tabla de Contenidos

1. [Estado Actual](#-estado-actual)
2. [Arquitectura](#-arquitectura)
3. [Estructura del Proyecto](#-estructura-del-proyecto)
4. [Configuración Local](#-configuración-local)
5. [Variables de Entorno](#-variables-de-entorno)
6. [Pasarela Flow (Producción)](#-pasarela-flow-producción)
7. [Planes y Límites Comerciales](#-planes-y-límites-comerciales)
8. [Despliegue en Producción (HostGator)](#-despliegue-en-producción-hostgator)
9. [Política de Respaldos](#-política-de-respaldos)
10. [Seguridad y Privacidad](#-seguridad-y-privacidad)
11. [Validación Rápida](#-validación-rápida)
12. [Pendientes](#-pendientes)

---

## 📊 Estado Actual

Funcionalidades operativas y verificadas en la suite de pruebas y en producción:

* **Usuarios y Autenticación:**
  * Registro de cuentas mediante código de invitación o acceso directo.
  * Autenticación por correo electrónico normalizado (insensible a mayúsculas/minúsculas).
  * Recuperación segura de contraseña mediante flujo ciego (*blind-flow*) vía SMTP SSL en puerto 465.
* **Gestión de Canciones:**
  * Ingestión de letras con acordes en formato de corchetes (`[G]Texto`) o acordes sobre la letra con monoespaciado exacto.
  * Sanitización automática y no destructiva de caracteres invisibles Unicode (`\u200b`, `\ufeff`, etc.) y normalización de espacios tipográficos al guardar y renderizar.
  * Edición rápida de acordes individuales o reemplazo global preservando columnas contiguas.
* **Fogatas (Setlists en Vivo):**
  * Agrupación ordenada de canciones para presentaciones, ensayos o fogatas.
  * Reordenamiento secuencial de temas y notas específicas por sesión.
* **Modo Tocar (Atril Digital):**
  * Vista inmersiva en pantalla completa optimizada para lectura en dispositivos móviles y tablets.
  * Auto-scroll continuo con velocidad regulable al vuelo y cálculo por duración estimada.
  * Activación de la **Screen Wake Lock API** para impedir que la pantalla se apague durante la ejecución musical.
  * Controles de tamaño de tipografía y modo oscuro de alto contraste.
* **Transposición Armónica:**
  * Transposición tonal de -6 a +6 semitonos con resolución inteligente de enarmónicos.
  * Ejecución client-side instantánea (<2 ms) en el DOM y fallback server-side accesible.
* **Notación Musical C ↔ Do:**
  * Alternancia instantánea con un clic entre notación anglosajona (`C, D, E...`) y latina (`Do, Re, Mi...`).
* **Diagramas de Acordes SVG:**
  * Generador procedural nativo en Python de diagramas vectoriales SVG para guitarra en afinación estándar EADGBE (cero librerías pesadas o CDNs).
  * Panel interactivo para inspeccionar la digitación de cualquier acorde pulsándolo en el atril.
* **Sesiones Compartidas y Modo Invitado:**
  * Enlaces temporales únicos (`/s/<token>/`) con códigos QR para compartir el setlist con otros músicos en tiempo real sin requerir registro.
* **Modelo Freemium (Gratis y Pro):**
  * Plan `GRATIS` con 100% de capacidades musicales habilitadas (límite de 10 canciones y 1 Fogata activa).
  * Plan `PRO` con almacenamiento ilimitado de canciones y Fogatas.
  * Política de downgrade no destructiva (si vence Pro, no se eliminan datos; solo se limita la creación de nuevos ítems).
* **Pasarela de Pago Flow (Chile / CLP):**
  * Integración con Flow Producción para pagos vía Webpay Plus, tarjetas de débito y crédito.
  * Recepción de webhooks asíncronos con verificación de firma HMAC-SHA256, activación atómica e idempotente de suscripciones Pro.
  * Comando cron de reconciliación periódica de pagos pendientes.
* **Fogata Control Center y Métricas:**
  * Panel administrativo en `/gestion/` con métricas de adopción, embudos de conversión y monitoreo de capacidad.
  * Ficha 360° de usuarios con historial de actividad y cambio manual de plan auditado.
  * Garantía ética de privacidad (`METADATA_WHITELIST`): nunca se persisten letras, acordes ni notas de los usuarios.
* **Herramientas de Mantenimiento:**
  * Endpoint administrativo `/gestion/mantenimiento/` para depuración segura de datos de prueba con previsualización en modo dry-run y salvaguardas irreversibles para cuentas reales.

---

## 🏗️ Arquitectura

* **Backend:** Django 5.2 LTS sobre Python 3.12+.
* **Filosofía:** Server-Side Rendering (SSR) puro, minimalista y de alto rendimiento.
* **Frontend:** HTML5 semántico, CSS vanilla (diseño responsive, dark mode nativo, glassmorphism sutil, tipografía Inter/monoespaciada) y JavaScript en ES5 nativo. Cero dependencias de npm, frameworks pesados (React/Vue) o empaquetadores (Webpack/Vite).
* **Base de Datos:** SQLite con configuración de alta concurrencia (`timeout=20`), transacciones atómicas `with transaction.atomic():` y actualizaciones condicionales atómicas con expresiones `F()`. Preparado para migración transparente a PostgreSQL.
* **Servidor Web y WSGI:** Apache 2.4 con Phusion Passenger en entorno compartido HostGator (`passenger_wsgi.py`).
* **PWA:** Web App Manifest (`/manifest.webmanifest`) y Service Worker (`/sw.js`) con soporte de instalación en pantalla de inicio.

---

## 📁 Estructura del Proyecto

```text
FOGATA/
├── apps/
│   ├── canciones/             # Motor musical, parser de acordes, transposición, diagramas SVG y atril
│   │   ├── diagramas.py       # Generador procedural de diagramas SVG de guitarra
│   │   ├── forms.py           # Formulario de creación/edición con sanitización automática
│   │   ├── models.py          # Modelo Cancion con contenido íntegro y tono base
│   │   ├── parser.py          # Detección formal de acordes, compensación espacial y transposición
│   │   ├── tests.py           # Suite exhaustiva de pruebas unitarias y musicales (76 tests)
│   │   └── views.py           # CRUD de repertorio, atril /tocar/ y edición rápida de acordes
│   │
│   ├── core/                  # Autenticación, perfiles, planes freemium, middleware y PWA
│   │   ├── backends.py        # Autenticación por correo normalizado
│   │   ├── context_processors.py # Inyección global del plan activo en plantillas
│   │   ├── middleware.py      # Control estricto de caché privada (Cache-Control: no-store)
│   │   ├── models.py          # Modelos Invitacion y PerfilPiloto
│   │   ├── planes.py          # Única fuente de verdad de límites y capacidad
│   │   ├── test_planes.py     # Suite de pruebas de límites y concurrencia
│   │   └── views.py           # Registro, login, recuperación de clave, landing /pro/ y PWA
│   │
│   ├── fogatas/               # Setlists, ordenamiento y sesiones compartidas con QR
│   │   ├── models.py          # Modelos Fogata, FogataCancion y SesionCompartida
│   │   ├── tests.py           # Pruebas de setlists y accesos públicos temporales
│   │   └── views.py           # Gestión de repertorios y atril para invitados
│   │
│   ├── gestion/               # Fogata Control Center, analítica ética y mantenimiento
│   │   ├── constants.py       # Whitelist estricta de metadatos (política de privacidad)
│   │   ├── metrics.py         # Métricas comerciales y embudos de adopción
│   │   ├── models.py          # Modelos EventoUso y AuditoriaAdmin
│   │   ├── services/          # Lógica desacoplada de eventos y limpieza segura
│   │   ├── tests.py           # Pruebas de métricas, seguridad y mantenimiento
│   │   └── views.py           # Panel administrativo y endpoints de mantenimiento
│   │
│   └── pagos/                 # Pasarela comercial Flow (Webpay Plus / Débito / Crédito)
│       ├── models.py          # Modelo OrdenPago con estados y metadatos Flow
│       ├── services.py        # Comunicación HTTPS firmada HMAC-SHA256 y activación Pro
│       ├── tests.py           # Pruebas de checkout, callbacks, seguridad y crons
│       └── views.py           # Endpoints de creación, retorno y webhook de confirmación
│
├── config/                    # Configuración central Django (settings, urls, wsgi)
├── static/                    # Archivos estáticos servidos (CSS vanilla, fogata.js, service worker)
├── templates/                 # Plantillas HTML semánticas SSR organizadas por aplicación
├── deploy.sh                  # Script de despliegue automatizado por SSH hacia HostGator
├── manage.py                  # Entrypoint CLI de Django con carga automática de .env
├── requirements.txt           # Dependencias de producción
├── .deployignore              # Patrones de exclusión para despliegue
├── .gitignore                 # Reglas de exclusión para Git
└── README.md                  # Documentación técnica maestra del proyecto
```

---

## 💻 Configuración Local

### Prerrequisitos
* Python 3.12 o superior.
* `venv` o `uv`.
* Git.

### Paso a paso

1. **Clonar el repositorio:**
   ```bash
   git clone git@github.com:nativoaustral-bit/fogata.git
   cd fogata
   ```

2. **Crear y activar entorno virtual:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Variables de entorno locales (opcional):**
   `config/settings.py` cuenta con valores predeterminados seguros para desarrollo local (`DEBUG=True`). Si se requiere personalizar parámetros, crear un archivo `.env` en la raíz (ver sección [Variables de Entorno](#-variables-de-entorno)).

5. **Aplicar migraciones:**
   ```bash
   python manage.py migrate
   ```

6. **Crear superusuario administrador:**
   ```bash
   python manage.py createsuperuser
   ```

7. **Ejecutar la suite completa de pruebas:**
   ```bash
   python manage.py test
   ```

8. **Iniciar el servidor local:**
   ```bash
   python manage.py runserver
   ```
   Abrir en el navegador: `http://127.0.0.1:8000/`.

---

## 🔐 Variables de Entorno

Fogata utiliza variables de entorno para desacoplar credenciales y configuraciones sensibles del código fuente. En desarrollo se aplican valores por defecto seguros; en producción se cargan desde el archivo `.env` fuera del árbol web.

### Parámetros Principales del Sistema

| Categoría | Variable | Propósito |
| :--- | :--- | :--- |
| **Django Base** | `DJANGO_DEBUG` | Control de modo depuración (`True` local, `False` producción). |
| | `DJANGO_SECRET_KEY` | Clave criptográfica para firmas de sesión y CSRF. |
| | `DJANGO_ALLOWED_HOSTS` | Dominios autorizados separados por coma. |
| | `DJANGO_CSRF_TRUSTED_ORIGINS` | Orígenes confiables para validación CSRF HTTPS. |
| | `DJANGO_DB_PATH` | Ruta absoluta al archivo de base de datos SQLite persistente. |
| | `DJANGO_LOG_DIR` | Ruta al directorio donde se escriben los logs rotativos. |
| **Pasarela Flow** | `FLOW_API_KEY` | Llave pública de comercio Flow. |
| | `FLOW_SECRET_KEY` | Clave secreta privada para firma HMAC-SHA256. |
| | `FLOW_ENVIRONMENT` | Entorno de ejecución (`production` o `sandbox`). |
| | `FLOW_BASE_URL` | URL base de la API Flow (`https://www.flow.cl/api` o `https://sandbox.flow.cl/api`). |
| | `FOGATA_BASE_URL` | URL pública absoluta de Fogata para webhooks de retorno y confirmación. |
| | `FOGATA_PAYMENTS_ENABLED` | Interruptor general para habilitar compras de planes Pro (`True` o `False`). |
| | `FLOW_PAYMENT_TIMEOUT` | Tiempo de expiración de órdenes pendientes en segundos. |
| | `FLOW_HTTP_TIMEOUT` | Timeout de peticiones de red hacia Flow en segundos. |
| | `FLOW_CONFIRMATION_TIMEOUT` | Timeout para la resolución del webhook de confirmación. |
| **Planes y Precios** | `FOGATA_FREE_MAX_SONGS` | Límite de canciones para plan Gratis (default: `10`). |
| | `FOGATA_FREE_MAX_FOGATAS` | Límite de Fogatas activas para plan Gratis (default: `1`). |
| | `FOGATA_PRO_SEMESTRAL_PRICE_CLP` | Precio en CLP del plan Pro Semestral (default: `5990`). |
| | `FOGATA_PRO_ANUAL_PRICE_CLP` | Precio en CLP del plan Pro Anual (default: `9990`). |
| | `FOGATA_ANALYTICS_START_DATE` | Fecha base de cálculo para métricas del Control Center (`YYYY-MM-DD`). |
| **Correo (SMTP)** | `DJANGO_EMAIL_BACKEND` | Backend de correo Django (`smtp` en producción, `console` en pruebas). |
| | `EMAIL_HOST` | Servidor SMTP saliente (ej: `mail.humm.cl`). |
| | `EMAIL_PORT` | Puerto SMTP seguro (ej: `465` para SSL nativo en HostGator). |
| | `EMAIL_USE_SSL` | Forzar canal cifrado SSL (`True`). |
| | `EMAIL_USE_TLS` | Forzar canal cifrado STARTTLS (`False` si se usa SSL). |
| | `EMAIL_HOST_USER` | Usuario o buzón autenticado del servidor de correo. |
| | `EMAIL_HOST_PASSWORD` | Contraseña de autenticación SMTP. |
| | `DEFAULT_FROM_EMAIL` | Remitente público visible (ej: `Fogata <no-reply@humm.cl>`). |

---

## 💳 Pasarela Flow (Producción)

Fogata cuenta con integración nativa con la pasarela oficial **Flow** (Chile) para la suscripción a planes Pro en moneda local (CLP):

1. **Configuración de Producción:**
   * Entorno activo: `FLOW_ENVIRONMENT=production`
   * Endpoint base: `https://www.flow.cl/api`
   * Pagos habilitados: `FOGATA_PAYMENTS_ENABLED=True`
2. **Ciclo de Transacción:**
   * **Creación:** El usuario pulsa *Suscribirme* en `/pro/`; el servidor crea el registro en `OrdenPago` con estado `PENDIENTE` y despacha una solicitud firmada con HMAC-SHA256 hacia `payment/create`.
   * **Checkout:** El usuario es redirigido a la pasarela Webpay Plus / Flow.
   * **Confirmación Asíncrona (`urlConfirmation`):** Flow invoca vía POST el endpoint público `/pagos/flow/confirmacion/`. El servidor valida el token llamando a `payment/getStatus`, verifica coincidencia exacta de monto, comercio y moneda, y activa la vigencia Pro en `PerfilPiloto` de forma atómica.
   * **Idempotencia:** Si se reciben llamadas duplicadas de confirmación para una misma orden ya aplicada (`pro_aplicado=True`), el sistema responde de forma segura sin alterar fechas ni duplicar vigencias.
   * **Retorno del Usuario (`urlReturn`):** Manejo dual (POST o GET) en `/pagos/flow/retorno/` con verificación de token y redirección a la pantalla de éxito `/pagos/exito/`.
3. **Reconciliación Automática por Cron:**
   * Comando de consola `manage.py reconciliar_pagos_flow`.
   * Ejecutado cada 15 minutos en el crontab del servidor para consultar transacciones que hayan quedado en estado pendiente por fallas transitorias de red o abandono del usuario en el navegador.
4. **Segregación Sandbox / Producción:**
   * En modo `sandbox`, las órdenes se crean contra `https://sandbox.flow.cl/api` y los pagos simulados no contaminan los ingresos comerciales reales en el Control Center.

---

## 💎 Planes y Límites Comerciales

La lógica de capacidad comercial está centralizada en `apps/core/planes.py`:

| Plan | Canciones Almacenadas | Fogatas Activas | Precio CLP | Experiencia Musical |
| :--- | :---: | :---: | :---: | :---: |
| **Fogata Gratis** | Hasta 10 canciones | 1 Fogata activa | **$0** (Para siempre) | **100% Completa** (Atril, transposición, diagramas, QR) |
| **Fogata Pro Semestral** | **Ilimitadas (∞)** | **Ilimitadas (∞)** | **$5.990** / 6 meses | **100% Completa** |
| **Fogata Pro Anual** | **Ilimitadas (∞)** | **Ilimitadas (∞)** | **$9.990** / año | **100% Completa** |

### Reglas Comerciales de la Plataforma
* **Capacidad, no funcionalidad:** Los usuarios del plan Gratis tienen acceso idéntico al Modo Tocar, auto-scroll, transposición, diagramas SVG y sesiones compartidas.
* **Validación Atómica Server-Side:** La creación de canciones y fogatas valida los límites dentro de transacciones de base de datos (`with transaction.atomic():`), impidiendo evasiones por concurrencia.
* **Política de Downgrade No Destructiva:** Si una suscripción Pro vence, **ningún dato se borra ni se bloquea**. El usuario conserva todas sus canciones y setlists existentes; únicamente no podrá crear ítems nuevos hasta renovar o situarse bajo el cupo gratuito.

---

## 🚀 Despliegue en Producción (HostGator)

Fogata opera en producción en el dominio **[https://fogata.humm.cl](https://fogata.humm.cl)** alojado en el servidor HostGator (`shared16.hostgator.cl`).

### Arquitectura de Aislamiento en el Servidor
Para garantizar máxima seguridad perimetral, el código, el entorno virtual, la base de datos persistente y los secretos residen **fuera** del árbol web público:

```text
/home1/paulocis/
├── apps/
│   └── fogata/
│       ├── app/                     <- Código fuente de la app sincronizado vía Git
│       │   ├── staticfiles/         <- Archivos estáticos procesados por collectstatic
│       │   └── manage.py
│       ├── venv/                    <- Entorno virtual Python 3.12 aislado (uv)
│       ├── var/
│       │   └── db.sqlite3           <- Base de datos persistente (chmod 600)
│       ├── logs/                    <- Directorio de logs de aplicación y crons
│       └── secrets/
│           └── .env                 <- Variables de entorno de producción (chmod 600)
│
└── fogata.humm.cl/                  <- DocumentRoot público exclusivo del subdominio
    ├── .htaccess                    <- Reglas Apache, forzado HTTPS 301 y bloqueo de accesos
    ├── passenger_wsgi.py            <- Punto de entrada Phusion Passenger WSGI
    ├── static -> /home1/paulocis/apps/fogata/app/staticfiles
    └── tmp/
        └── restart.txt              <- Control de recarga de procesos Passenger
```

### Flujo Automatizado con `deploy.sh`
Para desplegar actualizaciones a producción, ejecutar desde la estación de trabajo:

```bash
./deploy.sh
```

El script ejecuta de forma atómica y segura:
1. Envío de commits a GitHub (`git push origin main`).
2. Conexión SSH segura hacia el servidor HostGator (`paulocis@humm.cl:2222`).
3. Sincronización de código vía `git pull --ff-only origin main`.
4. Instalación de dependencias con `/home1/paulocis/.local/bin/uv pip install -r requirements.txt`.
5. Carga de variables de entorno de producción desde `secrets/.env`.
6. Ejecución de migraciones pendientes (`manage.py migrate --noinput`).
7. Recolección de estáticos (`manage.py collectstatic --noinput`).
8. Recarga del servidor mediante `touch tmp/restart.txt`.
9. Comprobación automática de salud web (Smoke test HTTP `200 OK` en `https://fogata.humm.cl/`).

### Tareas Programadas en Crontab (HostGator)
```cron
# Reconciliación de pagos pendientes Flow (cada 15 minutos)
*/15 * * * * cd /home1/paulocis/apps/fogata/app && /home1/paulocis/apps/fogata/venv/bin/python manage.py reconciliar_pagos_flow >> /home1/paulocis/apps/fogata/logs/cron_flow.log 2>&1

# Procesamiento diario de vencimientos de suscripciones Pro (03:00 UTC)
0 3 * * * cd /home1/paulocis/apps/fogata/app && /home1/paulocis/apps/fogata/venv/bin/python manage.py procesar_vencimientos_pro >> /home1/paulocis/apps/fogata/logs/cron_planes.log 2>&1
```

---

## 🗄️ Política de Respaldos

1. **Datos Respaldados:**
   * Archivo de base de datos persistente SQLite de producción ubicado en `/home1/paulocis/apps/fogata/var/db.sqlite3`.
2. **Ubicación y Almacenamiento:**
   * Los respaldos se gestionan a nivel de servidor y copias de seguridad de cPanel fuera del repositorio Git.
   * **Regla estricta:** Ningún respaldo de base de datos se versiona en Git (el directorio `db_backups/` y archivos `*.sqlite3` están excluidos permanentemente en `.gitignore`).
3. **Frecuencia y Retención:**
   * Copias periódicas previas a migraciones estructurales y respaldos rotativos automáticos en el servidor con retención de las últimas 7 copias.

---

## 🔒 Seguridad y Privacidad

1. **Secretos y Credenciales:**
   * Todas las credenciales, llaves de API de Flow y contraseñas SMTP se almacenan exclusivamente en `secrets/.env` con permisos restringidos (`chmod 600`).
   * No existen secretos versionados en el historial ni en el código fuente.
2. **Aislamiento Multiusuario y Cero IDOR:**
   * Todas las consultas del ORM filtran estrictamente por `propietario=request.user`.
   * Cualquier intento de acceso a canciones o fogatas inexistentes o ajenas responde invariablemente con un **HTTP 404 estricto**, impidiendo la enumeración de identificadores de terceros.
3. **Privacidad Ética en Telemetría:**
   * En cumplimiento con `apps/gestion/constants.py` (`METADATA_WHITELIST`), el sistema de analítica de comportamiento **jamás registra títulos de canciones, letras, progresiones de acordes ni notas de interpretación**.
4. **Seguridad Web:**
   * En producción (`DEBUG=False`), se aplican cabeceras de transporte seguro: `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`, `SESSION_COOKIE_HTTPONLY = True`, `SECURE_CONTENT_TYPE_NOSNIFF = True`, `X_FRAME_OPTIONS = 'DENY'` y política `Cache-Control: no-store` en vistas privadas.
5. **Autenticación y Recuperación Ciega:**
   * Flujo ciego en `recuperar-password`: el sistema presenta la misma respuesta visual tanto si el correo existe como si no, bloqueando la enumeración de usuarios registrados.

---

## 🧪 Validación Rápida

Comandos para verificar la salud y corrección de la plataforma:

```bash
# Activar entorno virtual
source .venv/bin/activate

# 1. Comprobación de configuración Django
python manage.py check

# 2. Ejecutar la suite completa de pruebas unitarias e integración (209 tests)
python manage.py test

# 3. Ejecutar pruebas de módulos específicos
python manage.py test apps.canciones      # Motor musical, parser, diagramas (76 tests)
python manage.py test apps.pagos          # Pasarela Flow, webhooks, reconciliación (30 tests)
python manage.py test apps.core           # Autenticación, planes, límites (39 tests)
python manage.py test apps.gestion        # Control Center, analítica, limpieza (43 tests)
python manage.py test apps.fogatas        # Setlists, sesiones compartidas (21 tests)

# 4. Chequeo sintáctico de JavaScript cliente
node -c static/js/fogata.js
node -c static/js/sw.js
```

### Lista de Comprobación Posterior al Despliegue (Smoke Test)
* [ ] **Disponibilidad Web:** `curl -s -o /dev/null -w "%{http_code}" https://fogata.humm.cl/` responde `200`.
* [ ] **Autenticación:** Inicio de sesión correcto y navegación hacia `/canciones/`.
* [ ] **Canción y Atril:** Abrir una canción en `/tocar/`, comprobar auto-scroll, transposición tonal y despliegue del modal de diagrama SVG de acordes.
* [ ] **Fogata:** Visualizar setlist y comprobar acceso invitado en `/s/<token>/`.
* [ ] **Flow:** Entrar a `/pro/` y verificar que las opciones de suscripción desplieguen los precios vigentes ($5.990 / $9.990).
* [ ] **Recuperación de Clave:** Solicitar recuperación en `/recuperar-password/` y constatar respuesta visual inmediata.

---

## 📌 Pendientes

1. **Pasarela de Pago Internacional:** Integración de medio de pago internacional complementario (ej: Stripe) para cobros en USD a usuarios fuera de Chile (Flow cubre actualmente el 100% de los medios de pago chilenos en CLP).
2. **Modo Offline PWA Extendido:** Almacenamiento local mediante IndexedDB / Cache Storage de setlists completos para permitir ejecución del atril sin conexión a internet en zonas remotas o campings.

---

*Fogata es un producto desarrollado con dedicación por el equipo de Humm.*  
*Contacto y soporte: [fogata.humm.cl](https://fogata.humm.cl)*
