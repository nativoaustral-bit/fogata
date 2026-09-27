"""
Módulo de Detección y Análisis de Contenido Musical (Fase 1).
Implementa un parser server-side no destructivo, independiente del idioma,
con separación estricta entre la estructura de datos (LineaMusical, AcordeToken)
y la generación segura de HTML en tiempo de renderizado.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from django.utils.html import escape
from django.utils.safestring import mark_safe


# =============================================================================
# 1. Estructuras de Datos (Modelo Intermedio)
# =============================================================================

@dataclass
class AcordeToken:
    """
    Representa un acorde detectado dentro de una línea.
    Preserva el texto original y descompone sus partes para funciones futuras
    (transposición, cambio de notación, diagramas).
    """
    texto_original: str
    nota_raiz: str
    alteracion: str
    modificador: str
    bajo_slash: str
    columna_inicio: int
    columna_fin: int
    es_embebido: bool = False


@dataclass
class LineaMusical:
    """
    Representa una línea analizada con su clasificación y sus tokens musicales.
    Tipos posibles:
      - 'vacia': línea en blanco o solo espacios
      - 'seccion': encabezados como [Intro], [Coro], [Verse], Intro:, etc.
      - 'acordes': línea compuesta primordialmente por acordes y separadores
      - 'embebida': línea de letra con acordes entre corchetes ([G]Palabra)
      - 'tablatura': líneas con tablatura instrumental (e|---, -----)
      - 'letra': texto de letra común sin acordes aislados
    """
    tipo: str
    texto_original: str
    tokens_acorde: List[AcordeToken] = field(default_factory=list)


# =============================================================================
# 2. Expresiones Regulares y Gramática Musical
# =============================================================================

# Raíces: Notación Americana (A-G) y Latina (Do, Re, Mi, Fa, Sol, La, Si).
# Ordenadas con Sol antes de Si/La para coincidencia greedy correcta.
PATRON_RAIZ = r'(?:Sol|sol|SOL|Do|do|DO|Re|re|RE|Mi|mi|MI|Fa|fa|FA|La|la|LA|Si|si|SI|[A-Ga-g])'
PATRON_ACCIDENTAL = r'[#b♯♭]'

# Modificadores (Sensible a mayúsculas/minúsculas para diferenciar M7 de m7)
# maj, min, m, M, dim, aug, sus, add, números y alteraciones
PATRON_MODIFICADOR = (
    r'(?:'
    r'maj7|maj9|maj11|maj13|maj|'
    r'min7|min9|min|'
    r'm7b5|m7|m9|m11|m13|m6|m\(maj7\)|m/maj7|m|'
    r'M7|M9|M11|M13|M|'
    r'dim7|dim|aug|\+|°|ø|'
    r'sus2|sus4|7sus4|7sus2|sus|'
    r'add9|add2|add4|add11|add|'
    r'6/9|69|6|'
    r'7#5|7b5|7#9|7b9|7\+5|7-5|'
    r'2|4|5|7|9|11|13|'
    r'Δ7|Δ'
    r')'
)

# Bajo alterado (Slash Chord): /G, /Fa#, /C, etc.
PATRON_BAJO = rf'(?:/(?:{PATRON_RAIZ})(?:{PATRON_ACCIDENTAL})?)'

# Regex completa de un acorde individual
REGEX_ACORDE_COMPLETO = re.compile(
    rf'^(?P<raiz>{PATRON_RAIZ})'
    rf'(?P<accidental>{PATRON_ACCIDENTAL})?'
    rf'(?P<modificador>{PATRON_MODIFICADOR})?'
    rf'(?P<bajo>{PATRON_BAJO})?$'
)

# Regex para acordes embebidos entre corchetes: [G], [C#m7], [Sol/Si]
REGEX_ACORDE_EMBEBIDO = re.compile(
    rf'\[(?P<contenido>(?:{PATRON_RAIZ})(?:{PATRON_ACCIDENTAL})?(?:{PATRON_MODIFICADOR})?(?:{PATRON_BAJO})?)\]'
)

# Encabezados de sección universales (independientes del idioma)
REGEX_SECCION = re.compile(
    r'^\s*(?:'
    r'\[(?:Intro|Verso|Verse|Coro|Chorus|Puente|Bridge|Estribillo|Outro|Final|Solo|Interludio|Pre-Coro|Pre-Chorus|Coda|Intro\s+\d+|Verso\s+\d+|Verse\s+\d+|Coro\s+\d+|Chorus\s+\d+)[^\]]*\]|'
    r'(?:Intro|Verso|Verse|Coro|Chorus|Puente|Bridge|Estribillo|Outro|Final|Solo|Interludio|Pre-Coro|Pre-Chorus|Coda)\s*:\s*$'
    r')',
    re.IGNORECASE
)

# Tablaturas: líneas con marcas características de cuerdas o guiones repetidos
REGEX_TABLATURA = re.compile(
    r'(?:^[eBGDAE]\|[-0-9hpbr/\\~| ]+|[-]{4,})'
)

# Separadores musicales aceptados en líneas de acordes (espacios, barras, guiones, comas, repeticiones)
SEPARADORES_MUSICALES = {
    '|', '||', '-', '--', '—', '/', '//', '\\', ',', ':', '.',
    'x2', 'x3', 'x4', '(x2)', '(x3)', '(x4)', '%', 'x'
}


# =============================================================================
# 3. Funciones de Validación de Acordes
# =============================================================================

def validar_token_acorde(token_str: str) -> Optional[Tuple[str, str, str, str]]:
    """
    Verifica si una cadena de texto es formalmente un acorde musical válido.
    Retorna una tupla (raiz, accidental, modificador, bajo) o None si no es acorde.
    """
    token_limpio = token_str.strip()
    if not token_limpio:
        return None

    match = REGEX_ACORDE_COMPLETO.match(token_limpio)
    if not match:
        return None

    raiz = match.group('raiz')
    accidental = match.group('accidental') or ''
    modificador = match.group('modificador') or ''
    bajo = match.group('bajo') or ''
    if bajo.startswith('/'):
        bajo = bajo[1:]

    return (raiz, accidental, modificador, bajo)


# =============================================================================
# 3.1. Teoría Musical, Clases de Altura y Transposición (Fase 3)
# =============================================================================

PITCH_CLASSES_SHARP_AMERICAN = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
PITCH_CLASSES_FLAT_AMERICAN  = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

PITCH_CLASSES_SHARP_LATIN    = ['Do', 'Do#', 'Re', 'Re#', 'Mi', 'Fa', 'Fa#', 'Sol', 'Sol#', 'La', 'La#', 'Si']
PITCH_CLASSES_FLAT_LATIN     = ['Do', 'Reb', 'Re', 'Mib', 'Mi', 'Fa', 'Solb', 'Sol', 'Lab', 'La', 'Sib', 'Si']

MAPA_RAIZ_A_PITCH = {
    'C': 0, 'DO': 0,
    'D': 2, 'RE': 2,
    'E': 4, 'MI': 4,
    'F': 5, 'FA': 5,
    'G': 7, 'SOL': 7,
    'A': 9, 'LA': 9,
    'B': 11, 'SI': 11,
}

TONALIDADES_BEMOLES = {
    'F', 'BB', 'EB', 'AB', 'DB', 'GB',
    'DM', 'GM', 'CM', 'FM', 'BBM', 'EBM',
    'FA', 'SIB', 'MIB', 'LAB', 'REB', 'SOLB',
    'REM', 'SOLM', 'DOM', 'FAM', 'SIBM'
}


def obtener_pitch_class(raiz: str, accidental: str = '') -> Optional[int]:
    """
    Calcula la clase de altura cromática (0..11) a partir de la raíz y alteración.
    """
    if not raiz:
        return None
    base = MAPA_RAIZ_A_PITCH.get(raiz.upper())
    if base is None:
        return None
    if accidental in ('#', '♯'):
        return (base + 1) % 12
    elif accidental in ('b', '♭'):
        return (base - 1) % 12
    return base


def pitch_class_a_nota(pitch: int, usar_bemoles: bool = False, notacion: str = 'american') -> str:
    """
    Convierte una clase de altura (0..11) a su nombre de nota según la armadura
    y el sistema de notación (americana o latina). Evita enarmónicos no prácticos
    (E#, B#, Cb, Fb).
    """
    pitch = pitch % 12
    if notacion == 'latin':
        if usar_bemoles:
            return PITCH_CLASSES_FLAT_LATIN[pitch]
        return PITCH_CLASSES_SHARP_LATIN[pitch]
    else:
        if usar_bemoles:
            return PITCH_CLASSES_FLAT_AMERICAN[pitch]
        return PITCH_CLASSES_SHARP_AMERICAN[pitch]


def determinar_preferencia_alteraciones(
    contenido: str = '',
    tonalidad: Optional[str] = None,
    semitonos: int = 0
) -> bool:
    """
    Política determinista única (Criterio 6):
      1. Prioridad: tonalidad explícita si existe.
      2. Prioridad: conteo predominante de bemoles vs sostenidos en acordes de la canción.
      3. Prioridad: neutral según dirección de transposición (negativa -> bemoles, positiva -> sostenidos).
    Retorna True si debe preferirse bemoles, False para sostenidos.
    """
    if tonalidad:
        t_clean = tonalidad.strip().upper()
        if 'B' in t_clean or '♭' in t_clean or t_clean in TONALIDADES_BEMOLES:
            return True
        if '#' in t_clean or '♯' in t_clean:
            return False

    if contenido:
        lineas = parse_cancion(contenido)
        count_bemoles = 0
        count_sostenidos = 0
        for l in lineas:
            for t in l.tokens_acorde:
                if t.alteracion in ('b', '♭') or 'b' in t.bajo_slash:
                    count_bemoles += 1
                if t.alteracion in ('#', '♯') or '#' in t.bajo_slash:
                    count_sostenidos += 1
        if count_bemoles > count_sostenidos:
            return True
        if count_sostenidos > count_bemoles:
            return False

    return semitonos < 0


def transponer_y_formatear_token(
    token: AcordeToken,
    semitonos: int = 0,
    usar_bemoles: bool = False,
    notacion: str = 'original'
) -> str:
    """
    Transforma un AcordeToken aplicando desplazamiento de semitonos (-6 a +6)
    y representación visual ('american', 'latin', o 'original').
    Conserva modificadores (m, 7, maj7, etc.) y transpone el bajo slash si existe.
    """
    if semitonos == 0 and notacion == 'original':
        return token.texto_original

    target_notacion = notacion
    if target_notacion == 'original':
        target_notacion = 'latin' if token.nota_raiz.capitalize() in ('Do', 'Re', 'Mi', 'Fa', 'Sol', 'La', 'Si') else 'american'

    pitch_raiz = obtener_pitch_class(token.nota_raiz, token.alteracion)
    if pitch_raiz is None:
        return token.texto_original

    nuevo_pitch_raiz = (pitch_raiz + semitonos) % 12
    nueva_raiz = pitch_class_a_nota(nuevo_pitch_raiz, usar_bemoles, target_notacion)

    nuevo_bajo = ''
    if token.bajo_slash:
        val_bajo = validar_token_acorde(token.bajo_slash)
        if val_bajo:
            r_b, acc_b, _, _ = val_bajo
            pitch_b = obtener_pitch_class(r_b, acc_b)
            if pitch_b is not None:
                nuevo_pitch_b = (pitch_b + semitonos) % 12
                nb = pitch_class_a_nota(nuevo_pitch_b, usar_bemoles, target_notacion)
                nuevo_bajo = '/' + nb
        else:
            nuevo_bajo = '/' + token.bajo_slash

    return f"{nueva_raiz}{token.modificador}{nuevo_bajo}"


def transponer_acorde_str(
    acorde_str: str,
    semitonos: int = 0,
    usar_bemoles: bool = False,
    notacion: str = 'original'
) -> str:
    """
    Helper para transponer y formatear una cadena de acorde individual aislada.
    """
    val = validar_token_acorde(acorde_str)
    if not val:
        return acorde_str
    r, acc, mod, bajo = val
    dummy = AcordeToken(
        texto_original=acorde_str,
        nota_raiz=r,
        alteracion=acc,
        modificador=mod,
        bajo_slash=bajo,
        columna_inicio=0,
        columna_fin=len(acorde_str)
    )
    return transponer_y_formatear_token(dummy, semitonos, usar_bemoles, notacion)


def transponer_tonalidad(
    tonalidad: Optional[str],
    semitonos: int = 0,
    usar_bemoles: bool = False,
    notacion: str = 'original'
) -> Optional[str]:
    """
    Transpone una tonalidad si es válida (ej: 'G' -> 'A', 'Em' -> 'F#m').
    """
    if not tonalidad or not tonalidad.strip():
        return None
    val = validar_token_acorde(tonalidad.strip())
    if not val:
        return tonalidad.strip()
    return transponer_acorde_str(tonalidad.strip(), semitonos, usar_bemoles, notacion)


# =============================================================================
# 3.2. Preservación Espacial y Edición de Acordes (Fase 3)
# =============================================================================

def compensar_espacios_en_linea(
    linea_texto: str,
    col_inicio: int,
    col_fin: int,
    texto_original: str,
    nuevo_acorde: str,
    es_embebido: bool = False
) -> str:
    """
    Reemplaza texto_original por nuevo_acorde en linea_texto conservando
    la alineación horizontal de los acordes o texto subsiguiente (Criterio 4).

    - Acordes embebidos ([G]Texto -> [Gmaj7]Texto): sin compensación espacial.
    - Acordes aislados (G      D -> Gmaj7  D):
      * Si nuevo_acorde es más largo, absorbe hasta 'diff' espacios inmediatamente
        posteriores si existen suficientes espacios para no fusionar con el siguiente elemento.
      * Si nuevo_acorde es más corto, inserta espacios compensatorios.
      * NUNCA elimina otro acorde ni letra.
    """
    if es_embebido:
        return linea_texto[:col_inicio] + nuevo_acorde + linea_texto[col_fin:]

    diff = len(nuevo_acorde) - len(texto_original)

    if diff == 0:
        return linea_texto[:col_inicio] + nuevo_acorde + linea_texto[col_fin:]

    if diff < 0:
        # El nuevo acorde es más corto: insertar espacios compensatorios
        espacios_extra = ' ' * (-diff)
        return linea_texto[:col_inicio] + nuevo_acorde + espacios_extra + linea_texto[col_fin:]

    # diff > 0: El nuevo acorde es más largo
    resto = linea_texto[col_fin:]
    num_espacios_disponibles = len(resto) - len(resto.lstrip(' '))

    # Si hay suficientes espacios inmediatamente después para absorber el crecimiento:
    if num_espacios_disponibles >= diff:
        # Absorber exactamente 'diff' espacios
        return linea_texto[:col_inicio] + nuevo_acorde + linea_texto[col_fin + diff:]
    else:
        # No hay suficientes espacios para absorber sin colisionar o no hay espacios:
        # Permitir desplazamiento sin eliminar texto ni caracteres subsiguientes
        return linea_texto[:col_inicio] + nuevo_acorde + linea_texto[col_fin:]


def reemplazar_acorde_en_contenido(
    contenido: str,
    num_linea: int,
    col_inicio: int,
    col_fin: int,
    texto_original: str,
    nuevo_acorde: str,
    modo: str = 'uno'
) -> Tuple[bool, str, str]:
    """
    Aplica una edición rápida sobre el contenido de la canción validando concurrencia
    e integridad (Criterios 2, 3, 4, 5).

    Retorna: (exito, nuevo_contenido, mensaje_error)
    """
    nuevo_acorde_limpio = nuevo_acorde.strip()
    if not nuevo_acorde_limpio:
        return (False, contenido, "El acorde no puede estar vacío.")

    # 1. Validar que el nuevo acorde sea formalmente reconocido
    if not validar_token_acorde(nuevo_acorde_limpio):
        return (
            False,
            contenido,
            "No reconocemos este acorde. Puedes editar la canción completa si necesitas una notación especial."
        )

    lineas = contenido.splitlines()

    # 2. Validar concurrencia e integridad sobre la aparición seleccionada
    if num_linea < 0 or num_linea >= len(lineas):
        return (
            False,
            contenido,
            "La canción cambió desde que abriste el editor. Recarga antes de modificar este acorde."
        )

    linea_actual = lineas[num_linea]
    if col_inicio < 0 or col_fin > len(linea_actual):
        return (
            False,
            contenido,
            "La canción cambió desde que abriste el editor. Recarga antes de modificar este acorde."
        )

    fragmento_actual = linea_actual[col_inicio:col_fin]
    if fragmento_actual != texto_original:
        return (
            False,
            contenido,
            "La canción cambió desde que abriste el editor. Recarga antes de modificar este acorde."
        )

    # 3. Modo 'uno': reemplazar solo la aparición seleccionada
    if modo == 'uno':
        linea_analizada = analizar_linea(linea_actual)
        es_embebido = linea_analizada.tipo == 'embebida'
        lineas[num_linea] = compensar_espacios_en_linea(
            linea_actual,
            col_inicio,
            col_fin,
            texto_original,
            nuevo_acorde_limpio,
            es_embebido=es_embebido
        )
        nuevo_contenido = "\n".join(lineas)
        return (True, nuevo_contenido, "")

    # 4. Modo 'todos': reemplazar todas las apariciones equivalentes basadas en AcordeToken
    if modo == 'todos':
        lineas_musicales = parse_cancion(contenido)
        nuevas_lineas = []

        for idx, lm in enumerate(lineas_musicales):
            tokens_coincidentes = [
                t for t in lm.tokens_acorde
                if t.texto_original == texto_original
            ]

            if not tokens_coincidentes:
                nuevas_lineas.append(lm.texto_original)
                continue

            # Procesar de derecha a izquierda para preservar índices anteriores
            tokens_ordenados = sorted(
                tokens_coincidentes,
                key=lambda t: t.columna_inicio,
                reverse=True
            )

            texto_linea = lm.texto_original
            for tok in tokens_ordenados:
                texto_linea = compensar_espacios_en_linea(
                    texto_linea,
                    tok.columna_inicio,
                    tok.columna_fin,
                    tok.texto_original,
                    nuevo_acorde_limpio,
                    es_embebido=tok.es_embebido
                )

            nuevas_lineas.append(texto_linea)

        nuevo_contenido = "\n".join(nuevas_lineas)
        return (True, nuevo_contenido, "")

    return (False, contenido, "Modo de reemplazo no válido.")


# =============================================================================
# 4. Clasificador y Parser Línea a Línea
# =============================================================================

def analizar_linea(linea: str) -> LineaMusical:
    """
    Analiza una sola línea de texto y la convierte en una instancia de LineaMusical
    con su clasificación y lista de AcordeTokens identificados.
    """
    # 1. Línea vacía
    if not linea.strip():
        return LineaMusical(tipo='vacia', texto_original=linea)

    # 2. Encabezado de Sección
    if REGEX_SECCION.match(linea):
        return LineaMusical(tipo='seccion', texto_original=linea)

    # 3. Tablatura
    if REGEX_TABLATURA.search(linea):
        return LineaMusical(tipo='tablatura', texto_original=linea)

    # 4. Acordes embebidos en corchetes [G]Letra [D]mas
    matches_embebidos = list(REGEX_ACORDE_EMBEBIDO.finditer(linea))
    if matches_embebidos:
        tokens_embebidos: List[AcordeToken] = []
        for m in matches_embebidos:
            contenido = m.group('contenido')
            val = validar_token_acorde(contenido)
            if val:
                raiz, acc, mod, bajo = val
                tokens_embebidos.append(AcordeToken(
                    texto_original=contenido,
                    nota_raiz=raiz,
                    alteracion=acc,
                    modificador=mod,
                    bajo_slash=bajo,
                    columna_inicio=m.start(1),
                    columna_fin=m.end(1),
                    es_embebido=True
                ))
        if tokens_embebidos:
            return LineaMusical(
                tipo='embebida',
                texto_original=linea,
                tokens_acorde=tokens_embebidos
            )

    # 5. Análisis de Línea de Acordes Aislada
    # Extraemos palabras/tokens y sus posiciones sin dividir slash chords (ej: G/B, Re/Fa#)
    tokens_raw: List[Tuple[str, int, int]] = []
    for m in re.finditer(r'[^\s,\|\-—]+|[,\|\-—]+', linea):
        tokens_raw.append((m.group(0), m.start(), m.end()))

    if not tokens_raw:
        return LineaMusical(tipo='vacia', texto_original=linea)

    tokens_musicales: List[AcordeToken] = []
    total_sustantivos = 0
    total_acordes_validos = 0
    tiene_palabra_larga_no_musical = False

    for token_texto, start_col, end_col in tokens_raw:
        # Si es un separador musical permitido (, | - / x2)
        if token_texto in SEPARADORES_MUSICALES or re.match(r'^x\d+$', token_texto):
            continue

        total_sustantivos += 1

        # Palabras de más de 8 caracteres difícilmente son acordes si no tienen slash
        if len(token_texto) > 8 and '/' not in token_texto:
            tiene_palabra_larga_no_musical = True

        val = validar_token_acorde(token_texto)
        if val:
            raiz, acc, mod, bajo = val
            total_acordes_validos += 1
            tokens_musicales.append(AcordeToken(
                texto_original=token_texto,
                nota_raiz=raiz,
                alteracion=acc,
                modificador=mod,
                bajo_slash=bajo,
                columna_inicio=start_col,
                columna_fin=end_col,
                es_embebido=False
            ))

    # Criterio independiente de idioma para determinar si la línea es de acordes:
    # 1. No debe tener palabras largas que correspondan a prosa.
    # 2. Debe tener al menos 1 acorde válido.
    # 3. La proporción de tokens válidos respecto a tokens sustantivos debe ser >= 70%
    #    (o 100% si hay solo 1 o 2 tokens sustantivos).
    if total_sustantivos > 0 and not tiene_palabra_larga_no_musical:
        ratio = total_acordes_validos / total_sustantivos
        es_linea_acordes = False

        if total_sustantivos == 1 and total_acordes_validos == 1:
            # Caso especial: un único token en la línea.
            # Evitar falsos positivos si es una sola letra ambigua en minúscula (ej: "a", "y")
            # A menos que sea un acorde claro con alteración/modificador (ej: "Am", "G", "C#", "Do")
            unico = tokens_musicales[0]
            if len(unico.texto_original) > 1 or unico.nota_raiz.isupper() or unico.alteracion or unico.modificador:
                es_linea_acordes = True
        elif total_sustantivos > 1 and ratio >= 0.70:
            es_linea_acordes = True

        if es_linea_acordes:
            return LineaMusical(
                tipo='acordes',
                texto_original=linea,
                tokens_acorde=tokens_musicales
            )

    # 6. En cualquier otro caso, se considera letra de canción
    return LineaMusical(tipo='letra', texto_original=linea)


def parse_cancion(contenido: str) -> List[LineaMusical]:
    """
    Analiza una canción completa línea por línea, produciendo una lista de LineaMusical.
    NO altera el contenido original ni los saltos de línea.
    """
    if not contenido:
        return []
    lineas = contenido.splitlines()
    return [analizar_linea(l) for l in lineas]


# =============================================================================
# 5. Generador Seguro de HTML (Renderizado en Servidor)
# =============================================================================

def render_linea_html(
    linea: LineaMusical,
    semitonos: int = 0,
    usar_bemoles: bool = False,
    notacion: str = 'original',
    incluir_metadata: bool = False,
    modo_edicion: bool = False,
    linea_idx: int = 0,
    cancion_id: Optional[int] = None,
    fogata_id: Optional[int] = None,
    pos: Optional[int] = None
) -> str:
    """
    Genera el HTML seguro para una sola línea a partir de su estructura LineaMusical.
    Todo el texto del usuario se escapa antes de insertar etiquetas controladas.
    Permite transposición en servidor, selección de notación y metadata para JS / edición rápida / diagramas.
    """
    texto = linea.texto_original

    # Líneas vacías
    if linea.tipo == 'vacia':
        return ""

    # Secciones ([Intro], [Coro], etc.)
    if linea.tipo == 'seccion':
        return f'<span class="seccion-musical">{escape(texto)}</span>'

    # Tablaturas y Letra común: texto escapado preservando espacios
    if linea.tipo in ('letra', 'tablatura') or not linea.tokens_acorde:
        return escape(texto)

    # Líneas con acordes (aislados o embebidos)
    partes: List[str] = []
    cursor = 0

    for token in linea.tokens_acorde:
        # Texto antes del acorde
        if token.columna_inicio > cursor:
            partes.append(escape(texto[cursor:token.columna_inicio]))

        # Calcular representación transpuesta y notación
        acorde_transpuesto = transponer_y_formatear_token(
            token,
            semitonos=semitonos,
            usar_bemoles=usar_bemoles,
            notacion=notacion
        )
        acorde_escapado = escape(acorde_transpuesto)

        if not incluir_metadata and not modo_edicion and not cancion_id:
            partes.append(f'<span class="acorde">{acorde_escapado}</span>')
        else:
            # Metadata estructurada para cliente JS (Criterios 1, 8, 10, 15)
            pitch_raiz = obtener_pitch_class(token.nota_raiz, token.alteracion)
            data_root = str(pitch_raiz) if pitch_raiz is not None else ""
            data_mod = escape(token.modificador)

            data_bass = ""
            if token.bajo_slash:
                val_b = validar_token_acorde(token.bajo_slash)
                if val_b:
                    p_b = obtener_pitch_class(val_b[0], val_b[1])
                    if p_b is not None:
                        data_bass = str(p_b)

            anchor_id = f"acorde-l{linea_idx}-c{token.columna_inicio}"

            attrs = [
                'class="acorde' + (' acorde-editable' if modo_edicion else '') + '"',
                f'id="{anchor_id}"',
                f'data-root="{data_root}"',
                f'data-mod="{data_mod}"',
                f'data-bass="{data_bass}"',
                f'data-original="{escape(token.texto_original)}"'
            ]

            if modo_edicion:
                attrs.extend([
                    f'data-linea="{linea_idx}"',
                    f'data-inicio="{token.columna_inicio}"',
                    f'data-fin="{token.columna_fin}"',
                    f'data-embebido="{"1" if token.es_embebido else "0"}"',
                    'role="button"',
                    'tabindex="0"'
                ])
                attr_str = " ".join(attrs)
                partes.append(f'<span {attr_str}>{acorde_escapado}</span>')
            else:
                # Modo Atril / Tocar: interactivo para consulta de diagramas (Fase 4)
                attrs.extend([
                    'role="button"',
                    'tabindex="0"',
                    f'title="Ver diagrama de {acorde_escapado}"'
                ])
                attr_str = " ".join(attrs)

                if cancion_id:
                    # Enlace semántico accesible para fallback 100% funcional sin JavaScript (Criterio 15)
                    # En transposición, el enlace de fallback apunta al pitch efectivo
                    eff_root = (pitch_raiz + semitonos) % 12 if pitch_raiz is not None else ""
                    eff_bass = ""
                    if data_bass != "":
                        try:
                            eff_bass = str((int(data_bass) + semitonos) % 12)
                        except ValueError:
                            eff_bass = ""

                    params = [
                        f"root={eff_root}",
                        f"mod={data_mod}",
                        f"bass={eff_bass}",
                        f"notacion={'latin' if notacion == 'latin' else 'american'}",
                        f"semitonos={semitonos}",
                        f"cancion_id={cancion_id}",
                        f"anchor={anchor_id}"
                    ]
                    if fogata_id:
                        params.append(f"fogata_id={fogata_id}")
                    if pos:
                        params.append(f"pos={pos}")

                    fallback_url = f"/canciones/diagrama/?{'&'.join(params)}"
                    partes.append(f'<a href="{fallback_url}" class="acorde-link"><span {attr_str}>{acorde_escapado}</span></a>')
                else:
                    partes.append(f'<span {attr_str}>{acorde_escapado}</span>')

        cursor = token.columna_fin

    # Texto restante después del último acorde
    if cursor < len(texto):
        partes.append(escape(texto[cursor:]))

    return "".join(partes)


def render_cancion_html(
    contenido: str,
    semitonos: int = 0,
    notacion: str = 'original',
    incluir_metadata: bool = False,
    modo_edicion: bool = False,
    tonalidad: Optional[str] = None,
    cancion_id: Optional[int] = None,
    fogata_id: Optional[int] = None,
    pos: Optional[int] = None
) -> str:
    """
    Renderiza la canción completa en HTML seguro con preservación de acordes.
    El resultado final se marca como safe ÚNICAMENTE después de haber escapado
    rigurosamente todo el contenido del usuario.
    """
    if not contenido:
        return ""

    # Clampeo de semitonos (-6 a +6)
    semitonos_val = max(-6, min(6, semitonos))
    usar_bemoles = determinar_preferencia_alteraciones(contenido, tonalidad, semitonos_val)

    lineas_musicales = parse_cancion(contenido)
    lineas_html = [
        render_linea_html(
            linea=l,
            semitonos=semitonos_val,
            usar_bemoles=usar_bemoles,
            notacion=notacion,
            incluir_metadata=incluir_metadata,
            modo_edicion=modo_edicion,
            linea_idx=idx,
            cancion_id=cancion_id,
            fogata_id=fogata_id,
            pos=pos
        )
        for idx, l in enumerate(lineas_musicales)
    ]
    return mark_safe("\n".join(lineas_html))



# =============================================================================
# 6. Servicios y Helpers
# =============================================================================

def extraer_acordes_unicos(
    lineas: List[LineaMusical],
    semitonos: int = 0,
    usar_bemoles: bool = False,
    notacion: str = 'original'
) -> List[str]:
    """
    Extrae la lista ordenada de acordes únicos detectados en la canción,
    reflejando la transposición y notación visual activa (Criterio 16).
    """
    vistos = set()
    acordes_unicos = []
    for l in lineas:
        for t in l.tokens_acorde:
            acorde_formateado = transponer_y_formatear_token(
                t,
                semitonos=semitonos,
                usar_bemoles=usar_bemoles,
                notacion=notacion
            )
            if acorde_formateado not in vistos:
                vistos.add(acorde_formateado)
                acordes_unicos.append(acorde_formateado)
    return acordes_unicos


def extraer_solo_letra(contenido: str) -> str:
    """
    Helper tolerante para el Modo Invitado (futuro).
    Elimina líneas compuestas solo por acordes y tablaturas, y limpia
    acordes embebidos [G] dejando únicamente la letra, sin alterar el texto base.
    """
    if not contenido:
        return ""

    lineas_musicales = parse_cancion(contenido)
    lineas_letra: List[str] = []

    for l in lineas_musicales:
        if l.tipo in ('acordes', 'tablatura'):
            continue
        elif l.tipo == 'embebida':
            # Quitar [Acorde] dejando el resto de la letra
            texto_limpio = REGEX_ACORDE_EMBEBIDO.sub('', l.texto_original)
            lineas_letra.append(texto_limpio)
        else:
            lineas_letra.append(l.texto_original)

    return "\n".join(lineas_letra)

