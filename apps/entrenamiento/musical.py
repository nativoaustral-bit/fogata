"""
Motor Musical y Banco de Ejercicios para «Entrena tu oído» (Fogata).
Maneja la lógica de afinación estándar (EADGBE), cálculo físico de frecuencias,
resolución de posiciones exactas en el diapasón, banco de acordes y progresiones armónicas.
Cero dependencias externas.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from django.utils.html import escape
from django.utils.safestring import mark_safe

from apps.canciones.diagramas import (
    DigitacionAcorde,
    generar_svg_acorde,
    buscar_digitacion,
)


# =============================================================================
# 1. Afinación Estándar y Mapeo Físico de Cuerdas (EADGBE)
# =============================================================================

# Cuerdas numeradas 1 (Mi agudo) a 6 (Mi grave).
# Afinación estándar internacional:
# 6ª cuerda: E2 = MIDI 40 (~82.41 Hz)
# 5ª cuerda: A2 = MIDI 45 (110.00 Hz)
# 4ª cuerda: D3 = MIDI 50 (~146.83 Hz)
# 3ª cuerda: G3 = MIDI 55 (~196.00 Hz)
# 2ª cuerda: B3 = MIDI 59 (~246.94 Hz)
# 1ª cuerda: E4 = MIDI 64 (~329.63 Hz)
OPEN_STRINGS_MIDI: Dict[int, int] = {
    6: 40,
    5: 45,
    4: 50,
    3: 55,
    2: 59,
    1: 64,
}

NOMBRES_CUERDAS: Dict[int, str] = {
    6: '6ª cuerda (Mi grave)',
    5: '5ª cuerda (La)',
    4: '4ª cuerda (Re)',
    3: '3ª cuerda (Sol)',
    2: '2ª cuerda (Si)',
    1: '1ª cuerda (Mi agudo)',
}


def midi_a_frecuencia(midi_note: int) -> float:
    """Calcula la frecuencia en Hz en afinación temperada A4 = 440 Hz."""
    return round(440.0 * (2.0 ** ((midi_note - 69) / 12.0)), 2)


# =============================================================================
# 2. Posiciones Físicas en el Mástil
# =============================================================================

@dataclass
class PosicionMastil:
    cuerda: int        # 1 a 6
    traste: int        # 0 (al aire) a 12
    descripcion: str   # ej: "3ª cuerda al aire", "4ª cuerda, traste 5"


def calcular_posiciones_exactas(midi_objetivo: int, max_traste: int = 12) -> List[PosicionMastil]:
    """
    Determina todas las posiciones del mástil (trastes 0 a max_traste) que
    producen EXACTAMENTE la misma altura (mismo MIDI, misma octava).
    No mezcla octavas distintas.
    """
    posiciones: List[PosicionMastil] = []
    # Ordenar de cuerda más aguda (1) a más grave (6) o viceversa para presentación clara
    for cuerda in [1, 2, 3, 4, 5, 6]:
        open_midi = OPEN_STRINGS_MIDI[cuerda]
        traste = midi_objetivo - open_midi
        if 0 <= traste <= max_traste:
            if traste == 0:
                desc = f"{cuerda}ª cuerda al aire"
            else:
                desc = f"{cuerda}ª cuerda, traste {traste}"
            posiciones.append(PosicionMastil(cuerda=cuerda, traste=traste, descripcion=desc))
    return posiciones


def generar_svg_mastil_posiciones(
    posiciones: List[PosicionMastil],
    nombre_nota: str,
    ancho: int = 480,
    alto: int = 150
) -> str:
    """
    Genera un diagrama vectorial horizontal del diapasón de la guitarra mostrando
    las posiciones exactas donde suena la nota.
    Visualización tipo tablatura: 1ª cuerda arriba, 6ª cuerda abajo.
    Trastes 0 (cejuela) al 12.
    """
    vb_w, vb_h = 500, 160
    margin_left = 50
    margin_right = 20
    fretboard_w = vb_w - margin_left - margin_right  # 430px
    top_y = 35
    string_spacing = 18                              # 5 espacios * 18 = 90px de mástil
    bottom_y = top_y + (5 * string_spacing)          # 125px
    num_frets = 12
    fret_w = fretboard_w / num_frets                 # ~35.8px por traste

    nombre_escapado = escape(nombre_nota)
    title_accesible = escape(f"Posiciones de {nombre_nota} en el mástil de la guitarra")

    partes: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vb_w} {vb_h}" '
        f'width="{ancho}" height="{alto}" role="img" class="mastil-posiciones-svg" '
        f'aria-label="{title_accesible}">',
        f'<title>{title_accesible}</title>',
        # Fondo del mástil
        f'<rect x="{margin_left}" y="{top_y - 2}" width="{fretboard_w}" height="{5 * string_spacing + 4}" '
        f'fill="#1c1c1c" rx="4" stroke="#333333" stroke-width="1.2" />',
    ]

    # Cejuela (Nut) gruesa en traste 0
    partes.append(
        f'<line x1="{margin_left}" y1="{top_y - 3}" x2="{margin_left}" y2="{bottom_y + 3}" '
        f'stroke="#d4d4d4" stroke-width="4.5" stroke-linecap="round" />'
    )

    # Trastes (líneas verticales 1..12) y números de traste
    for f in range(1, num_frets + 1):
        fx = margin_left + (f * fret_w)
        partes.append(
            f'<line x1="{fx}" y1="{top_y}" x2="{fx}" y2="{bottom_y}" stroke="#4f4f4f" stroke-width="1.2" />'
        )
        # Etiquetas de trastes clave (3, 5, 7, 9, 12)
        if f in (3, 5, 7, 9, 12):
            partes.append(
                f'<text x="{fx - (fret_w / 2)}" y="{top_y - 10}" text-anchor="middle" '
                f'fill="#888888" font-family="sans-serif" font-size="11" font-weight="600">{f}</text>'
            )

    # Marcadores de posición tradicionales (inlay dots en trastes 3, 5, 7, 9 y doble en 12)
    mid_y = top_y + (2.5 * string_spacing)
    for f in (3, 5, 7, 9):
        cx = margin_left + (f * fret_w) - (fret_w / 2)
        partes.append(f'<circle cx="{cx}" cy="{mid_y}" r="3" fill="#2e2e2e" />')
    # Doble punto en traste 12
    cx12 = margin_left + (12 * fret_w) - (fret_w / 2)
    partes.append(f'<circle cx="{cx12}" cy="{mid_y - 12}" r="2.8" fill="#2e2e2e" />')
    partes.append(f'<circle cx="{cx12}" cy="{mid_y + 12}" r="2.8" fill="#2e2e2e" />')

    # Líneas de cuerdas (horizontales): 1ª cuerda arriba (índice 0), 6ª cuerda abajo (índice 5)
    labels = ['1ª (E)', '2ª (B)', '3ª (G)', '4ª (D)', '5ª (A)', '6ª (E)']
    for c_idx in range(6):
        sy = top_y + (c_idx * string_spacing)
        sw = 1.0 + (c_idx * 0.3)  # cuerdas graves más gruesas
        partes.append(
            f'<line x1="{margin_left}" y1="{sy}" x2="{margin_left + fretboard_w}" y2="{sy}" '
            f'stroke="#5a5a5a" stroke-width="{sw}" />'
        )
        # Etiqueta de la cuerda a la izquierda
        partes.append(
            f'<text x="{margin_left - 10}" y="{sy + 3.5}" text-anchor="end" '
            f'fill="#9e9e9e" font-family="monospace, monospace" font-size="10">{labels[c_idx]}</text>'
        )

    # Dibujar las posiciones marcadas
    for pos in posiciones:
        c_idx = pos.cuerda - 1  # 1ª -> 0, 6ª -> 5
        py = top_y + (c_idx * string_spacing)

        if pos.traste == 0:
            # Cuerda al aire: círculo a la izquierda de la cejuela
            px = margin_left - 18
            partes.append(
                f'<circle cx="{px}" cy="{py}" r="6" fill="#181818" stroke="#ff9800" stroke-width="2.2" />'
            )
            partes.append(
                f'<circle cx="{px}" cy="{py}" r="2" fill="#ff9800" />'
            )
        else:
            # Traste presionado: círculo centrado en el traste correspondiente
            px = margin_left + (pos.traste * fret_w) - (fret_w / 2)
            partes.append(
                f'<circle cx="{px}" cy="{py}" r="7.5" fill="#ff9800" stroke="#ffffff" stroke-width="1.8" />'
            )
            # Traste adentro para máxima claridad
            partes.append(
                f'<text x="{px}" y="{py + 3.8}" text-anchor="middle" fill="#0d0d0d" '
                f'font-family="sans-serif" font-size="9" font-weight="700">{pos.traste}</text>'
            )

    partes.append('</svg>')
    return mark_safe("".join(partes))


# =============================================================================
# 3. Catálogo de Notas (Modalidad 1)
# =============================================================================

@dataclass
class EjercicioNota:
    id: str
    midi: int
    frecuencia: float
    nombre_latino: str
    nombre_americano: str
    octava: int
    posiciones: List[PosicionMastil]
    fretboard_svg: str


# Banco de notas seleccionadas en un registro cómodo para guitarra
# (evita graves extremos y sobreagudos difíciles de discernir en altavoces de celular).
# Rango: D3 (146.83 Hz) hasta G4 (392.00 Hz)
NOTAS_ENTRENAMIENTO = [
    ('D3', 50, 'Re (D3)', 'D3', 3),
    ('E3', 52, 'Mi (E3)', 'E3', 3),
    ('G3', 55, 'Sol (G3)', 'G3', 3),
    ('A3', 57, 'La (A3)', 'A3', 3),
    ('B3', 59, 'Si (B3)', 'B3', 3),
    ('C4', 60, 'Do (C4)', 'C4', 4),
    ('D4', 62, 'Re (D4)', 'D4', 4),
    ('E4', 64, 'Mi (E4)', 'E4', 4),
    ('F4', 65, 'Fa (F4)', 'F4', 4),
    ('G4', 67, 'Sol (G4)', 'G4', 4),
]

# Nota de referencia para orientación auditiva relativa
NOTA_REFERENCIA_DEFAULT = {
    'nombre': 'La (A3 — 220 Hz)',
    'midi': 57,
    'frecuencia': 220.0,
    'descripcion': 'Nota de referencia estándar para situar la altura en el instrumento.'
}


def obtener_catalogo_notas() -> List[EjercicioNota]:
    """Genera el catálogo de ejercicios de notas con sus posiciones y SVGs."""
    catalogo: List[EjercicioNota] = []
    for cod, midi, nom_lat, nom_am, octava in NOTAS_ENTRENAMIENTO:
        posiciones = calcular_posiciones_exactas(midi)
        svg = generar_svg_mastil_posiciones(posiciones, nom_lat)
        catalogo.append(EjercicioNota(
            id=cod,
            midi=midi,
            frecuencia=midi_a_frecuencia(midi),
            nombre_latino=nom_lat,
            nombre_americano=nom_am,
            octava=octava,
            posiciones=posiciones,
            fretboard_svg=svg,
        ))
    return catalogo


# =============================================================================
# 4. Catálogo de Acordes y Posiciones Alternativas (Modalidad 2)
# =============================================================================

@dataclass
class EjercicioAcorde:
    codigo: str
    nombre_latino: str
    nombre_americano: str
    notas_componentes: str
    trastes_referencia: List[int]
    midi_referencia: List[int]
    svg_referencia: str
    trastes_alternativa: List[int]
    midi_alternativa: List[int]
    svg_alternativa: str
    descripcion_alternativa: str


def calcular_midi_cuerdas(trastes: List[int]) -> List[int]:
    """
    Convierte una lista de 6 trastes [6ª..1ª] en sus valores MIDI correspondientes.
    Si traste es -1 (muteada), retorna -1.
    """
    cuerdas_orden = [6, 5, 4, 3, 2, 1]
    res: List[int] = []
    for c_num, t in zip(cuerdas_orden, trastes):
        if t < 0:
            res.append(-1)
        else:
            res.append(OPEN_STRINGS_MIDI[c_num] + t)
    return res


# Las 8 digitaciones esenciales y sus variantes validadas
ACORDES_DATA = [
    {
        'codigo': 'C',
        'nombre_latino': 'Do mayor',
        'nombre_americano': 'C',
        'notas_componentes': 'C – E – G (Do – Mi – Sol)',
        'ref': DigitacionAcorde(trastes=[-1, 3, 2, 0, 1, 0], dedos=[0, 3, 2, 0, 1, 0]),
        'alt': DigitacionAcorde(trastes=[-1, 3, 5, 5, 5, 3], base_fret=3, cejilla=(3, 5, 1)),
        'alt_desc': 'Forma de La (A) con cejilla en el traste 3. Al tocarse en un registro medio, ofrece un sonido más compacto y definido.',
    },
    {
        'codigo': 'G',
        'nombre_latino': 'Sol mayor',
        'nombre_americano': 'G',
        'notas_componentes': 'G – B – D (Sol – Si – Re)',
        'ref': DigitacionAcorde(trastes=[3, 2, 0, 0, 0, 3], dedos=[2, 1, 0, 0, 0, 3]),
        'alt': DigitacionAcorde(trastes=[3, 5, 5, 4, 3, 3], base_fret=3, cejilla=(3, 6, 1)),
        'alt_desc': 'Forma de Mi (E) con cejilla en el traste 3. Muy utilizada para acompañamiento rítmico cerrado y cortes secos.',
    },
    {
        'codigo': 'D',
        'nombre_latino': 'Re mayor',
        'nombre_americano': 'D',
        'notas_componentes': 'D – F# – A (Re – Fa# – La)',
        'ref': DigitacionAcorde(trastes=[-1, -1, 0, 2, 3, 2], dedos=[0, 0, 0, 1, 3, 2]),
        'alt': DigitacionAcorde(trastes=[-1, 5, 7, 7, 7, 5], base_fret=5, cejilla=(5, 5, 1)),
        'alt_desc': 'Forma de La (A) con cejilla en el traste 5. Concentra el sonido en las cuerdas agudas con el bajo en la 5ª cuerda.',
    },
    {
        'codigo': 'A',
        'nombre_latino': 'La mayor',
        'nombre_americano': 'A',
        'notas_componentes': 'A – C# – E (La – Do# – Mi)',
        'ref': DigitacionAcorde(trastes=[-1, 0, 2, 2, 2, 0], dedos=[0, 0, 1, 2, 3, 0]),
        'alt': DigitacionAcorde(trastes=[5, 7, 7, 6, 5, 5], base_fret=5, cejilla=(5, 6, 1)),
        'alt_desc': 'Forma de Mi (E) con cejilla en el traste 5. Brinda un ataque contundente y pleno en frecuencias graves.',
    },
    {
        'codigo': 'E',
        'nombre_latino': 'Mi mayor',
        'nombre_americano': 'E',
        'notas_componentes': 'E – G# – B (Mi – Sol# – Si)',
        'ref': DigitacionAcorde(trastes=[0, 2, 2, 1, 0, 0], dedos=[0, 2, 3, 1, 0, 0]),
        'alt': DigitacionAcorde(trastes=[-1, 7, 9, 9, 9, 7], base_fret=7, cejilla=(7, 5, 1)),
        'alt_desc': 'Forma de La (A) con cejilla en el traste 7. Ideal para complementar arreglos donde otra guitarra ya toca en primera posición.',
    },
    {
        'codigo': 'Am',
        'nombre_latino': 'La menor',
        'nombre_americano': 'Am',
        'notas_componentes': 'A – C – E (La – Do – Mi)',
        'ref': DigitacionAcorde(trastes=[-1, 0, 2, 2, 1, 0], dedos=[0, 0, 2, 3, 1, 0]),
        'alt': DigitacionAcorde(trastes=[5, 7, 7, 5, 5, 5], base_fret=5, cejilla=(5, 6, 1)),
        'alt_desc': 'Forma de Mi menor (Em) con cejilla en el traste 5. Sonoridad oscura, pareja y muy expresiva en acordes rasgueados.',
    },
    {
        'codigo': 'Em',
        'nombre_latino': 'Mi menor',
        'nombre_americano': 'Em',
        'notas_componentes': 'E – G – B (Mi – Sol – Si)',
        'ref': DigitacionAcorde(trastes=[0, 2, 2, 0, 0, 0], dedos=[0, 2, 3, 0, 0, 0]),
        'alt': DigitacionAcorde(trastes=[-1, 7, 9, 9, 8, 7], base_fret=7, cejilla=(7, 5, 1)),
        'alt_desc': 'Forma de La menor (Am) con cejilla en el traste 7. Registro medio-agudo con gran calidez armónica.',
    },
    {
        'codigo': 'Dm',
        'nombre_latino': 'Re menor',
        'nombre_americano': 'Dm',
        'notas_componentes': 'D – F – A (Re – Fa – La)',
        'ref': DigitacionAcorde(trastes=[-1, -1, 0, 2, 3, 1], dedos=[0, 0, 0, 2, 3, 1]),
        'alt': DigitacionAcorde(trastes=[-1, 5, 7, 7, 6, 5], base_fret=5, cejilla=(5, 5, 1)),
        'alt_desc': 'Forma de La menor (Am) con cejilla en el traste 5. Ampliamente utilizada en baladas, boleros y música acústica.',
    },
]


def obtener_catalogo_acordes() -> List[EjercicioAcorde]:
    """Genera el catálogo de acordes con sus diagramas SVG y notas calculadas."""
    catalogo: List[EjercicioAcorde] = []
    for item in ACORDES_DATA:
        ref_dig = item['ref']
        alt_dig = item['alt']
        svg_ref = generar_svg_acorde(ref_dig, nombre_mostrar=item['codigo'], ancho=170, alto=210)
        svg_alt = generar_svg_acorde(alt_dig, nombre_mostrar=f"{item['codigo']} (alt)", ancho=170, alto=210)

        catalogo.append(EjercicioAcorde(
            codigo=item['codigo'],
            nombre_latino=item['nombre_latino'],
            nombre_americano=item['nombre_americano'],
            notas_componentes=item['notas_componentes'],
            trastes_referencia=ref_dig.trastes,
            midi_referencia=calcular_midi_cuerdas(ref_dig.trastes),
            svg_referencia=svg_ref,
            trastes_alternativa=alt_dig.trastes,
            midi_alternativa=calcular_midi_cuerdas(alt_dig.trastes),
            svg_alternativa=svg_alt,
            descripcion_alternativa=item['alt_desc'],
        ))
    return catalogo


# =============================================================================
# 5. Catálogo de Progresiones Armónicas (Modalidad 3)
# =============================================================================

@dataclass
class EjercicioProgresion:
    id: str
    titulo: str
    acordes: List[str]
    acordes_str: str
    explicacion: str
    diagramas_svg: List[str]
    audio_chords: List[List[int]]


PROGRESIONES_DATA = [
    # --- 2 Acordes ---
    {
        'id': 'prog-g-d',
        'titulo': 'Cadencia elemental (Sol mayor)',
        'acordes': ['G', 'D'],
        'explicacion': 'Cadencia auténtica básica (I – V). La brillantez y tensión de Re mayor conduce naturalmente a descansar en Sol mayor.',
    },
    {
        'id': 'prog-am-em',
        'titulo': 'Relación modal menor (La menor)',
        'acordes': ['Am', 'Em'],
        'explicacion': 'Movimiento menor (i – v). Al compartir la nota Mi entre ambos acordes, el cambio se percibe continuo, introspectivo y suave.',
    },
    {
        'id': 'prog-c-g',
        'titulo': 'Movimiento fundamental (Do mayor)',
        'acordes': ['C', 'G'],
        'explicacion': 'Relación de quinta (I – V). Es una de las relaciones armónicas más naturales del oído humano y base del acompañamiento popular.',
    },
    {
        'id': 'prog-d-a',
        'titulo': 'Impulso brillante (Re mayor)',
        'acordes': ['D', 'A'],
        'explicacion': 'Cadencia en Re mayor (I – V). El acorde de La aporta la energía tonal necesaria para resolver de vuelta al reposo de Re.',
    },

    # --- 3 Acordes ---
    {
        'id': 'prog-a-d-e',
        'titulo': 'Fórmula clásica de tres acordes (La mayor)',
        'acordes': ['A', 'D', 'E'],
        'explicacion': 'Progresión I – IV – V en La mayor. Re genera apertura melódica y Mi concentra la tensión que resuelve con fuerza en La.',
    },
    {
        'id': 'prog-g-c-d',
        'titulo': 'Cadencia completa en Sol mayor',
        'acordes': ['G', 'C', 'D'],
        'explicacion': 'Estructura I – IV – V en Sol mayor. Do amplía el espacio sonoro y Re prepara el retorno al tono principal.',
    },
    {
        'id': 'prog-d-g-a',
        'titulo': 'Tríada tonal en Re mayor',
        'acordes': ['D', 'G', 'A'],
        'explicacion': 'La relación armónica pilar (I – IV – V) en Re mayor. Tres acordes mayores que delimitan con absoluta claridad la tonalidad.',
    },
    {
        'id': 'prog-am-dm-em',
        'titulo': 'Secuencia menor natural (La menor)',
        'acordes': ['Am', 'Dm', 'Em'],
        'explicacion': 'Secuencia i – iv – v en La menor. Al encadenar tres acordes menores, genera una atmósfera uniforme, cálida y reflexiva.',
    },

    # --- 4 Acordes ---
    {
        'id': 'prog-g-em-c-d',
        'titulo': 'Círculo armónico en Sol mayor',
        'acordes': ['G', 'Em', 'C', 'D'],
        'explicacion': 'Círculo clásico I – vi – IV – V. El paso por Mi menor agrega un matiz emotivo antes de avanzar por el impulso de Do y Re.',
    },
    {
        'id': 'prog-em-c-g-d',
        'titulo': 'Progresión menor moderna',
        'acordes': ['Em', 'C', 'G', 'D'],
        'explicacion': 'Secuencia vi – IV – I – V en Sol / Mi menor. Su dinamismo crea una rueda sonora que fluye de manera natural sin sentirse estancada.',
    },
    {
        'id': 'prog-c-am-dm-g',
        'titulo': 'Círculo armónico en Do mayor',
        'acordes': ['C', 'Am', 'Dm', 'G'],
        'explicacion': 'Secuencia I – vi – ii – V. Una de las progresiones más equilibradas y elegantes, muy utilizada en la balada y la música popular.',
    },
    {
        'id': 'prog-c-g-am-em',
        'titulo': 'Descenso armónico (Do mayor)',
        'acordes': ['C', 'G', 'Am', 'Em'],
        'explicacion': 'Secuencia I – V – vi – iii. Los acordes se encadenan con suavidad gracias a las notas comunes que comparten en cada transición.',
    },
]


def obtener_catalogo_progresiones() -> List[EjercicioProgresion]:
    """Genera el catálogo de progresiones con diagramas SVG y secuencias de audio."""
    catalogo_acordes_dict = {a.codigo: a for a in obtener_catalogo_acordes()}
    catalogo: List[EjercicioProgresion] = []

    for item in PROGRESIONES_DATA:
        acordes_codigos = item['acordes']
        diagramas: List[str] = []
        audio_chords: List[List[int]] = []

        for c_cod in acordes_codigos:
            acorde_info = catalogo_acordes_dict.get(c_cod)
            if acorde_info:
                diagramas.append(acorde_info.svg_referencia)
                audio_chords.append(acorde_info.midi_referencia)

        catalogo.append(EjercicioProgresion(
            id=item['id'],
            titulo=item['titulo'],
            acordes=acordes_codigos,
            acordes_str=" → ".join(acordes_codigos),
            explicacion=item['explicacion'],
            diagramas_svg=diagramas,
            audio_chords=audio_chords,
        ))

    return catalogo

