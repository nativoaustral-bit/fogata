# FOGATA — INFORME DE IMPLEMENTACIÓN
## Fase 8 — Modelo Freemium, Planes y Límites

**Fecha:** 28 de septiembre de 2026  
**Estado:** ✅ COMPLETADA Y VALIDADA CON ÉXITO  
**Batería de Pruebas:** 154 / 154 pruebas unitarias e integración aprobadas (100% exitosas)  
**Ambiente:** FOGATA (Desarrollo y Servidor de Producción listo para despliegue)

---

### 1. Resumen Ejecutivo

En la **Fase 8** se implementó con éxito la arquitectura comercial del **Modelo Freemium** para la plataforma Fogata, estableciendo la distinción entre cuentas gratuitas y de pago **sin incorporar todavía pasarelas de pago** (reservadas para la Fase 9).

El principio comercial rector se aplicó rigurosamente:
> **"Capacidad, no funcionalidad. Fogata Gratis debe permitir experimentar completamente el valor del producto sin limitaciones artificiales en la experiencia musical."**

---

### 2. Principales Logros y Entregables

#### A. Servicio Central de Límites (`apps/core/planes.py`)
Se consolidó una **única fuente de verdad** para los límites del plan y los permisos comerciales del usuario, evitando lógica dispersa o duplicada:
- `obtener_tipo_cuenta(user)`: Resuelve centralmente `ADMIN`, `PILOTO`, `PRO`, `GRATIS` o `ANONIMO`.
- `limite_canciones(user)`: `None` para cuentas ilimitadas (`ADMIN`, `PILOTO`, `PRO`); `10` para `GRATIS` (extraído dinámicamente de `settings.FOGATA_FREE_MAX_SONGS`).
- `limite_fogatas(user)`: `None` para cuentas ilimitadas; `1` para `GRATIS` (extraído de `settings.FOGATA_FREE_MAX_FOGATAS`).
- `canciones_utilizadas(user)` y `fogatas_utilizadas(user)`: Conteos activos de biblioteca y repertorios.
- `puede_crear_cancion(user, bloquear=False)` y `puede_crear_fogata(user, bloquear=False)`: Validación de cupo con soporte para bloqueo de concurrencia (`select_for_update`).
- `obtener_estado_capacidad(user)`: Diccionario unificado consumido por vistas y plantillas para calcular cuotas, advertencias y banners contextuales.

#### B. Comportamiento por Modalidad de Cuenta
1. **`GRATIS`**: Máximo 10 canciones y 1 Fogata activa en paralelo.
   - Dispone del **100% de las funciones musicales**: Modo Tocar, atril continuo, auto-scroll, transposición tonal (-6 a +6), C ↔ Do, diagramas interactivos de acordes, edición y guardado, generación de links temporales y QR para invitados, navegación en atril de invitados.
   - La restricción de 1 Fogata se refiere a **1 Fogata almacenada simultáneamente**: el usuario Gratis puede editarla, vaciarla, renombrarla, cambiar su repertorio y reutilizarla indefinidamente.
2. **`PRO`**: Canciones y Fogatas ilimitadas (`∞`).
3. **`PILOTO`**: Cuentas existentes del piloto se mantienen como `PILOTO` (**PRO sin cobro**), garantizando que ningún usuario inicial pierda contenido ni capacidad durante las pruebas.
4. **`ADMIN`**: Usuarios con `is_staff=True` o `is_superuser=True` operan con capacidad ilimitada, desacoplados de la clasificación comercial de suscripción.

#### C. Defensa en Servidor, Concurrencia y Comportamiento Real en SQLite
- **Validación server-side estricta:** Un usuario `GRATIS` con 10 canciones que fabrique manualmente una petición `POST /canciones/nueva/` es rechazado de forma segura e informado amigablemente. Lo mismo aplica para `POST /fogatas/nueva/`.
- **Validación dentro de transacciones:** Las creaciones de canciones y Fogatas se ejecutan dentro de bloques `with transaction.atomic():`, re-validando el cupo antes de persistir (`puede_crear_cancion(user, bloquear=True)`).
- **Comportamiento real observado bajo SQLite:**
  - Fogata utiliza actualmente SQLite como motor de base de datos.
  - En SQLite, `select_for_update()` no proporciona un bloqueo de fila real equivalente al disponible en PostgreSQL, ya que SQLite opera mediante bloqueos a nivel de archivo/base de datos completa.
  - Se implementó y ejecutó una suite de pruebas concurrentes específica (`ConcurrenciaFreemiumSQLiteTests`) con 4 hilos simultáneos intentando sobrepasar los límites de canciones (9 → 10 → 11) y de Fogatas (0 → 1 → 2).
  - **Resultados reales observados:**
    - Cero corrupción de datos.
    - Cero sobrepasos: los invariantes de integridad se mantuvieron estrictamente (`total_canciones <= 10` y `total_fogatas <= 1`).
    - Las peticiones concurrentes simultáneas son serializadas por el cerrojo de base de datos de SQLite o manejadas limpiamente ante contención (`database table is locked`), sin romper la aplicación.
  - **Declaración explícita de arquitectura:**
    > **"La validación de límites está protegida en servidor y dentro de transacciones. La garantía fuerte frente a concurrencia simultánea será reforzada al migrar la base de producción a PostgreSQL."**

#### D. Experiencia de Usuario (UX) Empática
Se erradicó cualquier lenguaje punitivo ("bloqueado", "prohibido", "debes pagar"):
- Al alcanzar 10 canciones: Pantalla comercial dedicada `templates/canciones/limite_alcanzado.html` con mensaje:  
  **"Tu repertorio está creciendo 🔥"** — *En Fogata Gratis puedes guardar hasta 10 canciones. Con Fogata Pro puedes guardar todas las canciones que quieras.*
- Al intentar crear una segunda Fogata: Pantalla comercial `templates/fogatas/limite_alcanzado.html` con mensaje:  
  **"¿Otra Fogata? 🔥"** — *En Fogata Gratis puedes mantener 1 Fogata. Con Fogata Pro puedes crear todas las sesiones y repertorios que necesites.*
- **Avisos preventivos en biblioteca:** Banner en `canciones/lista.html` al alcanzar 8 o 9 canciones indicando cuántas canciones quedan antes de llegar al límite.

#### E. Política de Downgrade No Destructiva
Si una cuenta `PRO` con 35 canciones y 5 Fogatas pasa a `GRATIS`:
- **Cero borrado, cero bloqueo:** Las 35 canciones y 5 Fogatas permanecen intactas.
- El usuario puede continuar viéndolas, tocándolas, editándolas y compartiéndolas.
- Únicamente se restringe la **creación de nuevo contenido** hasta que se sitúe por debajo del límite o reactive su suscripción Pro.

#### F. Landing Interna `/pro/` y Configuración Central de Precios
- Endpoint: `/pro/` (accesible tanto vía `{% url 'pro' %}` como `{% url 'core:pro' %}`).
- Contenido: Comparativa clara y honesta entre Fogata Gratis y Fogata Pro.
- Precios centralizados en `config/settings.py`:
  - `FOGATA_PRO_SEMESTRAL_PRICE_CLP = 5990` ($5.990 / 6 meses)
  - `FOGATA_PRO_ANUAL_PRICE_CLP = 9990` ($9.990 / año)
  - Mensaje destacado: **"Equivale a menos de $1.000 al mes."**
  - Botón de acción: Indicador sobrio "Próximamente" sin checkout falso.

#### G. Integración en Fogata Control Center (`apps/gestion`)
1. **Ficha de Usuario 360°:**
   - Visualización de capacidad utilizada y límite: `8 / 10` para Gratis o `34 / ∞` para Pro/Piloto/Admin.
   - Indicador visual del plan activo (`GRATIS`, `PRO`, `PILOTO`, `ADMIN`).
2. **Cambio Manual de Plan Administrativo:**
   - Formulario seguro protegido por `@staff_required` y `@require_POST` en `POST /gestion/usuarios/<id>/cambiar-plan/`.
   - Permite transiciones `GRATIS → PRO`, `PRO → GRATIS`, `PILOTO → PRO`.
   - Registro obligatorio en `AuditoriaAdmin` con acción `cambiar_plan`, registrando administrador, usuario afectado, plan anterior, plan nuevo y timestamp.
3. **Métricas Comerciales en Dashboard:**
   - Conteo de usuarios por plan: `GRATIS`, `PRO`, `PILOTO`.
   - Monitor de límites: usuarios Gratis en 8–9 canciones, en 10/10 canciones y con 1/1 Fogata.
   - Intención comercial: usuarios que vieron `/pro/`, usuarios que alcanzaron límite de canciones o Fogatas.
4. **Señal de Conversión:**
   - Métrica que detecta usuarios Gratis con señal activa de demanda (10 canciones, intento de canción 11, intento de 2da Fogata o visita a Pro tras límite).
5. **Funnel Comercial Freemium:**
   - Embudo de 6 etapas visualizado en `gestion/metricas.html`:  
     `Usuario Gratis → Usuario activado → 8+ canciones → Límite alcanzado → Visitó Pro → PRO`.

#### H. Privacidad Estricta
- Los nuevos eventos comerciales (`ver_pro`, `alcanzar_limite_canciones`, `alcanzar_limite_fogatas`) aplican la misma política de privacidad estricta de Fase 7: **jamás registran letras, acordes, títulos de canciones ni contenido musical privado**.
- Las visitas a `/pro/` y las alertas de límite incorporan debounce en sesión para prevenir saturación de logs.

---

### 3. Archivos Creados y Modificados

| Componente | Archivo | Acción | Propósito |
| :--- | :--- | :--- | :--- |
| **Configuración** | `config/settings.py` | Modificado | Constantes de precios, límites y context processor `plan_context`. |
| **Configuración** | `config/urls.py` | Modificado | Registro de ruta raíz canónica `/pro/`. |
| **Planes Service** | `apps/core/planes.py` | **Nuevo** | Servicio central de límites, tipos de cuenta y estructura de capacidad. |
| **Context Processor**| `apps/core/context_processors.py` | **Nuevo** | Inyección global ligera de plan en plantillas (`base.html`). |
| **Modelos Core** | `apps/core/models.py` | Modificado | Opciones `GRATIS`/`PRO` y campos para vigencia futura en `PerfilPiloto`. |
| **Migración Core** | `apps/core/migrations/0004_...py` | **Nuevo** | Campos de suscripción en `PerfilPiloto`. |
| **Vistas Core** | `apps/core/views.py` | Modificado | Nueva cuenta asignada a `GRATIS` y landing `pro_view`. |
| **Rutas Core** | `apps/core/urls.py` | Modificado | Ruta `path('pro/', views.pro_view, name='pro')`. |
| **Canciones Vistas** | `apps/canciones/views.py` | Modificado | Verificación atómica de límites en `crear` y capacidad en `lista`. |
| **Fogatas Vistas** | `apps/fogatas/views.py` | Modificado | Verificación atómica de límite de 1 Fogata en `crear` y capacidad en `lista`. |
| **Gestión Modelos**| `apps/gestion/models.py` | Modificado | Eventos comerciales en `EventoUso` y `cambiar_plan` en `AuditoriaAdmin`. |
| **Migración Gestión**| `apps/gestion/migrations/0002_...py`| **Nuevo** | Nuevos choices para eventos y auditoría. |
| **Gestión Constantes**| `apps/gestion/constants.py` | Modificado | Inclusión de eventos comerciales en `METADATA_WHITELIST`. |
| **Gestión Métricas** | `apps/gestion/metrics.py` | Modificado | Función `obtener_metricas_comerciales` (planes, límites, funnel, señales). |
| **Gestión Vistas** | `apps/gestion/views.py` | Modificado | Inclusión de métricas comerciales y vista `usuario_cambiar_plan_view`. |
| **Gestión Rutas** | `apps/gestion/urls.py` | Modificado | Ruta `usuarios/<pk>/cambiar-plan/`. |
| **Plantillas Core** | `templates/core/pro.html` | **Nuevo** | Landing interna Fogata Pro con precios referenciales y comparativa. |
| **Plantillas Base** | `templates/base.html` | Modificado | Indicador discreto del plan activo en el menú de navegación. |
| **Plantillas Canciones**| `templates/canciones/limite_alcanzado.html` | **Nuevo** | Pantalla comercial empática ante tope de canciones. |
| **Plantillas Canciones**| `templates/canciones/lista.html` | Modificado | Indicador de capacidad y banners de advertencia 8-9 canciones. |
| **Plantillas Fogatas**| `templates/fogatas/limite_alcanzado.html` | **Nuevo** | Pantalla comercial ante intento de 2da Fogata en Gratis. |
| **Plantillas Fogatas**| `templates/fogatas/lista.html` | Modificado | Indicador de capacidad de Fogatas y mensaje explicativo. |
| **Plantillas Gestión**| `templates/gestion/usuario_detalle.html` | Modificado | Ficha con métricas `X/10`, `X/∞` y formulario de cambio de plan. |
| **Plantillas Gestión**| `templates/gestion/usuarios_lista.html` | Modificado | Columna "Plan" en la tabla general de usuarios. |
| **Plantillas Gestión**| `templates/gestion/dashboard.html` | Modificado | Panel con métricas comerciales, límites y señales de conversión. |
| **Plantillas Gestión**| `templates/gestion/metricas.html` | Modificado | Gráfico del Funnel Comercial Freemium (6 etapas). |
| **Batería de Pruebas**| `apps/core/test_planes.py` | **Nuevo** | 19 pruebas exhaustivas de límites, downgrade, auditoría y eventos. |

---

### 4. Resultados de la Batería de Pruebas

Se ejecutó la suite completa de pruebas automatizadas:
```bash
.venv/bin/python manage.py test
```

**Resultado:**
```text
Ran 154 tests in 30.186s

OK
Destroying test database for alias 'default'...
```

#### Cobertura específica de Fase 8 (21 pruebas en test_planes.py):
- **`GRATIS`:**
  - Puede crear canciones 1 a 10 con éxito.
  - Canción 11 es rechazada tanto en GET como en POST forzado, mostrando pantalla comercial y manteniendo el conteo en 10.
  - Puede crear 1 Fogata. La 2da Fogata es rechazada en servidor tanto en GET como en POST forzado.
  - El usuario en el límite puede continuar utilizando Modo Tocar, auto-scroll, transposición tonal, diagramas interactivos, edición y compartición de sesiones.
- **`Concurrencia bajo SQLite (ConcurrenciaFreemiumSQLiteTests)`:**
  - Peticiones simultáneas concurrentes (4 hilos) para creación de canciones (9 → 10 → 11) respetan estrictamente el tope de 10 canciones (`total_canciones <= 10`).
  - Peticiones simultáneas concurrentes (4 hilos) para creación de Fogatas (0 → 1 → 2) respetan estrictamente el tope de 1 Fogata (`total_fogatas <= 1`).
  - Cero corrupción de base de datos; la contención milimétrica de SQLite es manejada limpiamente.
- **`PRO`:**
  - Canción 11+ permitida sin restricciones.
  - Múltiples Fogatas permitidas.
- **`PILOTO` y `ADMIN`:**
  - Comportamiento ilimitado comprobado.
- **`Downgrade`:**
  - Cuenta degradada de `PRO` a `GRATIS` con 15 canciones y 3 Fogatas preserva el 100% de su contenido, mantiene acceso total a Modo Tocar y edición, pero bloquea creaciones adicionales mientras esté sobre el cupo.
- **`Auditoría y Cambio de Plan`:**
  - Requiere privilegios de staff (403 para usuarios comunes).
  - Rechaza peticiones GET (405 Method Not Allowed).
  - Ejecuta el cambio de plan y genera el registro en `AuditoriaAdmin` con todos los detalles requeridos.
- **`Precios y Landing Pro`:**
  - `/pro/` renderiza los valores centralizados `$5.990` y `$9.990`.
- **`Eventos y Privacidad`:**
  - Emisión de `ver_pro`, `alcanzar_limite_canciones` y `alcanzar_limite_fogatas` sin almacenar jamás letras, acordes ni títulos de canciones.

---

### 5. Próximos Pasos (Hacia la Fase 9)

Con la arquitectura Freemium y la defensa en servidor completamente validadas, Fogata cuenta con la base técnica para la **Fase 9 — Medios de Pago e Integración Comercial**:
1. Selección e integración de pasarela de pago (ej: Webpay Plus / Mercado Pago / Stripe).
2. Generación de órdenes de compra y webhooks para actualización automática de `tipo_cuenta='PRO'`.
3. Gestión de vigencia de plan con `fecha_inicio_plan`, `fecha_fin_plan` y `estado_suscripcion` ya preparados en el modelo de base de datos.
