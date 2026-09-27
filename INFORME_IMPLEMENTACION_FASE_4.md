# FOGATA — Informe de Implementación Fase 4
## Diagramas de Acordes para Guitarra

**Fecha:** 26 de septiembre de 2026  
**Versión:** Fogata 0.4.0 (Fase 4 Completada)  
**Entorno:** Python 3.14.2, Django 5.2 LTS, SQLite, Vanilla CSS & Vanilla ES5 JavaScript.  
**Estado:** ✅ **Aprobada e Implementada al 100%**. Suite completa de 77 pruebas pasando sin errores (0.083s).

---

## 1. Resumen Ejecutivo

En la **Fase 4** se implementó la consulta de diagramas de digitación de guitarra durante el **Modo Tocar** bajo el principio rector:

> **"El diagrama debe ser musicalmente correcto, aparecer sin romper la canción y desaparecer sin hacer que el músico pierda su lugar."**

Se implementaron las siguientes capacidades clave:
1. **Validación musical automática**: Un motor de verificación armónica calcula las clases de altura producidas por cada cuerda que efectivamente suena en afinación estándar EADGBE, validando que mayores, menores, séptimas, maj7, m7, sus2, sus4 (sin tercera) y slash chords (bajo efectivo en la cuerda más grave) sean matemáticamente y musicalmente coherentes.
2. **Biblioteca de 64 digitaciones comprobadas**: Revisadas manualmente y verificadas con tests automatizados. Se corrigió explícitamente `Csus4` a `[-1, 3, 3, 0, 1, 1]` para evitar la tercera mayor (nota E) de la primera cuerda.
3. **Endpoint canónico estructurado y seguro (`/canciones/diagrama/`)**: No utiliza slugs crudos ni cadenas arbitrarias. Valida estrictamente `root` (0..11), modificador dentro del vocabulario formal y `bass` (0..11). Genera el título en el servidor y previene cualquier riesgo de inyección o redirección abierta.
4. **Modal en atril con JavaScript Progresivo (ES5)**:
   - Pausa automáticamente el auto-scroll.
   - Conserva la posición vertical de lectura (`window.pageYOffset`).
   - Muestra el diagrama SVG en modal accesible sin dependencias externas.
   - Al cerrar (botón, backdrop o tecla Esc), permanece pausado sin desfasar la ejecución del músico.
5. **Caché en cliente en memoria (`diagramCache`)**: Con clave `root|mod|bass`, evitando peticiones de red repetidas durante la sesión.
6. **Manejo coherente de Capo y Afinaciones Alternativas**:
   - **Capo**: Representa la forma física ejecutada respecto al capo (Capo 2 + G muestra forma de G, no de A).
   - **Afinaciones alternativas**: Si la afinación declarada es distinta de estándar (ej. Drop D, DADGAD), muestra advertencia discreta: *"Diagrama basado en afinación estándar EADGBE."*
7. **SVG vectorial sin dependencias ni fuentes musicales**: Cuerdas abiertas dibujadas con `<circle>` y cuerdas anuladas con dos `<line>` cruzadas (X), con `role="img"` y `<title>`.
8. **Preservación estricta de la métrica en atril**: Los enlaces `.acorde-link` son estrictamente inline y no introducen padding, margin, ni `inline-block` que rompan la alineación monospace de la estrofa.
9. **Fallback sin JavaScript 100% funcional**: Genera enlaces con anclas estables (`#acorde-l{line}-c{col}`) permitiendo consultar el diagrama en HTML accesible y retornar exactamente al punto de ejecución, tanto en canciones independientes como en setlists de Fogatas.

---

## 2. Decisiones de Arquitectura e Implementación

### 2.1. Validación Musical de Digitaciones (`apps/canciones/diagramas.py`)
- Se implementó la función `calcular_clases_altura(trastes, afinacion_cuerdas)`:
  - Cuerdas estándar: `[4, 9, 2, 7, 11, 4]` (6ª E a 1ª E).
  - Para cada traste >= 0: `(pitch_cuerda + traste) % 12`.
  - Determina además el bajo efectivo (la cuerda más grave que no está anulada con -1).
- Se implementó `validar_digitacion_musical(pitch_raiz, modificador, digitacion, bajo_pitch)`:
  - **Mayores**: Contienen raíz, 3ª mayor (+4) y 5ª (+7).
  - **Menores**: Contienen raíz, 3ª menor (+3) y 5ª (+7).
  - **sus4**: Contienen raíz, 4ª (+5) y 5ª (+7), y **NO** contienen 3ª mayor (+4) ni 3ª menor (+3).
  - **sus2**: Contienen raíz, 2ª (+2) y 5ª (+7), y **NO** contienen 3ª mayor (+4) ni 3ª menor (+3).
  - **Dominante 7**: Contiene raíz, 3ª mayor, 5ª y 7ª menor (+10).
  - **maj7**: Contiene raíz, 3ª mayor, 5ª y 7ª mayor (+11).
  - **m7**: Contiene raíz, 3ª menor, 5ª y 7ª menor (+10).
  - **Slash chords**: El bajo efectivo más grave que suena coincide estrictamente con `bajo_pitch`.

### 2.2. Biblioteca Inicial de Digitaciones (64 Acordes Validados)
- Contiene digitaciones prácticas de primera posición y con cejuela estándar para todos los grados cromáticos en:
  - Mayores (`C, D, E, F, G, A, B, C#, Eb, F#, Ab, Bb`)
  - Menores (`Cm, Dm, Em, Fm, Gm, Am, Bm, C#m, Ebm, F#m, G#m, Bbm`)
  - Séptimas (`C7, D7, E7, F7, F#7, G7, A7, A#7/Bb7, B7` — 9 acordes)
  - maj7 (`Cmaj7, Dmaj7, Emaj7, Fmaj7, Gmaj7, Amaj7, A#maj7/Bbmaj7` — 7 acordes)
  - m7 (`Cm7, C#m7, Dm7, Em7, F#m7, Gm7, Am7, Bm7` — 8 acordes)
  - Suspendidos (`Csus4, Dsus4, Esus4, Gsus4, Asus4, Csus2, Dsus2, Asus2` — 8 acordes)
  - Agregados (`Cadd9, Gadd9, Aadd9` — 3 acordes)
  - Slash Chords (`G/B, D/F#, C/G, Am/G, D/A` — 5 acordes)
- **Corrección de `Csus4`**: Se descartó la posición `x33010` (que sonaba con cuerda 1 al aire produciendo nota E). Se adoptó `x33011` (`[-1, 3, 3, 0, 1, 1]`) con notas C, F, G, C, F, eliminando por completo cualquier tercera.

### 2.3. Endpoint Canónico Seguro (`/canciones/diagrama/`)
- Mapeado en `apps/canciones/urls.py` como `path('diagrama/', views.ver_diagrama, name='ver_diagrama')`.
- Parámetros validados:
  - `root`: Entero 0..11 (devuelve 400 Bad Request si es inválido).
  - `mod`: Cadena perteneciente al conjunto controlado `VOCABULARIO_MODIFICADORES_VALIDOS` (devuelve 400 Bad Request si es desconocida o contiene scripts).
  - `bass`: Opcional, entero 0..11 (devuelve 400 Bad Request si no es válido).
  - `notacion`: `'american'` o `'latin'`.
  - `cancion_id`, `fogata_id`, `pos`, `semitonos`, `anchor`: Parámetros contextuales para construir el retorno.
- **Prevención de Open Redirect**: Los retornos sin JS se reconstruyen internamente hacia `reverse('canciones:tocar')` o `reverse('fogatas:tocar_sesion')`. No se acepta ningún parámetro `next` arbitrario.
- **Doble respuesta**: Retorna JSON para clientes con AJAX (`XMLHttpRequest` / `Accept: application/json` / `format=json`) o página HTML completa para navegadores sin JS.

### 2.4. Generación SVG Vectorial sin Tipografías Musicales
- Generado de forma pura en servidor mediante `generar_svg_acorde(digitacion, nombre_mostrar)`.
- Medidas exactas (`viewBox="0 0 160 200"`), responsive en móviles y pantallas de atril.
- `<title>` y `role="img"` para accesibilidad.
- Marcadores de cuerda:
  - Cuerda abierta: `<circle cx="..." cy="..." r="4.5" fill="none" stroke="#cccccc" stroke-width="1.8" />`.
  - Cuerda anulada: dos elementos `<line>` cruzados en `X` con `stroke="#888888"`.
- Traste base (`base_fret`): si es > 1, muestra indicador discreto (ej: `3fr`).
- Cejilla: dibuja una barra rectangular estilizada con radio curvado si la digitación la especifica.
- Puntos de digitación con número de dedo legible en contraste.

### 2.5. Interacción en Atril y JavaScript Progresivo (`static/js/fogata.js`)
- **Pausa inmediata**: Al pulsar un acorde en `.letra-acordes-musico`, si el auto-scroll está activo, se invoca `autoScrollCtrl.pausarAutoScroll()`.
- **Preservación del Scroll**: Se invoca `e.preventDefault()`, evitando que el navegador salte a la cabecera o al ancla.
- **Caché en memoria**:
  ```javascript
  var cacheKey = effRoot + '|' + mod + '|' + bassKey;
  if (diagramCache[cacheKey]) {
    mostrarDiagramaEnModal(diagramCache[cacheKey]);
    return;
  }
  ```
- **Transposición activa**: El acorde calcula su raíz y bajo efectivos:
  `effRoot = ((rootOrig + semitonos) % 12 + 12) % 12`
  permitiendo que al transponer la canción, el diagrama consultado corresponda al nuevo tono sonoro.
- **Cierre del Modal**: Vía botón `✕`, botón `Cerrar (Esc)`, clic fuera del modal o tecla `Escape`. El auto-scroll **permanece pausado** para que el músico decida cuándo continuar tocando.
- **Compatibilidad**: Estricto ES5 (sin `const`, `let`, arrow functions ni `fetch()`), verificado con `node -c static/js/fogata.js`.

### 2.6. Preservación Métrica del Atril y Fallback sin JavaScript
- Los acordes en la canción se envuelven en:
  ```html
  <a href="/canciones/diagrama/?root=..." class="acorde-link">
    <span class="acorde" id="acorde-l12-c18" data-root="7" data-mod="" data-bass="">G</span>
  </a>
  ```
- Reglas CSS en `static/css/fogata.css`:
  ```css
  .acorde-link {
    display: inline;
    color: inherit;
    text-decoration: none;
    cursor: pointer;
    padding: 0;
    margin: 0;
    border: none;
    background: transparent;
    font: inherit;
  }
  ```
- Cero impacto en el espaciado horizontal de fuentes monoespaciadas.
- En dispositivos sin JavaScript, el músico pulsa el enlace, accede a `/canciones/diagrama/` con el diagrama renderizado en SVG y el botón:
  `← Volver a la canción`
  que regresa a:
  `/canciones/42/tocar/?semitonos=...&notacion=...#acorde-l12-c18`
  (o `/fogatas/5/tocar/?pos=3...#acorde-l12-c18` si proviene de un setlist).

---

## 3. Cobertura de Pruebas y Validación

Se incorporaron 17 pruebas específicas en `apps/canciones/tests.py` (`Fase4DiagramasAcordesTest`), sumando un total de **77 pruebas en la suite de Fogata**:

| Prueba | Objetivo / Criterio Validado | Resultado |
|---|---|:---:|
| `test_validacion_armonica_biblioteca_completa` | Comprueba armónicamente las 64 posiciones de la biblioteca contra EADGBE | ✅ PASÓ |
| `test_sus4_sin_tercera` | Valida que Csus4 contenga C, F, G y ninguna tercera (mayor o menor) | ✅ PASÓ |
| `test_sus2_sin_tercera` | Valida que Dsus2 contenga D, E, A y ninguna tercera | ✅ PASÓ |
| `test_slash_chord_con_bajo_correcto` | Valida que G/B tenga bajo efectivo en B (quinta cuerda) y D/F# en F# | ✅ PASÓ |
| `test_detector_digitacion_invalida` | Detección de Csus4 erróneo (con 3ra) y G/B erróneo (con 6ta al aire) | ✅ PASÓ |
| `test_acorde_no_disponible_mensaje_exacto` | Acordes no incluidos muestran "Diagrama aún no disponible para este acorde." | ✅ PASÓ |
| `test_capo_no_altera_diagrama` | Canción con Capo 2 y acorde G solicita forma física de G (root=7), no A | ✅ PASÓ |
| `test_afinacion_alternativa_muestra_advertencia` | Canción en Drop D muestra "Diagrama basado en afinación estándar EADGBE." | ✅ PASÓ |
| `test_endpoint_diagrama_rechaza_root_fuera_de_rango` | Root < 0 o > 11 devuelve 400 Bad Request | ✅ PASÓ |
| `test_endpoint_diagrama_rechaza_modificador_invalido` | Modificadores arbitrarios o scripts devuelven 400 Bad Request | ✅ PASÓ |
| `test_svg_seguridad_xss_accesibilidad_y_primitivas` | SVG incluye role="img", <title>, <circle> abierta y <line> en X | ✅ PASÓ |
| `test_endpoint_diagrama_soporte_notacion_latina` | Root=0 genera "C" en americana y "Do" en latina con misma digitación | ✅ PASÓ |
| `test_retorno_no_js_con_ancla` | Retorno sin JS incluye ancla precisa `#acorde-l...-c...` | ✅ PASÓ |
| `test_retorno_no_js_dentro_de_fogata_setlist` | Retorno sin JS desde setlist conserva tema del repertorio y posición | ✅ PASÓ |
| `test_seguridad_retorno_sin_open_redirect` | Parámetros maliciosos no provocan redirecciones a sitios externos | ✅ PASÓ |
| `test_acorde_interactivo_no_rompe_alineacion_monospace` | `.acorde-link` es inline con 0 padding y 0 margin en pre | ✅ PASÓ |
| `test_diagramas_javascript_es5_y_cache` | JS cuenta con XHR, diagramCache, pausa de scroll y cero ES6 | ✅ PASÓ |

### Ejecución de Pruebas:
```bash
$ .venv/bin/python manage.py test
Found 77 test(s).
Creating test database for alias 'default'...
.............................................................................
----------------------------------------------------------------------
Ran 77 tests in 0.083s

OK
Destroying test database for alias 'default'...
```

---

## 4. Archivos Modificados e Incorporados

- **`apps/canciones/diagramas.py`** *(Nuevo)*: Motor de teoría musical, validador armónico de digitaciones, biblioteca de 64 acordes, generador de SVG accesible y resolutor de información de diagramas.
- **`apps/canciones/views.py`**: Incorporación de la vista `ver_diagrama` con validación estricta de parámetros, prevención de redirecciones abiertas y soporte JSON/HTML.
- **`apps/canciones/urls.py`**: Registro de la ruta canónica `path('diagrama/', views.ver_diagrama, name='ver_diagrama')`.
- **`apps/canciones/parser.py`**: Envoltura segura de `.acorde` en `.acorde-link` con IDs estables `#acorde-l{line}-c{col}` para soporte de diagramas interactivos y anclas no-JS.
- **`apps/canciones/templatetags/cancion_tags.py`**: Actualización de `render_cancion` para recibir y propagar `cancion_id`, `fogata_id` y `pos`.
- **`templates/canciones/_modal_diagrama.html`** *(Nuevo)*: Parcial de modal accesible para diagramas en atril.
- **`templates/canciones/diagrama_detalle.html`** *(Nuevo)*: Plantilla accesible para visualización de diagramas y retorno en navegadores sin JavaScript.
- **`templates/canciones/tocar.html`**: Inclusión del modal de diagramas y paso de atributos contextuales de atril.
- **`templates/fogatas/tocar_sesion.html`**: Inclusión del modal de diagramas y propagación de contexto de setlist (`fogata_id`, `pos`).
- **`static/css/fogata.css`**: Reglas estrictamente inline para `.acorde-link`, estilos del modal de diagrama, advertencia de afinación y visualización de SVG.
- **`static/js/fogata.js`**: Módulo `initDiagramasAtril`, `diagramCache`, llamadas XHR ES5, pausa de auto-scroll e integración con transposición dinámica.
- **`apps/canciones/tests.py`**: 17 nuevas pruebas integradas en la clase `Fase4DiagramasAcordesTest`.
- **`scratch/validar_fase_4.py`**: Script de verificación integral de criterios musicales y flujos reales.

---

## 5. Estado Final y Conclusión

La **Fase 4** cumple exhaustivamente con todos los criterios y ajustes solicitados:
- La biblioteca de acordes está armónicamente verificada contra afinación estándar.
- Las digitaciones no alteran la alineación espacial ni la legibilidad de la letra en modo músico.
- El músico consulta el acorde sin perder su ubicación de lectura y sin que el auto-scroll continúe corriendo sin supervisión.
- Existe una degradación perfecta para dispositivos antiguos sin JavaScript con retorno al punto exacto.
- Se preserva el principio fundamental de Fogata: **simplicidad, velocidad, compatibilidad y respeto estricto por el texto musical original**.
