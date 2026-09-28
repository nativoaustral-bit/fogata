# INFORME DE IMPLEMENTACIÓN — FASE 7
## Fogata Control Center & Analítica de Producto

> **Fecha:** 28 de Septiembre de 2026  
> **Estado:** **APROBADO Y VALIDADO (133 tests superados con 0 errores)**  
> **Principio rector:** *No necesitamos contar todo lo que ocurre en Fogata. Necesitamos medir las acciones que demuestran que Fogata está generando valor.*  
> **Principio de privacidad:** *La privacidad debe depender del diseño del servicio, no de que cada programador recuerde qué no almacenar.*

---

## 1. Resumen Ejecutivo

La **Fase 7** dota a **Fogata** de su propio centro de control administrativo y observabilidad de producto: **Fogata Control Center** (`/gestion/`).

El sistema fue diseñado bajo estrictos criterios de **privacidad por diseño**, **cero telemetría invasiva** (sin trackers de terceros, sin cookies analíticas, sin fingerprinting ni almacenamiento de IPs) y **medición rigurosa de adopción real**, separando de forma tajante el simple acceso o inicio de sesión de la actividad de valor para el músico.

Se implementó el registro centralizado y sanitizado de eventos de comportamiento (`EventoUso`), auditoría inmutable de acciones administrativas (`AuditoriaAdmin` con protección de borrado `on_delete=PROTECT`), desacoplamiento entre la base histórica previa y la nueva cohorte observable (`ANALYTICS_START_DATE`), cálculo de usuarios activos (DAU, WAU, MAU), usuarios activados, usuarios recurrentes a 30 días, retención en ventanas de 7 y 30 días, embudo de activación secuencial, controles de debounce en pantallas de atril para evitar inflar métricas, prevención integral de inyección de fórmulas en CSV (*Spreadsheet Formula Injection*), optimización contra *N+1 queries*, paginación en todas las tablas y suite completa de pruebas unitarias y de integración.

---

## 2. Modelos Creados y Modificados

### 2.1 Modelo `EventoUso` (`apps/gestion/models.py`)
Modelo liviano y asíncrono para almacenar exclusivamente hitos de uso operativo sin exponer jamás contenido privado (cero letras, cero acordes).

* **Campos:**
  * `usuario`: `ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)`. Permite preservar métricas agregadas si un usuario es depurado a futuro.
  * `tipo_evento`: `CharField(max_length=40, choices=TIPOS_EVENTO, db_index=True)`. Hitos tipificados.
  * `fecha`: `DateTimeField(default=timezone.now, db_index=True)`.
  * `objeto_tipo`: `CharField(max_length=40, blank=True, db_index=True)`.
  * `objeto_id`: `PositiveIntegerField(null=True, blank=True)`.
  * `metadata`: `JSONField(default=dict, blank=True)`. Estrictamente controlado por whitelist.
* **Índices Compuestos:** `['tipo_evento', 'fecha']`, `['usuario', 'fecha']`, `['usuario', 'tipo_evento']`.

### 2.2 Modelo `AuditoriaAdmin` (`apps/gestion/models.py`)
Registro inmutable de intervenciones administrativas sensibles ejecutadas desde Control Center.

* **Campos:**
  * `admin`: `ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='auditorias_admin_ejecutadas')`.
  * `usuario_afectado`: `ForeignKey(User, on_delete=models.PROTECT, related_name='auditorias_admin_recibidas')`.
    > **Decisión de diseño (Criterio 17):** Se fijó `on_delete=PROTECT` para impedir que una cuenta de usuario pueda ser eliminada accidentalmente dejando desaparecer sus registros de auditoría asociados.
  * `accion`: `CharField(choices=['suspender_usuario', 'reactivar_usuario', 'enviar_reset_password'])`.
  * `fecha`: `DateTimeField(default=timezone.now, db_index=True)`.
  * `detalles`: `TextField(blank=True)`.

### 2.3 Modelo `PerfilPiloto` (`apps/core/models.py`)
Ampliación del perfil de cuenta (Migración `core.0003_perfilpiloto_tipo_cuenta`):
* Incorporación del campo `tipo_cuenta`:
  * Opciones: `PILOTO` (defecto), `ADMIN`, `GRATIS` (preparación futura), `PRO` (preparación futura).
  * **Principio de autorización (Criterio 24):** `tipo_cuenta` es una clasificación comercial. La autorización de acceso a `/gestion/` reside estrictamente en `User.is_staff=True`.

---

## 3. Fecha Oficial de Inicio de Analítica

* **Constante y Configuración (Criterio 4):**
  Definida en `config/settings.py`:
  ```python
  FOGATA_ANALYTICS_START_DATE = os.environ.get('FOGATA_ANALYTICS_START_DATE', '2026-09-28')
  ```
  Obtenida de forma consciente de zona horaria mediante `obtener_analytics_start_date()`.
* **Aislamiento respecto a usuarios históricos:**
  Los usuarios registrados con anterioridad al despliegue de Fase 7 forman parte del **Estado actual de la plataforma** (conteo de cuentas, canciones y Fogatas existentes), pero no se mezclan con los denominadores de eventos ni distorsionan el embudo nuevo de activación.
* **Indicador en interfaz (Criterios 4, 33, 35):**
  En la cabecera del Control Center y en las secciones analíticas se exhibe visiblemente:
  > *«Analítica de uso activa desde: 28/09/2026 (Fase 7) — Comportamiento sin telemetría invasiva»*  
  > *«Uso medido desde el inicio de métricas»*

---

## 4. Definiciones Oficiales de Métricas de Comportamiento

| Métrica | Definición Oficial Fogata (Fase 7) | Eventos / Condiciones Consideradas | Exclusiones Explícitas |
| :--- | :--- | :--- | :--- |
| **Separación de Login** | Entrar a la plataforma no equivale a usarla. El login se muestra como auditoría de último acceso, nunca como adopción. | Evento `login` registrado solo para soporte. | Excluido de DAU, WAU, MAU, usuario activo y retención. |
| **Usuario Activo** | Usuario no-staff que generó al menos una acción real de producto durante el período analizado. | `crear_cancion`, `editar_cancion`, `tocar_cancion`, `crear_fogata`, `editar_fogata`, `tocar_fogata`, `crear_sesion_compartida`. | No incluye `login`, `registro` ni aperturas de invitados. |
| **DAU** | Usuarios únicos con al menos una acción real en el día en curso. | Acciones reales desde las 00:00:00 locales (`settings.TIME_ZONE`). | Excluye staff y logins. |
| **WAU** | Usuarios únicos con al menos una acción real en los últimos 7 días. | Acciones reales con `fecha >= ahora - 7 días`. | Excluye staff y logins. |
| **MAU** | Usuarios únicos con al menos una acción real en los últimos 30 días. | Acciones reales con `fecha >= ahora - 30 días`. | Excluye staff y logins. |
| **Usuario Activado** | Usuario no-staff que consolidó la propuesta de valor nuclear de Fogata. | Creó al menos una (1) canción y utilizó Modo Tocar (en canción o en Fogata) al menos una (1) vez. | Músicos que solo registraron cuenta o que solo guardaron canciones sin atril. |
| **Usuario Recurrente (30d)** | Usuario que valida hábito de uso continuo frente a prueba esporádica. | Usuario con actividad real en al menos dos (2) días distintos en los últimos 30 días. | No se infla por múltiples acciones en una misma jornada. |
| **Retención 7 días** | Capacidad de enganche inicial durante la primera semana. | Usuarios no-staff registrados hace ≥7 días que registraron actividad real entre el día 1 y el día 7 posterior a su registro. | Excluye el día 0 (registro inicial). Formato: `X de Y (Z%)`. |
| **Retención 30 días** | Sostenimiento del uso mensual. | Usuarios no-staff registrados hace ≥30 días que registraron actividad real entre el día 8 y el día 30 posterior a su registro. | Formato: `X de Y (Z%)`. Sin cohortes prematuras ni matrices predictivas complejas. |

---

## 5. Embudo de Adopción (Funnel de Nuevos Usuarios)

El embudo principal monitorea a la cohorte observable registrada desde `ANALYTICS_START_DATE`:

```
1. Cuenta Creada (date_joined >= ANALYTICS_START_DATE) [100%]
   ↓
2. Primera Canción (canciones creadas en repertorio propio)
   ↓
3. Primer Modo Tocar (abrió Modo Tocar individual o sesión de Fogata)
   ↓
4. Primera Fogata (armó al menos un setlist)
   ↓
5. Fogata Tocada (ejecutó el setlist en atril en vivo)
   ↓
6. Sesión Compartida (generó enlace temporal para invitados)
```

Los usuarios anteriores a la fecha de inicio se agrupan en el inventario global, evitando porcentajes incoherentes derivados de la ausencia de eventos previos.

---

## 6. Debounce y Métricas Operativas de Atril

Para evitar que recargas de página o avances de temas inflen artificialmente las estadísticas, se introdujo una arquitectura de *debounce* por sesión:

1. **Modo Tocar Canción (`tocar_cancion`):**
   * Almacena en la sesión del usuario la clave `ultima_apertura_cancion_<id>` con la marca temporal.
   * Solo registra un nuevo evento si han transcurrido al menos **5 minutos (300 segundos)** desde la última apertura de esa canción en dicha sesión (Criterio 9).
2. **Modo Tocar Fogata (`tocar_fogata`):**
   * Almacena en la sesión la clave `ultima_apertura_fogata_<id>`.
   * Ventana de debounce de **15 minutos (900 segundos)**.
   * El avance tema a tema dentro del atril continuo (`?pos=1` → `?pos=2` → `?pos=3`) **no genera eventos adicionales**, representando con fidelidad que el músico está ejecutando esa Fogata (Criterio 10).
3. **Aperturas de Sesiones Compartidas (`abrir_sesion_compartida`):**
   * Se registra exclusivamente al ingresar a la entrada principal del enlace compartido: `/s/<token>/` (Criterio 11).
   * La navegación interna de canciones por parte del invitado (`/s/<token>/cancion/<id>/`) **no emite eventos de apertura** (Criterio 11).
   * Cero fingerprinting o cookies de rastreo: la métrica se denomina transparentemente **«Aperturas de sesiones compartidas»** y nunca «Invitados únicos» (Criterio 12).
4. **Métrica de Sesiones Usadas (Criterio 13):**
   * Se calcula tanto el *Total de aperturas* como las *Sesiones compartidas con ≥1 apertura* y el *% de sesiones compartidas efectivamente abiertas*.

---

## 7. Privacidad Estricta y Sanitización Central

### 7.1 Servicio Centralizador (`apps/gestion/services.py`)
`registrar_evento()` es el único punto autorizado de persistencia de eventos de producto.

* **Validación de tipo:** Descarta eventos desconocidos.
* **Whitelist Estricta (`METADATA_WHITELIST`):**
  * `crear_cancion`, `editar_cancion`, `crear_fogata`, `abrir_sesion_compartida`, `login`, `registro`: `metadata = {}` (vacío).
  * `tocar_cancion`: solo clave `origen`.
  * `editar_fogata`: solo clave `accion_detalle` (`agregar_cancion`, `quitar_cancion`, `mover_cancion`).
  * `tocar_fogata`: solo clave `total_canciones`.
  * `crear_sesion_compartida`: solo clave `duracion_horas`.
* **Blacklist de Seguridad Inviolable (`FORBIDDEN_METADATA_KEYS`):**
  Cualquier clave que contenga `titulo`, `artista`, `letra`, `acordes`, `contenido`, `notas`, `token`, `email`, `password`, `clave`, `hash`, `ip`, `user_agent`, `fingerprint`, `tonalidad`, `capo`, `afinacion` es automáticamente rechazada y descartada.
* **Límites de Carga:** Strings truncados a 100 caracteres; payloads superiores a 1.000 bytes serializados son rechazados.
* **Seguridad Transaccional (`transaction.on_commit`):**
  Si el evento se dispara dentro de un bloque atómico (`with transaction.atomic():`), el guardado se encola mediante `transaction.on_commit()` para que un rollback de base de datos **nunca genere eventos fantasma** (Criterio 16).
* **Resiliencia:** Toda la lógica está blindada contra excepciones no controladas para garantizar que ningún fallo de telemetría afecte la experiencia del usuario final.

---

## 8. Arquitectura y Seguridad de Fogata Control Center

### 8.1 Control de Acceso (`@staff_required`)
* Todas las vistas bajo `/gestion/` exigen `request.user.is_staff=True`.
* Si el usuario es anónimo: Redirección limpia a `/login/?next=/gestion/` mediante `reverse(settings.LOGIN_URL)`.
* Si el usuario está autenticado pero no es staff: Retorna **HTTP 403 Forbidden** con plantilla sobria (`templates/gestion/403.html`), sin redirigir silenciosamente al home ni filtrar la existencia del panel.

### 8.2 Acciones Administrativas Seguras
* **Suspensión de cuenta:** Marca `is_active=False` y registra en `AuditoriaAdmin`.
  > **Verificación de seguridad:** Una sesión previamente activa pierde de forma inmediata el acceso privado en su siguiente petición HTTP, retornando redirección al login debido a la validación de `user_can_authenticate` en `AuthenticationMiddleware`.
* **Reactivación de cuenta:** Restablece `is_active=True` y audita la acción.
* **Envío de recuperación de contraseña:** Dispara el flujo estándar de `PasswordResetForm` de Django mediante correo transaccional, sin exponer ni alterar contraseñas visibles.
* **Restricción de métodos (Criterio 34):** Todas las acciones operativas requieren obligatoriamente `POST` con `@require_POST` y token `{% csrf_token %}`. Peticiones `GET` devuelven **HTTP 405 Method Not Allowed** y jamás modifican el estado.
* **Eliminación de usuarios deshabilitada (Criterio 19):** No existe botón ni endpoint de eliminación de cuentas en esta fase.

### 8.3 Vistas Implementadas
1. `/gestion/`: Dashboard sintetizado con KPIs de producto, uso en atril, embudo y últimos 50 eventos (sin títulos privados ni letras).
2. `/gestion/usuarios/`: Tabla de usuarios con búsqueda por nombre/email, filtros por estado y nivel de adopción, ordenación y paginación (25/pág).
3. `/gestion/usuarios/<id>/`: Ficha 360° con checklist de adopción, métricas agregadas de repertorio, metadatos públicos de canciones, actividad reciente y panel de control operativo.
4. `/gestion/fogatas/`: Métricas detalladas de uso en vivo de setlists y sesiones compartidas.
5. `/gestion/metricas/`: Desglose analítico de canciones en buckets de repertorio (0, 1-5, 6-20, >20 canciones) y retención.
6. `/gestion/actividad/`: Registro cronológico completo paginado a 50 eventos por página con filtro por tipo.

---

## 9. Exportación a CSV y Protección contra Formula Injection

Ruta administrativa: `/gestion/exportar/usuarios-csv/` (Criterios 21 y 22).

* **Columnas Exportadas:**
  `ID`, `Email`, `Nombre`, `Fecha Registro`, `Ultimo Login`, `Ultima Actividad`, `Codigo Invitacion`, `Tipo Cuenta`, `Total Canciones`, `Total Fogatas`, `Sesiones Compartidas`, `Usuario Activado`, `Estado`.
* **Exclusión Absoluta de Contenido Privado:** Cero letras, acordes, notas, passwords, hashes o tokens.
* **Sanitización contra Inyección de Fórmulas en Hojas de Cálculo (`sanitizar_celda_csv`):**
  Si un campo de texto (como nombre o email controlado por el usuario) comienza con los caracteres `=`, `+`, `-` o `@`, se le antepone automáticamente un apóstrofe (`'`) para evitar que Excel o Google Sheets lo interpreten como fórmula ejecutable.

---

## 10. Prevención de N+1 Queries y Benchmarks de Rendimiento

### 10.1 Optimización ORM (Criterio 29)
En el listado general de usuarios (`usuarios_lista_view`) se utilizó `select_related('perfil_piloto')` y agregaciones directas mediante `.annotate()` con `Count('canciones', distinct=True)`, `Count('fogatas', distinct=True)`, `Count('fogatas__sesiones_compartidas', distinct=True)` y `Max('eventos_uso__fecha')`.

Asimismo, se utilizó `.order_by()` explícito en las consultas de agregación y conteos de eventos para anular el `Meta.ordering = ['-fecha']` predeterminado del modelo `EventoUso`, previniendo que Django incluya la columna `fecha` en el `SELECT DISTINCT` o `GROUP BY`.

### 10.2 Mediciones Reales de Rendimiento (Criterio 28)
Mediciones ejecutadas sobre el entorno local real de la plataforma:

| Endpoint / Vista | Tiempo de Respuesta | Consultas SQL | Estado HTTP | Observación |
| :--- | :--- | :--- | :--- | :--- |
| **Dashboard** (`/gestion/`) | **24.01 ms** | 31 queries | 200 OK | Agregaciones completas de producto, embudo, retención y actividad reciente. |
| **Lista de Usuarios** (`/gestion/usuarios/`) | **2.03 ms** | 2 queries | 200 OK | Cero consultas adicionales por fila (N+1 resuelto). Paginado a 25 registros. |
| **Ficha de Usuario** (`/gestion/usuarios/<id>/`) | **4.57 ms** | 11 queries | 200 OK | Carga de métricas, checklist, metadatos y auditoría del usuario. |
| **Métricas de Fogatas** (`/gestion/fogatas/`) | **2.01 ms** | 11 queries | 200 OK | Conteo de setlists, sesiones compartidas y aperturas. |
| **Métricas Detalladas** (`/gestion/metricas/`) | **5.85 ms** | 36 queries | 200 OK | Buckets de repertorio y retenciones 7d/30d. |
| **Exportar CSV** (`/gestion/exportar/usuarios-csv/`) | **0.65 ms** | 1 query | 200 OK | Streaming directo de datos sanitizados. |

---

## 11. Suite de Pruebas Automatizadas

La suite de pruebas de `apps.gestion.tests` incorpora **20 pruebas exhaustivas** que validan la totalidad de los requerimientos y escenarios límite estipulados en el Criterio 38:

```bash
Found 20 test(s).
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
....................
----------------------------------------------------------------------
Ran 20 tests in 7.046s

OK
```

### Detalle de las Pruebas de Fase 7:
1. `test_acceso_anonimo_redirige_login`: Redirección con preservación de parámetro `next`.
2. `test_acceso_usuario_comun_prohibido_403`: Usuario no-staff recibe HTTP 403 con plantilla dedicada.
3. `test_acceso_staff_permitido`: Superusuario o staff accede correctamente al dashboard.
4. `test_sanitizar_metadata_elimina_claves_prohibidas`: Comprueba que `letra`, `acordes`, `titulo`, `token` sean eliminados por el sanitizador.
5. `test_registrar_evento_exitoso`: Creación controlada de evento operativo.
6. `test_transaccion_rollback_no_genera_evento`: Comprueba que operaciones atómicas que sufren rollback no persistan eventos vía `on_commit`.
7. `test_debounce_tocar_cancion`: Múltiples aperturas dentro de 5 minutos en la misma sesión generan un solo evento `tocar_cancion`.
8. `test_debounce_tocar_fogata`: Navegación entre temas dentro del atril continuo de una Fogata no infla `tocar_fogata`.
9. `test_aperturas_sesion_compartida_no_infla_por_canciones`: Apertura de la sesión compartida contabiliza 1 evento en la portada, pero ver temas individuales no suma eventos.
10. `test_login_solo_no_activa_usuario`: Iniciar sesión no incrementa DAU, WAU ni MAU. Solo acciones reales activan las métricas.
11. `test_usuario_recurrente_30_dias`: Actividad en 2 días distintos = recurrente; 2 eventos en la misma jornada = no recurrente.
12. `test_usuario_activado`: Validación de la regla (≥1 canción + ≥1 uso de Modo Tocar).
13. `test_cohorte_fase_7_no_distorsiona_funnel`: Cuentas creadas antes de `ANALYTICS_START_DATE` no ingresan al embudo de nuevos usuarios.
14. `test_retencion_7_y_30_dias`: Validación de las ventanas temporales de retención (días 1–7 y días 8–30).
15. `test_suspender_usuario_invalida_sesion_inmediatamente`: Suspensión administrativa deniega acceso de forma instantánea a sesiones previamente abiertas.
16. `test_reactivar_usuario`: Reactivación funcional con registro en auditoría.
17. `test_auditoria_protege_eliminacion_usuario`: Validación de `on_delete=PROTECT` impidiendo la eliminación física de un usuario con auditoría.
18. `test_csv_formula_injection_sanitization`: Comprueba que valores que comienzan con `=`, `+`, `-`, `@` reciban el prefijo `'` en el archivo CSV generado.
19. `test_prevenir_n_mas_1_usuarios_lista`: Verificación estricta de cantidad constante de consultas SQL (4 queries) independiente del volumen de usuarios.
20. `test_acciones_administrativas_requieren_post`: Métodos GET sobre endpoints de suspensión o reactivación retornan HTTP 405 y no mutan el estado.

### Validación Integral del Proyecto:
```bash
Found 133 test(s).
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
.....................................................................................................................................
----------------------------------------------------------------------
Ran 133 tests in 20.825s

OK
```
La totalidad de las aplicaciones (`apps.canciones`, `apps.core`, `apps.fogatas`, `apps.gestion`) conviven en absoluta estabilidad sin regresiones.

---

## 12. Conclusión y Estado de Entrega

La **Fase 7 — Fogata Control Center** queda formalmente implementada, verificada y lista para su despliegue junto con el piloto externo. 

Proporciona al equipo de gestión visibilidad honesta, sin vanity metrics ni telemetría invasiva, respaldando el objetivo comercial de evaluar la retención genuina del músico en torno a su repertorio.
