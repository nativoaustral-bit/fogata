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

def render_linea_html(linea: LineaMusical) -> str:
    """
    Genera el HTML seguro para una sola línea a partir de su estructura LineaMusical.
    Todo el texto del usuario se escapa antes de insertar etiquetas controladas.
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

        # Acorde resaltado de forma controlada
        acorde_escapado = escape(token.texto_original)
        partes.append(f'<span class="acorde">{acorde_escapado}</span>')

        cursor = token.columna_fin

    # Texto restante después del último acorde
    if cursor < len(texto):
        partes.append(escape(texto[cursor:]))

    return "".join(partes)


def render_cancion_html(contenido: str) -> str:
    """
    Renderiza la canción completa en HTML seguro con preservación de acordes.
    El resultado final se marca como safe ÚNICAMENTE después de haber escapado
    rigurosamente todo el contenido del usuario.
    """
    if not contenido:
        return ""

    lineas_musicales = parse_cancion(contenido)
    lineas_html = [render_linea_html(l) for l in lineas_musicales]
    return mark_safe("\n".join(lineas_html))


# =============================================================================
# 6. Servicios y Helpers Futuros
# =============================================================================

def extraer_acordes_unicos(lineas: List[LineaMusical]) -> List[str]:
    """
    Extrae la lista ordenada de acordes únicos detectados en la canción.
    Preparado para futuras funciones de diagramas de acordes.
    """
    vistos = set()
    acordes_unicos = []
    for l in lineas:
        for t in l.tokens_acorde:
            if t.texto_original not in vistos:
                vistos.add(t.texto_original)
                acordes_unicos.append(t.texto_original)
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
