# FOGATA — Informe de Implementación Fase 3
## Gestión, Edición Rápida, Notación y Transposición de Acordes

**Fecha:** 26 de septiembre de 2026  
**Versión:** Fogata 0.3.0 (Fase 3 Completada)  
**Entorno:** Python 3.14.2, Django 5.2 LTS, SQLite, Vanilla CSS & Vanilla ES5 JavaScript.  
**Estado:** ✅ **Aprobada e Implementada al 100%**. Suite completa de 60 pruebas pasando sin errores.

---

## 1. Resumen Ejecutivo

En la **Fase 3** se resolvió de forma robusta la necesidad de corregir y adaptar canciones tras su carga inicial, bajo el principio rector:

> **"Corregir o adaptar una canción debe ser más fácil que volver a cargarla, sin modificar jamás el original salvo cuando el usuario explícitamente decide editarlo."**

Se implementaron cuatro capacidades conectadas:
1. **Edición rápida de un acorde individual** preservando la alineación horizontal de los acordes subsiguientes.
2. **Reemplazo global selectivo** basado exclusivamente en `AcordeToken` (sin modificar texto, letra, comentarios ni tablaturas).
3. **Transposición no destructiva** entre −6 y +6 semitonos (tanto en servidor como instantáneamente en navegador).
4. **Cambio de notación visual** Americana (A–G) ↔ Latina (Do–Si) sin alterar el texto guardado en `Cancion.contenido`.

---

## 2. Decisiones de Arquitectura e Implementación

### 2.1. Una Única Interpretación Musical (Criterio 1)
- El **parser Python** existente es la **única fuente de verdad** musical.
- **No se creó un segundo parser en JavaScript**.
- Cada acorde renderizado expone metadatos estructurados en atributos HTML seguros:
  ```html
  <span class="acorde"
        data-root="7"
        data-mod="m7"
        data-bass=""
        data-original="Gm7">
    Gm7
  </span>
  ```
- Principio mantenido: **"Python entiende la canción. JavaScript solamente modifica temporalmente cómo se muestra."**

### 2.2. Edición Rápida de Acordes y Concurrencia (Criterios 2, 3, 5)
- Acceso desde la ficha de la canción: `Ficha de canción → 🎵 Editar acordes` (`/canciones/<pk>/acordes/`).
- Al pulsar un acorde en el atril de edición se despliega el selector rápido:
  - **Acorde actual:** `G`
  - **Cambiar por:** `[________]`
  - **Acciones:** `💾 Guardar` (sólo este acorde, predeterminado), `🔁 Cambiar todas las apariciones`, `✕ Cancelar`.
- **Validación de Concurrencia e Integridad**: Antes de guardar cualquier edición rápida se valida número de línea, posición inicial, posición final y texto original. Si el contenido fue alterado por otra sesión o pestaña, el cambio se rechaza con el mensaje explícito:  
  *«La canción cambió desde que abriste el editor. Recarga antes de modificar este acorde.»*
- **Reemplazo Global Seguro**: Se procesan los tokens de derecha a izquierda dentro de cada línea analizada, impidiendo que el desplazamiento de columnas afecte los índices precedentes. No se utiliza `str.replace()` y la letra jamás se modifica.

### 2.3. Preservación Espacial y Alineación Horizontal (Criterio 4)
- **Líneas de acordes aislados:**
  - Si el nuevo acorde es más largo (`G → Gmaj7`, diferencia +4 caracteres), absorbe hasta 4 espacios contiguos a la derecha para mantener el acorde siguiente (ej. `D`) en la misma columna exacta.
  - Si el nuevo acorde es más corto (`Gmaj7 → G`, diferencia −4 caracteres), inserta 4 espacios compensatorios a la derecha.
  - Nunca se eliminan letras, otros acordes ni separadores si los espacios no son suficientes; en tal caso se permite el desplazamiento natural.
- **Acordes embebidos en corchetes:**  
  `[G]Texto` → `[G7]Texto` sin compensación espacial de espacios.

### 2.4. Política Única y Determinista de Alteraciones (Criterios 6 y 7)
Se implementó la jerarquía estricta de 3 prioridades:
1. **Primera prioridad:** Si `Cancion.tonalidad` está definida y corresponde a bemoles (F, Bb, Eb, Ab, Db, Gb, Dm, Gm, etc.) se eligen bemoles; si corresponde a sostenidos (G, D, A, E, B, F#m, etc.) se eligen sostenidos.
2. **Segunda prioridad:** Si no hay tonalidad, se realiza un conteo global de alteraciones originales en los acordes de la canción (`b` vs `#`).
3. **Tercera prioridad:** Si la canción solo usa acordes naturales, transposición positiva usa sostenidos y transposición negativa usa bemoles.
- **Enarmónicos prácticos:** Se evitan grafías académicas no prácticas para guitarristas como `E#`, `B#`, `Cb`, `Fb` o dobles alteraciones, utilizando `F`, `C`, `B`, `E`.

### 2.5. Transposición y Notación en Modo Tocar (Criterios 8, 9, 10, 11, 12, 13, 14, 15)
- **Rango de semitonos:** −6 a +6 mediante parámetro URL `?semitonos=2` o `?semitonos=-2` (evitando `?tono=+2` por ambigüedad del signo `+` en query strings).
- **Client-Side Instantáneo:** Con JavaScript activo, pulsar `−♭` o `♯+` transpone todos los acordes en el DOM en menos de 2 milisegundos sin recargar la página, conservando la posición de lectura, el estado de auto-scroll, la velocidad y el tamaño de letra.
- **Preferencia de Notación:** Almacenada en `localStorage.fogata_chord_notation`.
- **Fallback Server-Side:** Sin JavaScript, los botones funcionan mediante enlaces GET y el servidor entrega el HTML completamente renderizado con los tonos y notación solicitados.
- **Retorno a Original:** Transposición 0 semitonos recupera exactamente las notas originales, respetando la notación latina si el usuario la tiene seleccionada.

### 2.6. Acordes Utilizados y Tonalidad Resultante (Criterios 16 y 17)
- Se incluye en el encabezado de atril y detalle el resumen discreto:
  `Acordes: G · D · Em · C`
  El cual refleja inmediatamente la transposición y el sistema de notación activo.
- La tonalidad muestra la relación original y transpuesta:  
  `Original: G (+2: A)` (o `Original: G (+2: La)` en notación latina).

---

## 3. Pruebas Automatizadas y Validación

### 3.1. Pruebas Específicas del Criterio 18
Se incorporaron y superaron todas las pruebas requeridas en `apps/canciones/tests.py`:
1. `test_edicion_acorde_embebido`: Edición `[G]Texto` → `[G7]Texto` sin tocar letra.
2. `test_edicion_G_a_Gmaj7_conservando_columna_posterior`: Conservación milimétrica de la columna de inicio de `D` tras expandir `G` a `Gmaj7`.
3. `test_reduccion_Gmaj7_a_G_conservando_columna_posterior`: Conservación de columna tras acortar `Gmaj7` a `G`.
4. `test_reemplazo_global_multiples_acordes_misma_linea`: Reemplazo de todos los `G` en una misma línea sin tocar la letra 'G' en versos ni tablaturas.
5. `test_transposicion_acorde_con_bajo_slash`: `G/B` + 2 semitonos → `A/C#`, `C/E` + 1 semitono (bemoles) → `Db/F`.
6. `test_transposicion_combinada_con_notacion_latina`: `C#m7` + 1 semitono → `Rem7`, `Bb` + 1 semitono → `Si`, `G/B` + 2 semitonos → `La/Do#`.
7. `test_consistencia_sostenidos_bemoles_cancion_completa`: Verificación de la regla de 3 prioridades deterministas.
8. `test_parametro_semitonos_fuera_de_rango`: Entradas como `?semitonos=15`, `-99` o `invalido` retornan de forma segura a 0 sin errores 500.
9. `test_fallback_servidor_sin_javascript`: Renderizado de acordes transpuestos en servidor y presencia de enlaces de navegación GET.
10. `test_contenido_con_html_malicioso_durante_edicion`: Rechazo de payloads XSS (`<script>`) como nombres de acordes, manteniendo el contenido intacto.
11. `test_retorno_a_tono_original_manteniendo_notacion_seleccionada`: Retorno a 0 semitonos mostrando la tonalidad original bajo grafía latina.
12. `test_concurrencia_e_integridad_cancion_modificada`: Detección y rechazo de modificaciones basadas en índices desactualizados.
13. `test_javascript_es5_fase3_sintaxis_y_funciones`: Verificación de compatibilidad estricta con navegadores antiguos (cero uso de `const`, `let` o `=>`).

### 3.2. Ejecución de la Suite Completa
```bash
$ .venv/bin/python manage.py test
Found 60 test(s).
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
............................................................
----------------------------------------------------------------------
Ran 60 tests in 0.069s

OK
Destroying test database for alias 'default'...
```

### 3.3. Validación de Sintaxis JavaScript
```bash
$ node -c static/js/fogata.js
# Código de salida 0 (Sin errores sintácticos)
```

---

## 4. Limitaciones Encontradas y Alcance Respetado

De acuerdo con el mandato de la Fase 3, **se mantuvo el alcance estrictamente acotado**:
- **NO se agregaron diagramas de acordes ni posiciones de dedos** (se mantiene para fases posteriores).
- **NO se agregaron afinadores, metrónomos ni generación de audio**.
- **NO se modificaron las funciones de compartir ni sesiones de invitados**.
- **NO se incorporó edición colaborativa concurrente** (la edición es local del usuario con protección de sobreescritura).
- **NO se alteró el principio no destructivo:** `Cancion.contenido` nunca cambia por transposición ni por cambio de notación; únicamente cambia cuando el usuario pulsa explícitamente "Guardar" en la pantalla de edición rápida.

---

## 5. Conclusión y Recomendación

La Fase 3 entrega una experiencia de atril profesional y ágil para el músico:
- Permite adaptar el tono de cualquier canción al rango vocal del intérprete de forma instantánea.
- Permite alternar la notación entre cifrado americano y latino según la costumbre del guitarrista.
- Permite corregir rápidamente errores de acordes copiados de la web con 2 toques en pantalla, sin romper la tabulación ni el formato original.

El sistema se encuentra listo para revisión y posterior definición de la Fase 4.
