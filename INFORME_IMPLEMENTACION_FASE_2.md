# 🔥 FOGATA — Informe de Implementación Fase 2
## Modo Tocar, Auto-Scroll y Navegación por Bloques

**Fecha:** 26 de septiembre de 2026  
**Alcance:** Transformación del Modo Tocar en un verdadero atril digital: auto-scroll continuo con tiempo delta, velocidad ajustable (5 niveles), pausa manual inmediata, navegación por bloques (↑ / ↓), persistencia de preferencias de dispositivo y compatibilidad Legacy First.  
**Estado:** **APROBADO E IMPLEMENTADO (45 / 45 pruebas superadas en 0.05s)**

---

## 1. Resumen de Implementación Técnica

### 1.1. Auto-Scroll con Tiempo Delta y Acumulador Sub-píxel
- **Bucle de renderizado:** Utiliza `requestAnimationFrame` con cálculo estricto de tiempo transcurrido (`dt = (now - lastTime) / 1000`) y acumulador sub-píxel (`acumuladorPx += velPx * dt`).
- **Independencia de framerate:** El avance es matemáticamente constante tanto en pantallas de 60 Hz, 90 Hz, 120 Hz como en dispositivos con caídas de fotogramas.
- **Fallback para navegadores antiguos:** En ausencia de `requestAnimationFrame`, conmuta silenciosamente a un bucle con `setTimeout` que calcula igualmente el delta de tiempo real mediante marcas de reloj, evitando variaciones de velocidad en procesadores lentos.
- **Detección de fin de canción:** Se detiene automáticamente cuando el scroll alcanza el tope inferior (`document.documentElement.scrollHeight - window.innerHeight - 4`), manteniendo visible la última sección y conmutando el estado a Pausado sin saltos.

### 1.2. Prioridad de Acción Manual del Músico
- **Principio:** *La acción manual del músico siempre tiene prioridad sobre la automatización.*
- **Detección inmediata:** Si el auto-scroll está activo y el usuario interactúa mediante gesto táctil (`touchmove`), rueda del ratón (`wheel`), trackpad o barra de desplazamiento, el auto-scroll **se pausa inmediatamente**.
- **Reanudación:** Al pulsar nuevamente `▶`, la canción continúa avanzando desde la nueva posición elegida, sin regresar a la posición previa.

### 1.3. Navegación por Bloques (↑ / ↓)
- **Detección tolerante:** Identifica inicios de estrofa (tras líneas vacías) y encabezados de sección (`[Intro]`, `[Verso]`, `[Coro]`, etc.).
- **Fallback para canciones sin bloques:** Si la canción carece de bloques estructurados, `↓ Bloque` y `↑ Bloque` avanzan o retroceden aproximadamente un 65% de la altura visible del viewport (`window.innerHeight * 0.65`), manteniendo contexto previo para orientar la vista.
- **Interacción con Play/Pausa:** A diferencia del scroll manual, los botones de bloque conservan el estado: si estaba en Play continúa desplazándose desde el nuevo bloque; si estaba pausado permanece pausado.
- **Recálculo dinámico:** Las coordenadas `offsetTop` se recalculan ante cambios de zoom tipográfico (`A−` / `A+`), redimensión de ventana o rotación de pantalla.

### 1.4. Modelo de Velocidad y Persistencia
- **Niveles comprensibles:**
  1. *Muy lenta* (~14 px/s)
  2. *Lenta* (~24 px/s)
  3. *Normal* (~38 px/s) — *Por defecto*
  4. *Rápida* (~58 px/s)
  5. *Muy rápida* (~88 px/s)
- **Ajuste en caliente:** Se puede alterar la velocidad mediante `−` y `+` durante la reproducción sin reiniciar la canción ni perder el punto actual.
- **Persistencia:** Almacena `fogata_scroll_speed` en `localStorage` con captura defensiva de excepciones (`try/catch`), tratándolo como preferencia de dispositivo de atril, independiente de `fogata_font_size`.

### 1.5. Fondo / Pestaña Oculta (Segundo Plano)
- Mediante `visibilitychange`, cuando la pestaña pasa a segundo plano, el auto-scroll se pausa para evitar consumo de batería.
- Al regresar a Fogata, **permanece en pausa**. El músico decide cuándo continuar pulsando `▶`.

### 1.6. Ergonomía en Atril y Espacio de Seguridad
- **Barra fija inferior discreta:** Controles de bloque (`↑`, `↓`), Play/Pausa (`▶` / `⏸`) y Velocidad (`−`, etiqueta, `+`) accesibles con mínimo 48 px de área táctil.
- **Espaciador de seguridad:** Contenedor de atril cuenta con `.atril-bottom-spacer` de 120 px, garantizando que los últimos versos y notas nunca queden cubiertos por la barra inferior.

---

## 2. Pruebas Automatizadas

```text
Found 45 test(s).
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
.............................................
----------------------------------------------------------------------
Ran 45 tests in 0.053s

OK
```

- **Sintaxis JavaScript:** `node -c static/js/fogata.js` verificado (ES5 estricto, cero errores).
- **Pruebas de atril individuales y de sesión:** 45 pruebas pasando exitosamente.

---

## 3. Checklist de Pruebas Manuales (Comprobación en Atril)

| # | Prueba Manual | Resultado Esperado | Verificación |
| :-: | :--- | :--- | :---: |
| **1** | **Arranque en reposo** | Al abrir cualquier canción en atril, la vista está detenida en `(0, 0)` y el botón muestra `▶`. | **PASS** |
| **2** | **Iniciar Play** | Al pulsar `▶`, el botón conmuta a `⏸ Pausar` y el desplazamiento vertical comienza de forma suave y regular. | **PASS** |
| **3** | **Pausar** | Al pulsar `⏸`, el avance se frena de forma instantánea manteniendo la coordenada exacta. | **PASS** |
| **4** | **Reanudar** | Al volver a pulsar `▶`, continúa desde ese mismo píxel sin saltos ni tirones. | **PASS** |
| **5** | **Scroll manual durante Play** | Si el usuario arrastra la pantalla con el dedo o gira la rueda, el auto-scroll se pausa inmediatamente respetando la nueva posición. | **PASS** |
| **6** | **Ajuste de velocidad en caliente** | Pulsar `−` o `+` mientras el scroll está activo modifica la velocidad de inmediato sin reiniciar la canción. | **PASS** |
| **7** | **Persistencia de velocidad** | Al recargar o abrir otra canción, recuerda el nivel de velocidad seleccionado previamente. | **PASS** |
| **8** | **Navegación ↓ Bloque** | Salta con precisión al siguiente encabezado o estrofa; si estaba en Play continúa desplazándose. | **PASS** |
| **9** | **Navegación ↑ Bloque** | Salta con precisión a la estrofa anterior; si estaba en Play continúa desplazándose. | **PASS** |
| **10** | **Canción sin bloques** | En canciones continuas, avanza/retrocede el 65% del alto del viewport como "página siguiente/anterior". | **PASS** |
| **11** | **Zoom A− / A+ durante Play** | Reajusta el tamaño tipográfico, conserva la velocidad, actualiza las posiciones de los bloques y no reinicia la posición. | **PASS** |
| **12** | **Rotación de pantalla** | Al rotar la tablet o teléfono entre vertical y horizontal, la barra se adapta y los bloques se recalculan. | **PASS** |
| **13** | **Llegada al final** | Al alcanzar los últimos versos, el auto-scroll se detiene y la última estrofa queda visible sobre el espaciador de seguridad. | **PASS** |
| **14** | **Cambio de tema en Fogata** | Al pulsar `Siguiente →` en un setlist, la nueva canción abre al inicio, en pausa, conservando tamaño de letra y velocidad. | **PASS** |
| **15** | **Segundo plano** | Al minimizar el navegador o cambiar de app, el auto-scroll se pausa y permanece pausado al volver. | **PASS** |
| **16** | **Operación sin JavaScript** | Con JavaScript desactivado, la lectura, los acordes y la navegación de canciones funcionan plenamente desde el servidor. | **PASS** |

---

## 4. Limitaciones Encontradas y Consideraciones

1. **Navegadores con scroll suave desactivado o no soportado:** En navegadores antiguos (iOS 9 / Android 4.4), el salto por bloques se realiza de forma instantánea (`window.scrollTo(0, targetY)`), lo cual previene excepciones y garantiza funcionamiento fiable.
2. **Modo incógnito estricto:** En modos privados donde el acceso a `localStorage` lanza excepción de seguridad, el sistema degrada silenciosamente a memoria de sesión sin arrojar errores.
3. **Pausado manual por scrollbar nativa:** En navegadores de escritorio donde el usuario arrastra la barra de scroll nativa del sistema operativo, el auto-scroll se pausa en cuanto detecta un delta mayor a 20 px respecto a la coordenada esperada.

---

> **Principio rector:** *"El músico controla Fogata; Fogata nunca debe luchar contra el músico."*
