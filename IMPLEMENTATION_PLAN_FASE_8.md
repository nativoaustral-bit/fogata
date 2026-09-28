# IMPLEMENTATION PLAN — FASE 8: MODELO FREEMIUM, PLANES Y LÍMITES
## Fogata Commercial Engine & Capacity Management

> **Fecha:** 28 de Septiembre de 2026  
> **Estado:** **PROPUESTA PARA REVISIÓN**  
> **Principio rector:** *Fogata Gratis debe ser suficientemente buena para enamorarse del producto. Fogata Pro debe aparecer cuando el repertorio del músico comienza a crecer.*  
> **Diferenciador comercial:** *Capacidad, no funcionalidad.*

---

## 1. Servicio Central de Límites (`apps/core/planes.py`)

Para cumplir con el principio de **«Una sola fuente de verdad para los límites del plan»**, se creará el módulo de servicio `apps/core/planes.py`. Ninguna vista, plantilla o API consultará modelos de forma ad-hoc ni dispersará lógica condicional.

### Funciones nucleares:
```python
def obtener_tipo_cuenta(user) -> str:
    """
    Retorna el tipo de cuenta efectivo del usuario:
    - Si user.is_staff o user.is_superuser: 'ADMIN'
    - Si no autenticado: 'ANONIMO'
    - En base a PerfilPiloto.tipo_cuenta: 'ADMIN', 'PILOTO', 'PRO', 'GRATIS'
    """

def limite_canciones(user) -> Optional[int]:
    """Retorna None si es ilimitado (ADMIN, PILOTO, PRO), o settings.FOGATA_FREE_MAX_SONGS si es GRATIS."""

def limite_fogatas(user) -> Optional[int]:
    """Retorna None si es ilimitado (ADMIN, PILOTO, PRO), o settings.FOGATA_FREE_MAX_FOGATAS si es GRATIS."""

def canciones_utilizadas(user) -> int:
    """Conteo exacto de canciones propias creadas por el usuario."""

def fogatas_utilizadas(user) -> int:
    """Conteo exacto de Fogatas propias creadas por el usuario."""

def puede_crear_cancion(user) -> bool:
    """Determina si el usuario tiene cupo disponible para crear una nueva canción."""

def puede_crear_fogata(user) -> bool:
    """Determina si el usuario tiene cupo disponible para crear una nueva Fogata."""

def obtener_estado_capacidad(user) -> dict:
    """
    Helper omnicomprensivo para vistas y templates:
    {
        'tipo_cuenta': 'GRATIS'|'PRO'|'PILOTO'|'ADMIN',
        'nombre_plan': 'Fogata Gratis'|'Fogata Pro'|'Piloto'|'Administrador',
        'es_ilimitado': bool,
        'canciones_usadas': int,
        'canciones_limite': Optional[int],
        'canciones_disponibles': Optional[int],
        'puede_crear_cancion': bool,
        'sobre_limite_canciones': bool,
        'fogatas_usadas': int,
        'fogatas_limite': Optional[int],
        'puede_crear_fogata': bool,
        'sobre_limite_fogatas': bool,
        'es_cercano_limite_canciones': bool, # 8 o 9 canciones
    }
    """
```

---

## 2. Comportamiento por Tipo de Cuenta

| Tipo de Cuenta | Límite Canciones | Límite Fogatas | Funciones Musicales | Justificación Estratégica |
| :--- | :---: | :---: | :--- | :--- |
| **`ADMIN`** | **∞** (Ilimitado) | **∞** (Ilimitado) | 100% disponibles | Control técnico y operacional del sistema. Independiente de la clasificación comercial. |
| **`PILOTO`** | **∞** (Ilimitado) | **∞** (Ilimitado) | 100% disponibles | Cuentas existentes del piloto externo. Se comportan temporalmente como **PRO sin cobro** para no interrumpir pruebas ni degradar usuarios iniciales. |
| **`PRO`** | **∞** (Ilimitado) | **∞** (Ilimitado) | 100% disponibles | Modalidad comercial completa para músicos con repertorios en expansión. |
| **`GRATIS`** | **10** canciones | **1** Fogata | 100% disponibles | Permite enamorarse del producto y tocar en vivo sin fricción técnica. Restringe solo capacidad. |

* **Nuevos registros:** A partir de la activación comercial, todo nuevo usuario registrado mediante `/registro/` se creará con `tipo_cuenta = 'GRATIS'`.
* **Usuarios existentes:** Conservan intacto su estado (`ADMIN` para staff, `PILOTO` para usuarios actuales).

---

## 3. Límite de Canciones (Experiencia de Usuario y Servidor)

### 3.1 Flujo de Usuario Gratis (0 a 9 canciones)
* Flujo habitual sin interrupciones.
* Cuando el usuario tiene 8 o 9 canciones: En la vista de canciones (`/canciones/`) se muestra una tarjeta sutil, elegante y no intrusiva:
  > *«Tu repertorio está creciendo (8/10 canciones). Con Fogata Pro puedes guardar canciones ilimitadas. [Conocer Pro]»*

### 3.2 Flujo al alcanzar 10 canciones
* Si un usuario con 10 canciones pulsa **«+ Nueva canción»** (`GET /canciones/nueva/`):
  * **NO** se muestra un error técnico 403 ni mensaje hostil.
  * Se renderiza la plantilla comercial empática: `templates/canciones/limite_alcanzado.html`.
  * **Contenido exacto:**
    ```text
    Tu repertorio está creciendo 🔥
    En Fogata Gratis puedes guardar hasta 10 canciones.
    Con Fogata Pro puedes guardar todas las canciones que quieras.

    [ Conocer Fogata Pro ]
    [ Volver a mis canciones ]
    ```
  * Se registra el evento de intención comercial: `alcanzar_limite_canciones`.

### 3.3 Defensa en Servidor (`POST /canciones/nueva/`)
* Si el cliente elude la interfaz e intenta enviar un `POST` manual cuando `puede_crear_cancion(user) == False`:
  * La vista intercepta la petición antes de cualquier procesamiento de formulario.
  * Retorna renderizado de `templates/canciones/limite_alcanzado.html` o respuesta JSON estructurada (`{'ok': False, 'error': 'limite_alcanzado', 'redirect': '/pro/'}`) si fue vía AJAX.
  * Se evita cualquier inserción en la base de datos.

---

## 4. Límite de Fogatas (Experiencia de Usuario y Servidor)

### 4.1 Definición de «1 Fogata»
* La limitación es: **1 Fogata almacenada simultáneamente** (concurrente), **NO** una creada una sola vez en la vida.
* El usuario Gratis puede:
  * Cambiarle el nombre y descripción.
  * Agregar, quitar y reordenar canciones tantas veces como quiera.
  * Tocarla en vivo en atril continuo.
  * Compartirla y generar links temporales con invitados.
  * Eliminarla y crear una nueva Fogata desde cero.

### 4.2 Flujo al intentar crear una segunda Fogata
* Si un usuario con 1 Fogata activa pulsa **«+ Nueva Fogata»** (`GET /fogatas/crear/`):
  * Se renderiza la pantalla comercial: `templates/fogatas/limite_alcanzado.html`.
  * **Contenido exacto:**
    ```text
    ¿Otra Fogata? 🔥
    En Fogata Gratis puedes mantener 1 Fogata.
    Con Fogata Pro puedes crear todas las sesiones y repertorios que necesites.

    [ Conocer Fogata Pro ]
    [ Volver a mi Fogata ]
    ```
  * Se registra el evento `alcanzar_limite_fogatas`.

### 4.3 Defensa en Servidor (`POST /fogatas/crear/`)
* Intercepción estricta en servidor ante cualquier `POST` directo cuando `puede_crear_fogata(user) == False`.

---

## 5. Principio de No Bloqueo y Política de Downgrade

### 5.1 Regla Inviolable
> **Nunca bloquear, ocultar, borrar ni restringir el contenido preexistente.**

Si una cuenta pasa de `PRO` (o `PILOTO`) a `GRATIS` y posee, por ejemplo, **35 canciones y 5 Fogatas**:
1. **Acceso Total:** Puede ver, editar, tocar en atril individual, tocar en setlist, transponer y compartir las 35 canciones y las 5 Fogatas.
2. **Restricción Exclusiva:** Solo se deshabilita la creación de **nuevas** canciones (hasta que baje de 10) o **nuevas** Fogatas (hasta que baje de 1).
3. **Comunicación Serena:**
   > *«Tienes más contenido que el límite del plan Gratis (35/10 canciones · 5/1 Fogatas). Todo tu repertorio permanece completamente disponible, pero necesitarás Fogata Pro para seguir agregando canciones o Fogatas.»*

---

## 6. Compartir sigue siendo 100% Gratis

* La generación de enlaces criptográficos temporales (`/s/<token>/`), el QR, la lectura fluida de invitados y el atril para invitados **no tienen restricciones de plan**.
* Esto preserva el motor de viralidad y difusión orgánica de Fogata.

---

## 7. Prevención de Condiciones de Carrera (Concurrencia)

Para evitar sobrepasar el límite de 10 canciones mediante envíos de peticiones simultáneas:
* En `apps/canciones/views.py` y `apps/fogatas/views.py`, la validación de cupo y la creación se ejecutan dentro de un bloque transaccional atómico:
  ```python
  with transaction.atomic():
      # Bloqueo condicional a nivel de cuenta (compatible con SQLite y PostgreSQL)
      perfil = PerfilPiloto.objects.select_for_update().get(user=request.user)
      if not puede_crear_cancion(request.user):
          return render(request, 'canciones/limite_alcanzado.html', ...)
      cancion = form.save(commit=False)
      cancion.propietario = request.user
      cancion.save()
  ```
* En **SQLite** (entorno de pruebas y producción actual), las transacciones de escritura adquieren un bloqueo exclusivo que serializa las escrituras.
* En **PostgreSQL** (arquitectura futura), `select_for_update()` sobre `PerfilPiloto` garantiza aislamiento estricto y serialización por usuario sin bloqueos de tabla.
* Se incorporará un test de concurrencia simulada en la suite de pruebas.

---

## 8. Landing Interna: Página «Fogata Pro» (`/pro/`)

* **Ruta:** `/pro/` (`apps.core.views.pro_view`, nombre de url: `core:pro`).
* **Plantilla:** `templates/core/pro.html`.
* **Diseño y Estética:** Look & feel sobrio, oscuro, cálido y premium propio de Fogata (acordes ámbar/flame sobre fondo charcoal `#121212`).
* **Estructura visual:**
  * Título: **Fogata Pro 🔥**
  * Subtítulo: *Todo tu repertorio. Todas tus Fogatas. Sin límites.*
  * Comparativa de Planes:
    * **Gratis:** Hasta 10 canciones, 1 Fogata, Modo Tocar, Auto-scroll, Transposición, C ↔ Do, Diagramas, Compartir sesiones.
    * **Pro:** Canciones ilimitadas, Fogatas ilimitadas, Todo lo anterior, Soporte preferente.
  * Precios Centralizados:
    * `$5.990 / 6 meses`
    * `$9.990 / año`
    * Leyenda destacada: **«Equivale a menos de $1.000 al mes»**
  * Estado de Pago: Botón `Próximamente` (o contacto directo/activación para pruebas del piloto).
  * Evento de analítica: Emite `ver_pro` con debounce de 15 minutos en sesión.

---

## 9. Precios y Parámetros Comerciales Centralizados

Definidos en `config/settings.py` con lectura opcional de variables de entorno:

```python
# Fase 8 — Parámetros Comerciales y Límites Freemium
FOGATA_FREE_MAX_SONGS = int(os.environ.get('FOGATA_FREE_MAX_SONGS', 10))
FOGATA_FREE_MAX_FOGATAS = int(os.environ.get('FOGATA_FREE_MAX_FOGATAS', 1))
FOGATA_PRO_SEMESTRAL_PRICE_CLP = int(os.environ.get('FOGATA_PRO_SEMESTRAL_PRICE_CLP', 5990))
FOGATA_PRO_ANUAL_PRICE_CLP = int(os.environ.get('FOGATA_PRO_ANUAL_PRICE_CLP', 9990))
```

Formatos monetarios provistos mediante helper o templatetag para evitar discrepancias de puntuación (`$5.990` y `$9.990`).

---

## 10. Integración en Fogata Control Center (`/gestion/`)

### 10.1 Ficha de Usuario (`/gestion/usuarios/<id>/`)
* **Badge del Plan:** `GRATIS`, `PRO`, `PILOTO` o `ADMIN`.
* **Capacidad:**
  * Gratis: `Canciones: 8 / 10` · `Fogatas: 1 / 1`.
  * Pro / Piloto / Admin: `Canciones: 34 / ∞` · `Fogatas: 6 / ∞`.
* **Cambio Manual de Plan (Criterio 17 y 18):**
  * Formulario administrativo exclusivo mediante `POST` con CSRF.
  * Permite conmutar:
    * `GRATIS` → `PRO`
    * `PRO` → `GRATIS`
    * `PILOTO` → `PRO`
  * Registra en `AuditoriaAdmin`:
    * `accion = 'cambiar_plan'`
    * `detalles = f"Plan cambiado de {plan_anterior} a {plan_nuevo} por {admin.email}"`

### 10.2 Métricas Comerciales en Dashboard (`/gestion/`)
* **Distribución de Planes:** Conteo de usuarios `GRATIS`, `PRO` y `PILOTO`.
* **Monitor de Límites:**
  * Usuarios Gratis en zona cercana (8 o 9 canciones).
  * Usuarios Gratis con cupo lleno (10/10 canciones).
  * Usuarios Gratis con Fogata activa (1/1).
* **Señales de Conversión (Demanda real):**
  * Usuarios Gratis que alcanzaron el límite de canciones o intentaron crear la 11ª.
  * Usuarios Gratis que intentaron crear una segunda Fogata.
  * Usuarios que visitaron `/pro/`.
  * Total de **Usuarios con Señal de Conversión** (demanda de upgrade sin duplicados).

### 10.3 Embudo Comercial
Visualización gráfica en Control Center:
```
Usuario Gratis
      ↓
Usuario Activado
      ↓
8+ Canciones en Repertorio
      ↓
Límite de Capacidad Alcanzado (10 canciones o 2ª Fogata)
      ↓
Visitó Página Fogata Pro (/pro/)
      ↓
Convertido a PRO (Upgrade manual en Fase 8)
```

---

## 11. Eventos Comerciales y Privacidad

Nuevos tipos añadidos a `EventoUso.TIPOS_EVENTO`:
* `ver_pro`: Visualización de la landing Pro.
* `alcanzar_limite_canciones`: Intento de creación al tope de capacidad.
* `alcanzar_limite_fogatas`: Intento de creación de segunda Fogata.

### Whitelist Estricta de Metadata:
* `ver_pro`: `{'origen'}` (ej: `'menu'`, `'limite_canciones'`, `'limite_fogatas'`).
* `alcanzar_limite_canciones`: `{'total_actual'}` (entero).
* `alcanzar_limite_fogatas`: `{'total_actual'}` (entero).
* **Cero datos privados:** Jamás ingresan títulos, letras, acordes ni notas musicales.

---

## 12. Migraciones de Base de Datos

* **Migración en `core` (`0004_perfilpiloto_campos_comerciales.py`):**
  Agrega campos no destructivos a `PerfilPiloto`:
  * `fecha_inicio_plan = models.DateTimeField(null=True, blank=True)`
  * `fecha_fin_plan = models.DateTimeField(null=True, blank=True)`
  * `estado_suscripcion = models.CharField(max_length=20, default='ACTIVA', blank=True)`
* **Migración en `gestion` (`0002_eventouso_tipos_comerciales.py`):**
  Actualiza las choices de `EventoUso` y `AuditoriaAdmin` para incorporar `cambiar_plan` y eventos comerciales.
* **Preservación Total:** Cero modificaciones en tablas de `canciones` o `fogatas`.

---

## 13. Suite de Pruebas Automatizadas

Se crearán pruebas exhaustivas para validar cada uno de los puntos exigidos:

1. **Usuario Gratis:**
   * Creación exitosa de canciones 1 a 10.
   * Rechazo de la canción 11 (renderiza pantalla comercial y emite evento).
   * Creación exitosa de 1 Fogata.
   * Rechazo de segunda Fogata (renderiza pantalla comercial y emite evento).
   * Uso irrestricto de Modo Tocar, transposición, diagramas, auto-scroll y compartir con 10 canciones.
2. **Usuario Pro:**
   * Creación exitosa de 11+ canciones y múltiples Fogatas.
3. **Usuario Piloto:**
   * Comportamiento ilimitado idéntico a Pro sin cobro.
4. **Administrador (`is_staff=True`):**
   * Creación ilimitada sin importar su tipo de cuenta comercial.
5. **Defensa ante POST forzado:**
   * `POST /canciones/nueva/` y `POST /fogatas/crear/` manuales cuando el usuario está en el límite son rechazados sin crear registros huérfanos.
6. **Política de Downgrade:**
   * Usuario Pro con 35 canciones pasa a Gratis: sus 35 canciones siguen activas, editables y tocables, pero no puede crear la 36ª.
7. **Control Center y Auditoría:**
   * Endpoint de cambio de plan exige `POST` y `is_staff=True`. Petición `GET` retorna 405.
   * Registro exacto en `AuditoriaAdmin` con plan anterior y nuevo.
8. **Precios Centralizados:**
   * La vista `/pro/` refleja exactamente los valores fijados en `settings.py`.
9. **Eventos Comerciales y Privacidad:**
   * Los eventos comerciales emiten payloads mínimos sanitizados libres de contenido musical.

---

## 14. Plan de Ejecución Paso a Paso

1. **Paso 1: Configuración y Modelos**
   * Configurar constantes de precios y límites en `config/settings.py`.
   * Agregar campos de vigencia futura a `PerfilPiloto` en `apps/core/models.py`.
   * Agregar `cambiar_plan` a `AuditoriaAdmin.ACCIONES` y eventos comerciales a `EventoUso.TIPOS_EVENTO`.
   * Crear y ejecutar migraciones limpias.
2. **Paso 2: Servicio Central de Capacidad (`apps/core/planes.py`)**
   * Implementar `puede_crear_cancion`, `puede_crear_fogata`, `obtener_estado_capacidad`, etc.
   * Modificar `apps/core/views.py` para asignar `tipo_cuenta = 'GRATIS'` a nuevos registros.
3. **Paso 3: Vistas y Pantallas Comerciales**
   * Crear vista y template `/pro/` (`templates/core/pro.html`).
   * Crear plantillas comerciales de límite:
     * `templates/canciones/limite_alcanzado.html`
     * `templates/fogatas/limite_alcanzado.html`
   * Proteger `crear()` en `canciones/views.py` y `fogatas/views.py` con bloqueo transaccional.
   * Agregar avisos sutiles de capacidad en las listas de canciones y Fogatas.
   * Mostrar el plan activo discretamente en el navbar (`templates/base.html`).
4. **Paso 4: Integración en Fogata Control Center**
   * Agregar cambio manual de plan con auditoría en `apps/gestion/views.py`.
   * Actualizar ficha de usuario con desglose de capacidad y selector de plan.
   * Agregar métricas comerciales y funnel en `apps/gestion/metrics.py` y `templates/gestion/dashboard.html`.
5. **Paso 5: Pruebas Automatizadas y Validación**
   * Implementar batería completa de tests en `apps/core/tests.py`, `apps/canciones/tests.py`, `apps/fogatas/tests.py` y `apps/gestion/tests.py`.
   * Ejecutar la suite completa para asegurar 0 fallos y 0 regresiones.
6. **Paso 6: Documentación Final**
   * Generar `INFORME_IMPLEMENTACION_FASE_8.md`.
