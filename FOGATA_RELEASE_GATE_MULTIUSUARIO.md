# FOGATA — RELEASE GATE MULTIUSUARIO PARA PILOTO EXTERNO

**Fase:** 6.1 — Release Gate Multiusuario  
**Fecha de Evaluación:** Septiembre 2026  
**Resultado Global:** **APROBADO PARA PILOTO EXTERNO**  
**Principio Rector:** *"Antes de invitar a un amigo, debemos intentar utilizar Fogata como si fuéramos otro usuario intentando romper el aislamiento."*  

---

## 1. Resumen Ejecutivo de Validación

La suite adversarial y los ensayos de penetración funcional ejecutados sobre la arquitectura multiusuario de Fogata confirman que:
1. El aislamiento entre usuarios es absoluto a nivel de vista, consulta ORM y almacenamiento estático/PWA.
2. No existen vulnerabilidades de referencia directa a objetos inseguros (IDOR); cualquier acceso cruzado o manipulación de parámetros devuelve HTTP 404 estricto sin divulgar títulos, artistas, metadatos ni existencia de entidades.
3. El flujo completo de extremo a extremo para un usuario nuevo que inicia desde cero (sin datos previos ni privilegios de staff) fue probado vía peticiones HTTP de navegador con éxito total.
4. Las pruebas automatizadas (113 tests unitarios y de integración) y la verificación estática de sintaxis JavaScript (`node -c`) arrojaron cero errores y cero advertencias.

---

## 2. Checklist Adversarial Obligatorio (20 Controles)

A continuación se detalla la ejecución, comportamiento observado y estado de cada control del checklist adversarial:

| Control | Descripción y Metodología Adversarial | Comportamiento Observado | Estado |
| :--- | :--- | :--- | :---: |
| **1. Usuario A / Usuario B — Aislamiento completo** | Creación de dos cuentas independientes con canciones y Fogatas privadas. Intercambio manual de IDs numéricos en URLs de detalle (`/canciones/<id>/`), modo atril (`/tocar/`), edición (`/editar/`), editor de acordes (`/acordes/`), detalle de Fogata (`/fogatas/<id>/`), atril de Fogata y edición. | Toda petición cruzada responde con **HTTP 404 Not Found**. El cuerpo de respuesta no contiene título, artista, notas ni indicios de existencia de los recursos de la otra cuenta. | **PASS** |
| **2. POST Fabricados** | Envío de peticiones HTTP POST directas con cliente HTTP intentando editar contenido ajeno, borrar canciones ajenas o asociar canciones del Usuario B al setlist del Usuario A mediante `/agregar-cancion/`. | Todas las peticiones mutables hacia IDs ajenos responden con HTTP 404 o `PermissionDenied` (403). La base de datos permanece estrictamente inalterada. | **PASS** |
| **3. Sesiones Compartidas** | Usuario A comparte Fogata A (token temporal). Acceso anónimo abre `/s/<token>/`. Se intenta forzar `cancion_id` ajeno en la URL `/s/<token>/cancion/<id>/`. Se prueba revocación y expiración temporal. | El acceso anónimo solo puede leer las canciones pertenecientes a esa Fogata. Un ID no asociado responde **HTTP 404**. Al expirar la duración o al ser revocada manualmente, responde **HTTP 410 Gone** con cabecera `Cache-Control: no-store, private`. | **PASS** |
| **4. Logout + Botón Atrás** | Navegación por páginas privadas autenticadas (detalle de canciones, atril, fogatas). Cierre de sesión mediante `POST /logout/`. Simulación de historial Atrás/Adelante del navegador. | La respuesta a `/logout/` es un redirect limpio. Todas las vistas privadas incluyen `Cache-Control: no-cache, no-store, must-revalidate, private` y `Pragma: no-cache`. El navegador no recupera contenido utilizable desde BFCache. | **PASS** |
| **5. Sesión Expirada** | Carga de vistas privadas. Invalidación o eliminación de la cookie de sesión en el cliente. Intento de recarga y navegación hacia endpoints protegidos (`/canciones/`, `/fogatas/`). | Redirección inmediata (HTTP 302) hacia `/login/?next=...`. Ningún dato privado es renderizado en la respuesta. | **PASS** |
| **6. Cambio de Usuario en Mismo Navegador** | Usuario A inicia sesión, visualiza repertorio y cierra sesión. Usuario B inicia sesión en el mismo cliente inmediatamente después. | El dashboard y repertorio de Usuario B muestran únicamente sus propios recursos. No existe filtración cruzada en interfaz, historial de sesión ni estado de cliente. | **PASS** |
| **7. Service Worker e Inspección de CacheStorage** | Inspección profunda de `static/js/sw.js` y política de caché de la PWA. Verificación de exclusión de rutas HTML privadas. | La caché estática se incrementó a `fogata-static-v2`. Se eliminó `/` y cualquier URL privada del precaching. Las solicitudes de navegación HTML solo usan red directa (`fetch`). CacheStorage solo almacena CSS, JS público y fuentes. | **PASS** |
| **8. Registro Duplicado** | Registro de cuenta inicial con `Usuario@Correo.cl` e intento posterior de registro con `usuario@correo.cl`. | El formulario normaliza correos a minúsculas (`strip().lower()`) y valida existencia contra `username` y `email__iexact`. Rechaza el registro con mensaje *"Ya existe una cuenta registrada con este correo electrónico"*. | **PASS** |
| **9. Estados de Invitaciones** | Envío de peticiones POST de registro probando invitación agotada (`usos_actuales >= max_usos`), expirada (`expira_el < now`), inactiva (`activa=False`) y código inexistente. | El servidor revalida en backend de manera estricta durante el POST. En todos los casos deniega la creación de cuenta y no descuenta cupos. | **PASS** |
| **10. Concurrencia de Invitaciones en SQLite** | Análisis y prueba multihilo con 2 hilos compitiendo simultáneamente por un código con `max_usos=1`. | **Ver Sección 3**. SQLite no implementa bloqueo por fila (`select_for_update` es no-op). Se implementó actualización condicional atómica a nivel SQL (`UPDATE ... WHERE usos_actuales < max_usos`). Exactamente 1 hilo obtuvo el cupo (1 éxito, 1 rechazo). | **CORREGIDO** |
| **11. Código de Invitación de Producción** | Generación de código criptográficamente seguro para el piloto, retiro de `PILOTO2026` y protección de credenciales. | `PILOTO2026` fue desactivado (`activa=False`). Se generó una invitación aleatoria con entropía criptográfica (`secrets.token_urlsafe`) de 10 cupos, resguardada fuera de Git, informes y repositorios. | **PASS** |
| **12. Login Uniforme** | Pruebas de autenticación: correo con mayúsculas/minúsculas mezcladas, contraseña errónea, usuario inexistente y múltiples intentos erróneos. | Las credenciales válidas funcionan independientemente del uso de mayúsculas en el correo. Las credenciales inválidas y correos inexistentes devuelven idéntico mensaje genérico (*"Correo o contraseña incorrectos"*), impidiendo enumeración de cuentas. | **PASS** |
| **13. Recuperación de Contraseña (Blind Flow + SMTP)** | Solicitud de reset para correo registrado vs correo inexistente. Verificación de entrega SMTP y token seguro. | Ambas solicitudes redirigen a la misma pantalla informativa ciego (*"Si existe una cuenta asociada a ese correo, recibirás un enlace..."*). Solo se despacha correo al usuario registrado, con token temporal de un solo uso. | **PASS** |
| **14. Protección CSRF** | Peticiones HTTP mutables (POST a login, registro, creación de canciones, compartir) enviadas sin token CSRF o con token falsificado. | Django intercepta y rechaza inmediatamente con **HTTP 403 Forbidden** (`CSRF verification failed`). | **PASS** |
| **15. Configuración de Producción Real** | Ejecución con `DEBUG=False`. Prueba de arranque sin `DJANGO_SECRET_KEY` o sin `DJANGO_ALLOWED_HOSTS`. | La aplicación aborta en inicialización (`SystemCheckError` / `ImproperlyConfigured`) si faltan variables críticas de entorno. Con variables reales configuradas, el sistema arranca con normalidad. | **PASS** |
| **16. Seguridad HTTPS y Cookies** | Revisión de parámetros de cookies y transporte seguro en producción. | En producción (`DEBUG=False`), `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `SESSION_COOKIE_HTTPONLY=True` y `CSRF_COOKIE_HTTPONLY=False` (requerido para cabecera AJAX). Cabeceras `Strict-Transport-Security` configuradas. | **PASS** |
| **17. Errores 404 / 500 Limpios** | Provocación intencional de rutas inexistentes y errores con `DEBUG=False`. | Se sirven pantallas limpias personalizadas de error. No se filtran trazas de ejecución (tracebacks), variables de entorno, directorios del servidor ni configuración interna. | **PASS** |
| **18. Django Admin Restringido** | Intento de acceso a `/admin/` con credenciales de usuario piloto estándar (`is_staff=False`). | Redirección y denegación de acceso inmediata. Únicamente cuentas con bandera explícita `is_staff=True` tienen acceso al panel de administración. | **PASS** |
| **19. Auditoría de Secretos y Contenido** | Búsqueda exhaustiva en repositorio, fixtures, migraciones y código fuente de letras completas comerciales o credenciales expuestas. | El repositorio no contiene letras completas comerciales protegidas por copyright, claves SMTP reales ni SECRET_KEY de producción. Todos los secretos se inyectan por variables de entorno. | **PASS** |
| **20. Suite Final de Validación Técnica** | Ejecución de `python manage.py test` y chequeo sintáctico de scripts cliente `node -c static/js/fogata.js` y `node -c static/js/sw.js`. | **113 tests ejecutados, 0 fallos, 0 errores (OK)**. Chequeo sintáctico Node.js finalizado con código de salida 0. | **PASS** |

---

## 3. Dictamen Técnico Específico: Concurrencia en SQLite (Control 10)

### Hallazgo y Limitación de la Base de Datos
En SQLite, la instrucción `select_for_update()` del ORM de Django es una **operación nula (no-op)** debido a que el motor SQLite no implementa bloqueos granulares a nivel de fila (Row-Level Locking), sino bloqueos a nivel de archivo de base de datos (`database table is locked`).

Si dos peticiones entraran en el microsegundo exacto leyendo `invitacion.usos_actuales` antes de que la otra escriba, un esquema basado en lectura + escritura en memoria podría causar sobreasignación de cupos.

### Mitigación Implementada y Verificada (CORREGIDO)
Se corrigió el método `Invitacion.consumir_codigo` implementando una **actualización condicional atómica a nivel SQL**:

```python
filas_afectadas = Invitacion.objects.filter(
    Q(codigo=codigo, activa=True) &
    (Q(expira_el__isnull=True) | Q(expira_el__gt=ahora)) &
    (Q(max_usos__isnull=True) | Q(usos_actuales__lt=models.F('max_usos')))
).update(
    usos_actuales=models.F('usos_actuales') + 1
)

if filas_afectadas == 0:
    raise ValueError("El código de invitación es inválido, expiró o agotó sus cupos.")
```

Asimismo, se configuró `'timeout': 20` en las opciones de SQLite en `settings.py` para evitar errores de colisión por bloqueo de base de datos bajo ráfagas concurrentes.

### Regla Operacional para el Piloto
> **Regla de Despliegue:**  
> Mientras SQLite sea el motor del piloto, no se emitirán códigos con cupos de alta contención simultánea (como un código único de 1 cupo entregado a múltiples personas al mismo tiempo en competencia pública). Las invitaciones del piloto se entregarán de forma nominal y controlada a cada usuario.

---

## 4. Evidencia de Prueba Real de Usuario desde Cero

Se ejecutó la prueba de extremo a extremo simulando a un músico real que ingresa por primera vez sin intervención de base de datos:

```text
[Paso 1] Invitación emitida y entregada al usuario
         ↓
[Paso 2] Pantalla de registro cargada con prellenado de código (?codigo=...)
         ↓
[Paso 3] Registro exitoso con nombre y correo normalizado. Autenticación automática.
         ↓
[Paso 4] Home/Bienvenida: Detección de repertorio vacío y presentación del CTA inicial
         ↓
[Paso 5] Formulario "Nueva Canción": Carga de acordes en formato bracket [Sol]
         ↓
[Paso 6] Flujo "Guardar y Tocar": Guardado instantáneo y redirección directa al Atril (/tocar/)
         ↓
[Paso 7] Creación de Fogata "Fogata en la Playa"
         ↓
[Paso 8] Incorporación de la canción al setlist de la Fogata con nota de interpretación
         ↓
[Paso 9] "Tocar Fogata": Ejecución continua de repertorio en pantalla única
         ↓
[Paso 10] Compartir Sesión: Generación de enlace temporal seguro con vigencia de 4 horas
         ↓
[Paso 11] Apertura en Navegador Incógnito (Invitado anónimo):
          - Visualización de setlist y letra autorizada
          - Sin acordes ni controles de edición
          - Cabeceras de privacidad estrictas (Cache-Control: no-store, private)
```
**Resultado:** **PASS TOTAL.** Todo el recorrido opera a través de la interfaz web nativa sin fricciones ni bloqueos.

---

## 5. Matriz de Criterio de Aprobación

| Área Crítica | Requerimiento de Puerta | Estado |
| :--- | :--- | :---: |
| Aislamiento de datos | Cero filtración entre Usuario A y Usuario B | **PASS** |
| IDOR | Todo acceso cruzado a IDs ajenos debe responder 404 | **PASS** |
| Autenticación | Registro seguro, hash PBKDF2 nativo, normalización de correos | **PASS** |
| Logout | Salida por POST con expiración inmediata de sesión | **PASS** |
| Sesión expirada | Bloqueo de acceso privado ante cookies vencidas | **PASS** |
| CSRF | Obligatoriedad de token en todas las mutaciones | **PASS** |
| Recuperación de contraseña | Respuesta ciega idéntica y despacho SMTP seguro | **PASS** |
| Caché privada | Bloqueo de BFCache e historial para vistas privadas | **PASS** |
| Configuración de producción | `DEBUG=False`, fail-fast ante falta de variables críticas | **PASS** |

---

## 6. Veredicto Final

```text
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║                   APROBADO PARA PILOTO EXTERNO                            ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

No existen bloqueadores de seguridad, privacidad ni arquitectura.  
El código de producción del piloto (10 cupos) está activo en el servidor y listo para ser entregado a los músicos seleccionados.

> **Cierre de Ciclo de Desarrollo:**  
> A partir de este momento, **no se desarrollarán nuevas funcionalidades**. Fogata queda en modo de escucha y aprendizaje de sus usuarios reales de acuerdo con las pautas de [PILOTO_EXTERNO_FOGATA.md](file:///Users/rmerinog/PLATAFORMAS/FOGATA/PILOTO_EXTERNO_FOGATA.md).
