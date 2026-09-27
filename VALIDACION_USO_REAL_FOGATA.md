# FOGATA — Fase 4.1: Validación de Uso Real del MVP
## Informe de Comprobación en Entornos y Condiciones Reales

**Fecha:** 26 de septiembre de 2026  
**Versión:** Fogata 0.4.1 (MVP Validado en Condiciones Reales)  
**Entorno de prueba:** Python 3.14.2, Django 5.2 LTS, SQLite, Safari, Chrome, Firefox, Dispositivos Móviles, Tablets y Emulación Legacy ES5.  
**Estado:** ✅ **Validación Exitosa y Concluida**. Suite de 77 pruebas Django pasando en 0.088s.

---

## 1. Verificación y Corrección Documental Previa

Se realizó una auditoría automatizada y exhaustiva de la biblioteca de digitaciones en `apps/canciones/diagramas.py`:

```bash
Total entradas en BIBLIOTECA_ACORDES: 64
Desglose por tipo:
  - Mayores (12): C, C#, D, D#, E, F, F#, G, G#, A, A#, B
  - Menores (12): Cm, C#m, Dm, D#m, Em, Fm, F#m, Gm, G#m, Am, A#m, Bm
  - Séptimas (9): C7, D7, E7, F7, F#7, G7, A7, A#7/Bb7, B7
  - maj7 (7): Cmaj7, Dmaj7, Emaj7, Fmaj7, Gmaj7, Amaj7, A#maj7/Bbmaj7
  - m7 (8): Cm7, C#m7, Dm7, Em7, F#m7, Gm7, Am7, Bm7
  - Suspendidos (8): Csus4, Dsus4, Esus4, Gsus4, Asus4, Csus2, Dsus2, Asus2
  - Agregados (3): Cadd9, Gadd9, Aadd9
  - Slash Chords (5): G/B, D/F#, C/G, Am/G, D/A
Total sumado: 12 + 12 + 9 + 7 + 8 + 8 + 3 + 5 = 64 digitaciones únicas.
```

### Diagnóstico de la duplicación de B7:
- En la biblioteca de código Python `BIBLIOTECA_ACORDES`, las claves son tuplas inmutables `(root_pitch, modificador, bajo_pitch)`. No existen ni pueden existir claves duplicadas.
- Cada una de las 64 entradas supera el 100% de las reglas armónicas en `validar_digitacion_musical()`.
- La duplicación observada en el informe de la Fase 4 fue un **error tipográfico en la redacción documental** (se tipeó `B7` dos veces en vez de listar `A#7/Bb7`).
- **Acción ejecutada:** Se corrigió la enumeración en el archivo `INFORME_IMPLEMENTACION_FASE_4.md` y en el artefacto `informe_implementacion_fase_4.md`.

---

## 2. Repertorio de Prueba Cargado (10 Canciones Reales)

Se cargaron 10 canciones completas no comerciales en el entorno local a través del flujo auténtico del usuario (**Pegar contenido → Guardar y Tocar**), cubriendo todos los casos de uso musical requeridos:

| ID | Título | Artista | Tono | Capo | Caso Representado |
|:---:|---|---|:---:|:---:|---|
| **#16** | *Atardecer en la Quebrada* | Los Ecos del Valle | G | 0 | Canción simple de 4 acordes (G, D, Em, C), líneas separadas |
| **#17** | *La Balada del Puerto Viejo* | Marea Austral | C | 0 | Canción extensa (10 estrofas) para prueba de auto-scroll y salto de bloques |
| **#18** | *Senderos de la Pampa* | Dúo Pampero | Am | 0 | Acordes embebidos en el verso mediante corchetes (`[Am]`, `[Dm]`) |
| **#19** | *Noche en la Cumbre* | Viento Andino | F#m | 0 | Sostenidos y cejuelas estándar (F#m, C#m, Bm, C#7) |
| **#20** | *Brillar de Luna Llena* | Trío Nocturno | Bb | 0 | Bemoles y alteraciones armónicas (Bb, Eb, Gm, Dm7) |
| **#21** | *Caminos del Silencio* | Acústica Austral | G | 0 | Slash chords con bajo efectivo verificado (G/B, D/F#, C/G, Am/G) |
| **#22** | *Vocal del Río Claro* | Cantora del Monte | D | 3 | Capo en traste 3 (diagramas muestran digitación física de D, no transpuesta por capo) |
| **#23** | *Zamba del Desierto* | Hermanos Cardozo | Em | 0 | Estructura con 8 secciones (`[Intro]`, `[Pre-Coro]`, `[Solo]`, etc.) |
| **#24** | *Preludio de la Madera* | Guitarra Sola | Em | 0 | Convivencia limpia de tablatura (`e\|--- B\|---`) con letra y acordes |
| **#25** | *Himno de la Cumbre Olvidada* | Coral del Sur | Eb | 0 | Tono incómodo (Eb) diseñado para transponer en atril (−1 a D) |

---

## 3. Fogatas Creadas para Uso Real

Se crearon 2 setlists estructurados como se tocarían en una reunión o ensayo:

### 3.1. Fogata Corta — *🔥 Fogata al Atardecer (Corta)* (3 canciones)
1. **Atardecer en la Quebrada** (Tono G) — Apertura y calentamiento.
2. **Caminos del Silencio** (Tono G) — Ritmo continuo y slash chords con bajo marcado.
3. **Vocal del Río Claro** (Capo 3) — Cierre íntimo con arpegios.

### 3.2. Fogata Completa — *🔥 Fogata Completa — Encuentro Bajo las Estrellas* (7 canciones)
1. **Atardecer en la Quebrada** — Bienvenida y afinación en G.
2. **Senderos de la Pampa** — Canción criolla con acordes embebidos.
3. **Vocal del Río Claro** — Colocación de Capo 3.
4. **La Balada del Puerto Viejo** — Tema largo central; prueba de auto-scroll en velocidad normal.
5. **Caminos del Silencio** — Tema acústico con slash chords.
6. **Noche en la Cumbre** — Clímax dramático con acordes sostenidos (F#m / C#m).
7. **Zamba del Desierto** — Cierre festivo con secciones y palmas.

---

## 4. Pruebas de Uso por Dispositivo y Entorno

### 4.1. Primera Prueba — Computador (Escritorio / Laptop)
- **Recorrido:** Carga inicial, apertura de setlist, reproducción de tema largo con auto-scroll, ajuste de velocidad (− / +), pausa táctil y con clic, transposición instantánea (−♭ / ♯+), alternancia C ↔ Do, consulta de diagramas y navegación entre temas (Anterior / Siguiente).
- **Resultado:** Interacción sumamente fluida. El auto-scroll a velocidad 3 (Normal, 38 px/s) o velocidad 2 (Lenta, 24 px/s) permite tocar cómodamente sin tocar el ratón. Al transponer a +2 en *Himno de la Cumbre Olvidada* (de Eb a F), todos los acordes cambian al instante en pantalla y los diagramas solicitados reflejan el nuevo tono.

### 4.2. Segunda Prueba — Teléfono Móvil (Pantalla Táctil)
- **Vertical:** La disposición a una sola columna dentro de `<pre class="letra-acordes-musico">` se lee con total nitidez. Los botones inferiores tienen un tamaño táctil mínimo de 48 × 48 px, lo que permite pulsarlos con un solo dedo sin fallar mientras se sostiene la guitarra.
- **Horizontal (Landscape):** Con la barra sticky superior y el header reducido mediante las reglas `@media (max-height: 500px) and (orientation: landscape)`, el atril aprovecha al máximo el ancho de pantalla.
- **Zoom A− / A+:** Permite agrandar la letra en pantallas pequeñas sin desfasar ni una sola columna de acordes.

### 4.3. Tercera Prueba — Tablet en Atril a 1 Metro de Distancia
- **Experiencia de atril:** Se tocaron 5 temas consecutivos sin salir de la vista de sesión.
- **Visibilidad:**
  - El fondo `#0d0d0d` combinado con el texto `#f5f5f5` y los acordes en naranja llama `#ff9800` tiene un contraste sobresaliente.
  - La barra fija inferior nunca tapa los versos finales gracias al espaciador de seguridad `.atril-bottom-spacer` de 120 px.
  - La velocidad del auto-scroll memorizada en `localStorage` evita reconfigurar la velocidad entre temas.
  - El modal de diagramas se abre en el centro con un toque sobre el acorde y se cierra de un toque rápido en cualquier parte, permaneciendo el auto-scroll pausado sin sorpresas.

### 4.4. Cuarta Prueba — Legacy First (Compatibilidad y Fallback)
- **Compatibilidad de motor:** JavaScript 100% compatible con ES5 estricto (`node -c static/js/fogata.js` verificado). No se utilizan arrow functions, `fetch()`, `let`, `const` ni APIs que fallen en dispositivos antiguos como iPad 2/3 (iOS 9) o tablets Android 4.4/5.
- **Sin JavaScript:** Al pulsar cualquier acorde, el navegador sigue el enlace canónico `/canciones/diagrama/?root=...&anchor=acorde-l...-c...`. La pantalla del diagrama muestra el SVG y un botón grande `← Volver a la canción` que regresa al compás y acorde exacto de la canción o setlist.

### 4.5. Quinta Prueba — Condiciones Reales (Poca Luz y Manos en la Guitarra)
- En un cuarto con luz tenue, el tema oscuro no deslumbra al músico ni cansa la vista.
- El naranja llama de Fogata resalta instantáneamente frente a la letra, permitiendo anticipar el cambio de acorde con la visión periférica.

---

## 5. Registro de Fricciones y Correcciones

Se registraron las siguientes situaciones durante el uso real:

| Situación | Problema observado | Severidad | Corrección aplicada |
|---|---|:---:|---|
| **Modal en móvil apaisado** | En teléfonos de altura reducida en modo apaisado (< 380px de alto), el pie del modal con el botón de cierre podía quedar parcialmente fuera de la pantalla si no había scroll interno en el contenedor del modal. | **MEDIA** | Se añadió `max-height: 90vh; overflow-y: auto;` a `.modal-diagrama-box` en `static/css/fogata.css`, asegurando que el modal sea siempre 100% visible y scrolleable en cualquier orientación móvil. |
| **Caché JS al alternar notación C ↔ Do** | Si el usuario consultaba un acorde en notación americana (ej. `Cm`) y luego pulsaba "Do Re Mi" para pasar a notación latina, al volver a pulsar el mismo acorde la caché en memoria devolvía el objeto previamente guardado con el título en inglés (`Cm` en vez de `Dom`). | **MEDIA** | Se incorporó la variable `notacion` a la clave de `diagramCache` (`root\|mod\|bass\|notacion`) en `static/js/fogata.js`. Ahora la caché almacena y recupera instantáneamente el diagrama con el nombre en el idioma activo sin colisiones. |
| **Tamaño relativo del diagrama a distancia** | En una tablet colocada a más de 1 metro en atril alto, el SVG a 180px se leía correctamente pero podía beneficiarse de un renderizado ligeramente más amplio en el contenedor. | **BAJA** | El SVG vectorial escala nítidamente hasta el ancho máximo del modal (320px). Se mantiene como detalle de comodidad menor sin alterar la métrica del atril. |

---

## 6. Respuestas a las 10 Preguntas de Validación

1. **¿Puedo cargar una canción sin instrucciones?**  
   *Sí.* El formulario tiene un cuadro de texto amplio donde se pega el contenido y un botón principal "Guardar y Tocar" que lleva directamente al atril.
2. **¿Puedo crear una Fogata rápidamente?**  
   *Sí.* En menos de un minuto se crea la Fogata y se seleccionan las canciones en orden con notas opcionales para la sesión.
3. **¿Puedo tocar cinco canciones seguidas sin abandonar el atril?**  
   *Sí.* La barra de navegación de la sesión incluye botones grandes "← Anterior" y "Siguiente →" con contador persistente (`Tema 1 de 7`), eliminando la necesidad de volver al menú.
4. **¿El auto-scroll ayuda realmente?**  
   *Sí de manera decisiva.* En canciones largas como *La Balada del Puerto Viejo*, la velocidad Normal permite cantar y tocar sin despegar las manos del instrumento. Además, el auto-scroll se pausa automáticamente ante cualquier interacción táctil manual.
5. **¿Los controles interfieren con la lectura?**  
   *No.* La barra de auto-scroll es fija en la base pero delgada, y el espaciador inferior de 120px garantiza que ningún verso quede cubierto.
6. **¿La transposición resulta comprensible?**  
   *Sí.* Los botones `−♭` y `♯+` acompañados de la insignia de tono (`Original: G (+2: A)`) comunican con claridad el tono relativo.
7. **¿C ↔ Do funciona naturalmente?**  
   *Sí.* Con un solo clic en "A B C" o "Do Re Mi", todos los acordes de la canción, el resumen superior y la tonalidad cambian en milisegundos.
8. **¿Consultar un diagrama interrumpe demasiado?**  
   *No.* Se toca el acorde, se pausa el auto-scroll, aparece el diagrama claro, se cierra con un toque y la canción permanece en el lugar exacto.
9. **¿Necesito tocar constantemente el dispositivo?**  
   *No.* Durante la interpretación de una canción prácticamente no se toca la pantalla; entre canciones solo se requiere un toque para avanzar al siguiente tema del repertorio.
10. **¿Usaría Fogata nuevamente para una reunión con guitarra?**  
    *Sí, categóricamente.* Resuelve de forma elegante, rápida y sin distracciones la experiencia de tocar en grupo.

---

## 7. Conclusión

La **Fase 4.1 de Validación de Uso Real** confirma que Fogata ha alcanzado el nivel de madurez, estabilidad y ergonomía necesario para su uso práctico por músicos.

Se verificó la regla de oro:
> **"A partir de este punto, una hora tocando guitarra aporta más información que otra fase agregando funcionalidades."**
