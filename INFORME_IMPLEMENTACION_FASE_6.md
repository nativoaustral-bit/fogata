# INFORME DE IMPLEMENTACIÓN — FASE 6
## Fogata — Piloto Multiusuario, Registro e Inicio de Sesión

> **Fecha:** 27 de Septiembre de 2026  
> **Estado:** **APROBADO Y VALIDADO (112 tests superados con 0 errores)**  
> **Principio rector:** *Cada usuario debe sentir que Fogata es únicamente suya.*  
> **Máxima de seguridad:** *Ningún dato privado debe depender de que el usuario recuerde cerrar sesión correctamente para mantenerse privado.*

---

## 1. Resumen Ejecutivo

La **Fase 6** transforma a **Fogata** desde un MVP personal hacia una plataforma multiusuario robusta, segura y lista para un **piloto externo controlado**.

Se implementó el aislamiento estricto de datos entre usuarios (canciones, Fogatas y setlists), autenticación nativa de Django con correo electrónico normalizado en minúsculas como identidad única (`User.username = User.email = email.lower()`), registro exclusivo por invitación con reserva atómica bajo concurrencia (`select_for_update()`), protección completa contra referencias directas inseguras a objetos (**IDOR**), flujo de restablecimiento ciego de contraseña (**blind password reset**), logout seguro exclusivamente por **POST**, cabeceras estrictas de no-caché para contenido privado (`Cache-Control: no-store, private`), suspensión temporal preventiva del almacenamiento persistente de letras privadas en PWA CacheStorage para evitar fugas entre cuentas, y hardening de producción por defecto (`DEBUG=False` con validación estricta de variables de entorno).

---

## 2. Respaldo Obligatorio y Migraciones Ejecutadas

### 2.1 Respaldo Verificable
Antes de aplicar las mutaciones estructurales a la base de datos existente, se generó un respaldo fechado de la base de datos fuera de Git:
```bash
db_backups/fogata_pre_multiusuario_20260927_142421.sqlite3
```
El directorio `db_backups/` fue registrado en `.gitignore` para impedir que se suba accidentalmente al repositorio.

### 2.2 Proceso en Dos Pasos y Asignación de Propietario Inicial
Para evitar la creación automática o ficticia de cuentas como `admin@fogata.app` dentro de migraciones, se siguió un proceso estricto:

1. **Migración 1 (Campos anulables):**
   - `apps/canciones/migrations/0003_cancion_propietario.py`: agrega `propietario` (`null=True`) en `Cancion`.
   - `apps/fogatas/migrations/0002_fogata_propietario.py`: agrega `propietario` (`null=True`) en `Fogata`.
   - `apps/core/migrations/0001_initial.py`: crea el modelo de `Invitacion`.

2. **Comando Administrativo Explícito:**
   Se desarrolló el comando:
   ```bash
   python manage.py asignar_propietario_inicial --email=admin@humm.cl
   ```
   **Resultado:** Verificó la existencia de la cuenta real del superusuario (`admin@humm.cl`), detectó 7 canciones y 4 Fogatas sin propietario, las asignó atómicamente y certificó que quedaron **0 registros huérfanos**.

3. **Migración 2 (Cierre estricto a `null=False`):**
   - `apps/canciones/migrations/0004_alter_cancion_propietario.py`: altera `propietario` a `null=False` en `Cancion`.
   - `apps/fogatas/migrations/0003_alter_fogata_propietario.py`: altera `propietario` a `null=False` en `Fogata`.

4. **Migración 3 (Auditoría de Piloto):**
   - `apps/core/migrations/0002_perfilpiloto.py`: crea el modelo `PerfilPiloto` vinculado vía `OneToOneField` a `User` para registrar el código de invitación empleado por cada cuenta en el piloto.

---

## 3. Identidad y Autenticación Django Simplificada

Se conservó el modelo estándar `django.contrib.auth.models.User` para evitar migraciones riesgosas en este piloto, implementando la siguiente estrategia de identidad:

* **Presentación al usuario:** Exclusivamente **Correo electrónico + Contraseña**.
* **Tratamiento interno:**
  1. El correo recibido se normaliza y se convierte a minúsculas (`email.strip().lower()`).
  2. Se limita a un máximo de 150 caracteres (compatibilidad con `username`).
  3. Se almacena idénticamente en:
     ```python
     user.username = email_normalizado
     user.email = email_normalizado
     ```
  4. Se aprovecha la restricción `unique=True` a nivel de esquema de base de datos que Django posee en `username`.
* **Backend de Autenticación (`EmailAuthBackend`):** Permite autenticar al usuario insensibilizando las mayúsculas/minúsculas introducidas en el login (`email__iexact=email`).

---

## 4. Registro por Invitación con Protección de Concurrencia

El modelo `Invitacion` protege el acceso al piloto con los siguientes criterios:

* **Consumo Atómico con Bloqueo de Fila:**
  ```python
  with transaction.atomic():
      inv = Invitacion.objects.select_for_update().get(codigo=codigo_limpio)
      if not inv.activa or (inv.expira_el and timezone.now() >= inv.expira_el) or ...:
          raise ValueError(...)
      inv.usos_actuales += 1
      if inv.max_usos and inv.usos_actuales >= inv.max_usos:
          inv.activa = False
      inv.save()
  ```
  Esto previene que dos peticiones simultáneas consuman el último cupo disponible (*race condition*).
* **Validación en Servidor:** Si llega `/registro/?codigo=ABC123`, el valor se precarga en el formulario, pero en el `POST` se revalida de punta a punta. Nunca se confía en valores `GET`, `hidden` o `readonly`.
* **Consentimiento Mínimo:** Se incluyó la leyenda regulatoria explícita:
  > *«Al crear tu cuenta aceptas utilizar Fogata para gestionar tu propio repertorio.»*
* **Comando Administrativo:**
  ```bash
  python manage.py crear_invitacion --codigo=PILOTO2026 --usos=25 --descripcion="Piloto inicial amigos"
  ```

---

## 5. Prevención de IDOR y Aislamiento de Bibliotecas

Se implementó el principio fundamental:
> **«El ID nunca otorga acceso. El propietario sí.»**

### 5.1 En Vistas de Canciones y Fogatas
Todas las vistas privadas de `apps.canciones` y `apps.fogatas` están protegidas con `@login_required` y consultan estrictamente por propietario:
```python
cancion = get_object_or_404(Cancion, pk=pk, propietario=request.user)
fogata = get_object_or_404(Fogata, pk=pk, propietario=request.user)
```
Si el Usuario A solicita cualquier recurso del Usuario B (incluso si conoce el ID numérico), el servidor responde con **HTTP 404 (Not Found)** genérico, sin revelar jamás si el recurso existe o a quién pertenece.

### 5.2 Endpoints Auxiliares y Modales
En el endpoint de diagramas de acordes (`ver_diagrama`):
* Si recibe `cancion_id`, se valida `Cancion.objects.filter(pk=id, propietario=request.user)`.
* Si recibe `fogata_id`, se valida `Fogata.objects.filter(pk=id, propietario=request.user)`.
* Un usuario no puede utilizar el visor de diagramas para inferir ni acceder a metadatos de canciones ajenas.

### 5.3 Triple Protección Fogata ↔ Canción (Criterio 9)
Para impedir que una Fogata del Usuario A contenga canciones del Usuario B:
1. **Filtro en Formulario:** `AgregarCancionForm` restringe su `ModelChoiceField` a `Cancion.objects.filter(propietario=fogata.propietario)`.
2. **Validación en Servidor en la Vista:** `agregar_cancion` comprueba `cancion.propietario == request.user`; ante discrepancia, arroja `PermissionDenied`.
3. **Validación en el Modelo:** `FogataCancion.clean()` y `FogataCancion.save()` verifican que `fogata.propietario_id == cancion.propietario_id`. Si difieren, lanza `ValidationError`.

---

## 6. Sesión, Logout y Política de Caché Privada

### 6.1 Logout Seguro por POST
* La acción de cierre de sesión está restringida a peticiones `POST` con token CSRF válido (`apps.core.views.logout_view`).
* Peticiones `GET` a `/logout/` son rechazadas (redirigen a inicio sin alterar la sesión).

### 6.2 Middleware de No-Caché Privado (`PrivateCacheMiddleware`)
Para impedir que navegadores o cachés intermedias conserven páginas privadas si la sesión expira o si el dispositivo cambia de usuario:
* Todas las respuestas emitidas a usuarios autenticados incorporan automáticamente:
  ```http
  Cache-Control: no-store, private, no-cache, must-revalidate
  Pragma: no-cache
  ```
* Esto neutraliza la recuperación indebida de contenido privado a través del botón Atrás/Adelante (*Back/Forward Cache*) tras cerrar sesión.

---

## 7. Suspensión Preventiva de Offline Privado (PWA en Fase 6)

Siguiendo las directrices críticas de los **Requisitos 11 y 12**:

* **Decisión:** Para este primer piloto externo se deshabilitó temporalmente el almacenamiento persistente de letras, canciones y Fogatas privadas en `CacheStorage` (`fogata-offline`).
* **Justificación de Seguridad:** En un entorno multiusuario donde múltiples personas pueden usar el mismo dispositivo o donde las cookies pueden expirar sin que se invoque el flujo de logout, `CacheStorage` representa un riesgo de filtración local hasta que se diseñe una arquitectura de cifrado y aislamiento local multiusuario.
* **Service Worker (`static/js/sw.js` v2):**
  - Almacena exclusivamente recursos técnicos públicos: CSS, JS, manifest, iconos y el App Shell técnico.
  - Al activarse, elimina proactivamente la caché `fogata-offline` de versiones previas.
  - Las peticiones de navegación HTML utilizan **Network Only**. Si no hay señal de red, se muestra la pantalla informativa `/offline/` explicando con sobriedad que la biblioteca privada requiere conexión activa.
* **Interfaz:** Se suspendió el panel y el botón `⬇ Disponible sin conexión` de la vista de detalle de Fogatas.

---

## 8. Flujo Ciego de Recuperación de Contraseña

En `FogataPasswordResetView` y sus plantillas asociadas:
* Al enviar el formulario de recuperación con cualquier correo (registrado o inexistente), la aplicación muestra exactamente la misma respuesta:
  > *«Si existe una cuenta asociada a ese correo, recibirás instrucciones para restablecer tu contraseña.»*
* Esto previene ataques de enumeración de usuarios (*user enumeration*).
* La configuración SMTP proviene íntegramente de variables de entorno (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`).

---

## 9. Experiencia de Usuario: Landing y Onboarding

* **Usuario Anónimo (`/`):** Landing minimalista y directa:
  ```text
  Fogata 🔥
  Tus canciones. Tus acordes. Tu sesión.
  Atril digital para guitarra.
  [ Crear cuenta ]  [ Iniciar sesión ]
  ```
* **Primer Usuario sin Repertorio (`canciones.count() == 0`):**
  ```text
  Bienvenido a Fogata 🔥
  Agrega tu primera canción.
  "Copia la letra y los acordes desde donde normalmente los utilizas,
   pégalos aquí y comienza a tocar."
  [ + Agregar primera canción ]
  ```
* **Usuario con Repertorio:** Listados esenciales de *Mis canciones* y *Mis Fogatas* con acceso directo y botones de acción rápida, sin saturación de estadísticas innecesarias.

---

## 10. Django Admin y Métricas de Auditoría

En el panel `/admin/`:
* Se personalizó `CustomUserAdmin` mostrando:
  - Correo / Nombre
  - Fecha de alta (`date_joined`)
  - Último login (`last_login`)
  - Métrica en vivo de canciones (`numero_canciones`)
  - Métrica en vivo de Fogatas (`numero_fogatas`)
  - Código de invitación utilizado (`codigo_invitacion_usado`) a través del inline `PerfilPiloto`.
* Se registró el modelo `InvitacionAdmin` con monitoreo de usos actuales vs cupo máximo y estado de vigencia.

---

## 11. Hardening y Configuración de Producción

En `config/settings.py`:
* **Fallo al Iniciar en Producción Insegura:** Si `DEBUG=False` y falta `DJANGO_SECRET_KEY` o `DJANGO_ALLOWED_HOSTS`, el servidor aborta inmediatamente el inicio con `ImproperlyConfigured`.
* **Cookies Seguras:** Cuando `DEBUG=False`:
  - `SESSION_COOKIE_SECURE = True`
  - `CSRF_COOKIE_SECURE = True`
  - `SESSION_COOKIE_HTTPONLY = True`
  - `SECURE_CONTENT_TYPE_NOSNIFF = True`
  - `X_FRAME_OPTIONS = 'DENY'`

---

## 12. Resultados de las Pruebas Automatizadas

Se ejecutó la suite completa de pruebas unitarias, integradas y adversariales del proyecto:

```bash
.venv/bin/python manage.py test
```

### Resumen del Reporte:
* **Total de pruebas ejecutadas:** **112 tests**
* **Fallos:** **0**
* **Errores:** **0**
* **Tiempo de ejecución:** **13.33s**

### Cobertura de Fase 6 (`apps/core/tests_fase6.py` - 24 tests específicos):
1. `test_listados_estrictamente_aislados`: A no ve contenido de B. (PASS)
2. `test_idor_lectura_cancion_ajena_retorna_404`: Detalle, atril y acordes ajenos devuelven 404. (PASS)
3. `test_idor_modificacion_cancion_ajena_retorna_404`: Edición y borrado ajeno devuelven 404. (PASS)
4. `test_idor_lectura_fogata_ajena_retorna_404`: Detalle y atril de Fogata ajena devuelven 404. (PASS)
5. `test_idor_modificacion_fogata_ajena_retorna_404`: Edición y borrado de Fogata ajena devuelven 404. (PASS)
6. `test_idor_compartir_sesion_fogata_ajena_retorna_404`: Generar sesión en Fogata ajena devuelve 404. (PASS)
7. `test_1_formulario_filtra_solo_canciones_propias`: Queryset restringido por propietario. (PASS)
8. `test_2_post_forzado_a_servidor_es_rechazado`: Inyección de canción ajena en POST es rechazada. (PASS)
9. `test_3_modelo_rechaza_asociacion_cruzada`: `clean()` y `save()` lanzan ValidationError ante cruce. (PASS)
10. `test_registro_normaliza_email_a_minusculas_y_asigna_username`: Normalización comprobada. (PASS)
11. `test_no_permite_registro_duplicado_insensible_a_mayusculas`: Correo duplicado rechazado. (PASS)
12. `test_login_insensible_a_mayusculas`: Inicio de sesión case-insensitive validado. (PASS)
13. `test_consumo_hasta_max_usos`: Consumo atómico agota cupos exactamente. (PASS)
14. `test_invitacion_expirada_es_rechazada`: Expiración temporal verificada. (PASS)
15. `test_invitacion_desactivada_es_rechazada`: Invitación inactiva rechazada. (PASS)
16. `test_registro_no_confia_en_query_string`: Parámetros GET no validan el POST. (PASS)
17. `test_logout_por_get_no_cierra_sesion`: GET inocuo en logout. (PASS)
18. `test_logout_por_post_cierra_sesion_y_redirige`: POST invalida la sesión. (PASS)
19. `test_sesion_expirada_redirige_a_login`: Redirección 302 ante sesión no autenticada. (PASS)
20. `test_cabeceras_no_store_private_en_vistas_autenticadas`: Cache-Control auditado en todas las vistas privadas. (PASS)
21. `test_password_reset_respuesta_visual_identica`: Respuesta ciega contra enumeración. (PASS)
22. `test_landing_publica_anonima`: Vista sobria pública verificada. (PASS)
23. `test_bienvenida_primer_usuario_sin_canciones`: Empty state motivacional. (PASS)
24. `test_home_con_repertorio`: Vista privada operativa con canciones. (PASS)

### Validación de Sintaxis JavaScript:
```bash
node -c static/js/fogata.js
node -c static/js/sw.js
# Ambas finalizadas con código de salida 0 (sin errores sintácticos)
```

---

## 13. Limitaciones Conocidas y Alcance

* **Offline Privado Suspendido:** Los repertorios privados de los usuarios piloto operan exclusivamente con conexión a internet y sesión activa. La aplicación base (App Shell) y el catálogo general de 64 digitaciones de acordes permanecen disponibles offline. El soporte offline multiusuario seguro será abordado en una fase posterior.
* **Sin Features de Red Social:** No existen perfiles públicos, comentarios, biblioteca comunitaria ni opciones para compartir canciones entre cuentas privadas, conforme a las restricciones acordadas para la Fase 6.
* **Sesiones Compartidas de Invitados:** Las sesiones compartidas para tocar en vivo mediante `/s/<token>/` se mantienen públicas y anónimas para invitados con expiración temporal o revocación manual por parte del dueño.

---

## 14. Conclusión y Recomendación

La **Fase 6 — Piloto Multiusuario, Registro e Inicio de Sesión** se encuentra íntegramente implementada y validada contra todos los criterios de seguridad, concurrencia y aislamiento estricto de datos.

Se ha dejado preconfigurada la invitación `PILOTO2026` con 25 usos disponibles para las primeras pruebas controladas.

Se recomienda proceder con la breve **Fase 6.1 de Validación Adversarial (Release Gate)** antes de distribuir masivamente las invitaciones a usuarios externos.
