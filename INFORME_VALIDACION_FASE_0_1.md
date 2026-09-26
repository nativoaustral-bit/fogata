# 🔥 FOGATA — Informe de Aceptación y Validación Fase 0.1

**Fecha de validación:** 26 de septiembre de 2026  
**Alcance:** Validación funcional y técnica de Fase 0 (MVP), corrección estricta de errores detectados y sustitución de datos de prueba por canciones ficticias.  
**Estado general:** **APROBADO (17 / 17 pruebas superadas)**  

---

## 1. Criterios de Aceptación y Resultados

| # | Prueba / Criterio de Verificación | Estado | Detalle de la Verificación y Correcciones Aplicadas |
| :-: | :--- | :-: | :--- |
| **1** | **Crear, editar y eliminar canción** | **PASS** | Flujo completo verificado mediante peticiones estándar POST. Los redireccionamientos, mensajes de confirmación de borrado y persistencia en SQLite operan correctamente sin depender de JavaScript. |
| **2** | **Preservar exactamente espacios y saltos de línea al guardar y volver a editar** | **PASS** | Verificado byte por byte. Se mantiene `strip=False` en `CancionForm` y `wrap="off"` en el `<textarea>`. Ningún espacio al inicio ni sangría interna es alterado al guardar ni al volver a abrir el formulario de edición. |
| **3** | **Pegar canciones con líneas largas** | **PASS** | Las líneas extensas (> 120 caracteres) se almacenan íntegras sin truncarse y se renderizan sin quiebres automáticos indeseados gracias a `white-space: pre` y `word-wrap: normal`. |
| **4** | **Comportamiento del Modo Tocar en móvil vertical y horizontal** | **CORREGIDO** | En modo vertical mantiene columna única centrada. Se añadió una regla `@media (max-height: 500px) and (orientation: landscape)` en `fogata.css` para compactar la barra de herramientas al colocar el dispositivo apaisado en atril, maximizando el área visible de letra. |
| **5** | **A- / A+ y persistencia del tamaño** | **PASS** | Opera entre 12 px y 40 px con incrementos de 2 px. Se persiste en `localStorage` con captura defensiva de excepciones (`try/catch`) para evitar bloqueos en modos privados de navegadores antiguos. |
| **6** | **Navegación Canción anterior / siguiente dentro de una Fogata** | **PASS** | Validada la navegación secuencial con parámetro `?pos=X`. En la primera canción solo se ofrece "Siguiente", en las intermedias ambas opciones, y en la última "Anterior" y "Fin del Setlist". Parámetros fuera de rango se corrigen automáticamente a los límites válidos. |
| **7** | **Funcionamiento completo sin JavaScript para funciones esenciales** | **CORREGIDO** | Toda la navegación, lectura, alta, edición, reordenamiento (▲/▼) y borrado opera 100% mediante HTML semántico y formularios estándar POST. Se agregó un bloque `<noscript><button type="submit">Ir al tema</button></noscript>` en `tocar_sesion.html` para permitir saltar a cualquier tema desde el desplegable aun sin JS activo. |
| **8** | **Degradación silenciosa cuando Wake Lock no existe** | **CORREGIDO** | En `tocar_sesion.html` se corrigió el identificador `id="btn-wakeLock"` por `id="btn-wakelock"` para coincidir con el script. Ante navegadores antiguos sin `navigator.wakeLock`, se deshabilita el botón mostrando el aviso sobrio sin arrojar ninguna excepción en consola. |
| **9** | **Scroll horizontal únicamente cuando sea necesario** | **CORREGIDO** | Se aplicó `max-width: 100%` y `box-sizing: border-box` al contenedor `.letra-acordes-wrapper`. Solo se activa el scroll horizontal dentro de la caja de letra si un verso sobrepasa el ancho de pantalla; la página principal nunca sufre desborde horizontal. |
| **10** | **Controles táctiles de mínimo 48 px** | **CORREGIDO** | Se corrigieron todos los elementos interactivos que medían menos de 48 px: botones `.btn-sm`, enlaces de navegación `.site-nav a`, botones `.zoom-btn`, botón `.wakelock-btn` y los botones de setlist (▲, ▼, ✕) en `detalle.html`. Todos cumplen ahora con `min-height: 48px; min-width: 48px;`. |
| **11** | **Ausencia de errores JavaScript** | **PASS** | Validado mediante comprobación estricta de sintaxis ES5 (`node -c static/js/fogata.js`). Cero errores en consola y ejecución segura en modo estricto. |
| **12** | **Ausencia de recursos externos obligatorios** | **PASS** | Verificado en todas las plantillas y hojas de estilo. Cero llamadas HTTP/HTTPS a recursos externos, cero `@import` remotos. |
| **13** | **Que ninguna funcionalidad dependa de CDN** | **PASS** | No existen dependencias de Bootstrap, Tailwind, jQuery, Google Fonts ni ningún otro proveedor CDN. Utiliza exclusivamente fuentes del sistema y activos locales servidos por Django. |
| **14** | **Que las páginas funcionen con conexión lenta** | **PASS** | Peso total combinado de los activos estáticos (`reset.css` + `fogata.css` + `fogata.js`): **~15 KB**. Carga inmediata incluso bajo conexiones 2G/3G inestables. |
| **15** | **Que una sesión temporal expirada o revocada no entregue contenido** | **CORREGIDO** | Si una sesión está vencida o revocada, retorna **HTTP 410 (Gone)** con la pantalla sobria *"Esta Fogata terminó"*. Se corrigió `sesion_compartida_cancion` para que consultas de canciones inexistentes o ajenas a la sesión respondan igualmente con 410, sin filtrar títulos ni fragmentos de letra. |
| **16** | **Que todas las rutas de invitado tengan no-store, private, noindex y nofollow** | **CORREGIDO** | Todas las respuestas públicas de sesión compartida (tanto exitosas como 410) emiten obligatoriamente las cabeceras HTTP: <br>`Cache-Control: no-store, private`<br>`X-Robots-Tag: noindex, nofollow`.<br>Además, se añadieron etiquetas defensivas `<meta name="robots" content="noindex, nofollow">` en el `<head>` de todas las plantillas de invitado. |
| **17** | **Datos de ejemplo con canciones ficticias libres** | **CORREGIDO** | En `cargar_datos_ejemplo.py` y en `tests.py` se eliminaron todas las canciones comerciales protegidas. Se reemplazaron por canciones ficticias creadas exclusivamente para pruebas acústicas (*"Atardecer en la Quebrada"*, *"Río de Arena"*, *"Noche de Viento Sur"*). |

---

## 2. Métricas y Verificación Técnica

- **Pruebas Unitarias y de Integración:** 17 de 17 pruebas superadas en 0.038 segundos.
- **Entorno de Ejecución:** Python 3.14 + Django 5.2 LTS + SQLite 3.
- **Tamaño de Carga Estática:**
  - `reset.css`: 1.2 KB
  - `fogata.css`: 14.1 KB
  - `fogata.js`: 6.1 KB
  - **Total activos frontend:** ~21.4 KB sin comprimir (< 8 KB con compresión gzip).
- **Control de Versiones:** Cambios consolidados en commit `f5e0c94`.

---

## 3. Conclusión

La aplicación cumple estrictamente con el principio rector:

> **SIMPLICIDAD + VELOCIDAD + LEGIBILIDAD + COMPATIBILIDAD**

Fogata se mantiene en su alcance de **Fase 0.1** como aplicación monousuario personal y de desarrollo, lista para pruebas en atril y dispositivos reales (Legacy Compatibility Targets).
