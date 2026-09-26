# 🔥 FOGATA — Informe de Aceptación y Validación Fase 1.1
## Validación Real del Parser y Flujo de Carga

**Fecha de validación:** 26 de septiembre de 2026  
**Alcance:** Validación real del flujo *copiar → pegar → guardar → tocar*, robustez ante los formatos habituales (A al F), simplificación del formulario y confirmación de estabilidad.  
**Estado general:** **APROBADO (15 / 15 pruebas superadas: 11 PASS, 4 CORREGIDO, 0 FAIL)**  

---

## 1. Tabla de Aceptación

| PRUEBA | ESTADO | OBSERVACIÓN |
| :--- | :---: | :--- |
| **1. Preservación de espacios** | **PASS** | Espacios iniciales, intermedios entre acordes y sangrías se conservan exactamente byte por byte al renderizar los `<span>` en servidor. |
| **2. Acordes en líneas independientes** | **PASS** | **Formato A**: Acordes ubicados sobre sílabas en líneas independientes mantienen su posición espacial estricta (`white-space: pre`). |
| **3. Acordes embebidos** | **PASS** | **Formato B**: Reconoce sintaxis `[G]Letra [D]más`. Mantiene los corchetes intactos en el HTML y resalta el acorde sin romper la métrica ni desplazar texto. |
| **4. Progresiones** | **PASS** | **Formato C**: Identifica líneas musicales estructuradas con barras `\| G \| D \|`, guiones `G - D - Em - C` o comas `G, D, Em, C` como líneas de acordes. |
| **5. Notación latina** | **PASS** | **Formato E**: Detecta raíces tradicionales (`Sol`, `Re`, `Mim`, `Do`, `Fa#`, `Lam`), alteraciones y acordes con bajo alterado como `Re/Fa#`. |
| **6. Notación americana** | **PASS** | Reconocimiento completo de notas base anglosajonas (`A`–`G`), sostenidos/bemoles (`#`, `b`), extensiones (`7`, `maj7`, `sus4`, `add9`, `m7b5`) y slash chords (`G/B`). |
| **7. Secciones** | **PASS** | **Formato D**: Encabezados como `[Intro]`, `[Verso]`, `[Coro]`, `Intro:` reciben estilo diferenciado (`.seccion-musical`) sin alterar la altura de línea ni espaciado. |
| **8. Tablaturas** | **CORREGIDO** | **Formato F**: Se ajustó la expresión regular de tablaturas para identificar cuerdas `e\|`, `B\|`, `G\|` con o sin barra de cierre. Las cuerdas no se confunden con acordes y quedan perfectamente legibles e intactas. |
| **9. Contenido desconocido** | **PASS** | Indicaciones de interpretación (`Nota: tocar suave`), afinaciones especiales o texto libre no desaparecen ni causan error: se representan verbatim con escape seguro. |
| **10. Pegado desde navegador** | **CORREGIDO** | El `<textarea>` cuenta con `wrap="off"`, `strip=False` en Django, y atributos móviles `autocapitalize="off"`, `autocorrect="off"`, `autocomplete="off"` y `spellcheck="false"`, impidiendo mayúsculas o correcciones indeseadas al pegar. |
| **11. Edición posterior** | **CORREGIDO** | Se incorporó el botón de flujo directo **🎸 Guardar y Tocar** (`accion_guardar='tocar'`) que lleva de inmediato al atril. Se corrigió el campo `capo` haciéndolo opcional con valor `0` por defecto, permitiendo guardar solo con Título y Contenido sin errores. La edición posterior no altera el texto. |
| **12. Seguridad XSS** | **PASS** | Todo el texto provisto por el usuario pasa por `django.utils.html.escape` antes de inyectar las etiquetas controladas de Fogata. Nunca se aplica `safe` al contenido sin sanear. |
| **13. Funcionamiento sin JavaScript** | **PASS** | El parser y el renderizado se ejecutan 100% en el servidor. La lectura en modo atril, zoom tipográfico base y guardado de canciones funcionan íntegramente con JavaScript desactivado. |
| **14. Visualización móvil** | **PASS** | Contenedor de atril en columna única centrada, tipografía monoespaciada legible, caja con scroll horizontal seguro si una línea excede el ancho, y controles táctiles de 48 px. |
| **15. Visualización tablet** | **CORREGIDO** | Se simplificó el formulario de carga: Título, Artista y Contenido ocupan el primer plano. Los campos secundarios (Tono, Capo, Afinación, Notas) se plegaron en un bloque `<details>` semántico y limpio, maximizando la comodidad en tablets y móviles. |

---

## 2. Ajustes Realizados Durante la Validación

1. **Flujo "Pegar y Tocar" Inmediato**:
   - Se añadió el botón principal `🎸 Guardar y Tocar` en el formulario de creación y edición.
   - Si el usuario lo pulsa, el controlador redirige directamente a la pantalla de atril (`/canciones/<id>/tocar/`).
2. **Simplificación del Formulario (Principio Bloc de Notas)**:
   - Los campos `tonalidad`, `capo`, `afinacion` y `notas_personales` se trasladaron a un contenedor nativo `<details>` desplegable (abierto automáticamente si alguno contiene datos o errores).
   - `capo` fue configurado como `blank=True` en el modelo y opcional en el formulario con valor `0` por defecto, evitando validaciones fallidas si el usuario decide no ingresar cejillo.
3. **Resiliencia en Tablaturas**:
   - La detección de tablaturas fue flexibilizada para reconocer líneas que comiencen con indicador de cuerda (`e|`, `B|`, `G|`, `D|`, `A|`, `E|`) independientemente de si finalizan en barra de compás `|` o no.
4. **Protección en Dispositivos Móviles al Pegar**:
   - Se agregaron atributos `autocapitalize="off"`, `autocorrect="off"`, `autocomplete="off"` y `spellcheck="false"` al `<textarea>` para prevenir alteraciones involuntarias de teclados virtuales.

---

## 3. Estado de la Suite de Pruebas

```text
Found 40 test(s).
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
........................................
----------------------------------------------------------------------
Ran 40 tests in 0.049s

OK
```

- **Pruebas Totales:** 40
- **Fase 1.1 Pruebas Específicas:** 15
- **Tiempo de Ejecución:** ~0.05 segundos
- **Dependencias Externas:** 0 (100% recursos locales, SQLite, Django 5.2 LTS)

---

## 4. Principio Rector Cumplido

> **"Fogata debe hacer que cargar una canción sea casi tan fácil como pegarla en un bloc de notas."**
