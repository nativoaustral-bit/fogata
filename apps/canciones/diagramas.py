"""
Módulo de Diagramas de Acordes para Guitarra (Fase 4).
Generación de diagramas vectoriales en SVG nativo a partir de digitaciones
validadas musicalmente en afinación estándar EADGBE.
Cero dependencias externas. Cero CDNs.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Set, Dict
from django.utils.html import escape
from django.utils.safestring import mark_safe

from apps.canciones.parser import (
    pitch_class_a_nota,
    obtener_pitch_class,
    validar_token_acorde
)


# =============================================================================
# 1. Afinación Estándar de Referencia y Estructura de Datos
# =============================================================================

# Clases de altura (pitch class 0..11) de las 6 cuerdas al aire en afinación estándar:
# 6ª = Mi (4), 5ª = La (9), 4ª = Re (2), 3ª = Sol (7), 2ª = Si (11), 1ª = Mi (4)
CUERDAS_AFINACION_ESTANDAR = [4, 9, 2, 7, 11, 4]


@dataclass
class DigitacionAcorde:
    """
    Representa la posición de digitación recomendada para un acorde en guitarra.
    Cuerdas ordenadas de 6ª cuerda (Mi grave) a 1ª cuerda (Mi agudo).
    """
    # trastes: 6 enteros para [6ª, 5ª, 4ª, 3ª, 2ª, 1ª]
    # -1 = cuerda no tocada / muteada ('X')
    #  0 = cuerda tocada al aire ('O')
    #  1..N = traste presionado
    trastes: List[int]

    # dedos: opcional [6ª, 5ª, 4ª, 3ª, 2ª, 1ª]
    # 0 = sin dedo / al aire / muteada
    # 1=índice, 2=medio, 3=anular, 4=meñique
    dedos: Optional[List[int]] = None

    # base_fret: traste de inicio del diagrama (1 si incluye cejuela abierta)
    base_fret: int = 1

    # cejilla: opcional (traste, cuerda_desde, cuerda_hasta)
    # ej. para F: (1, 6, 1) -> traste 1 de 6ª a 1ª cuerda
    # ej. para Bm: (2, 5, 1) -> traste 2 de 5ª a 1ª cuerda
    cejilla: Optional[Tuple[int, int, int]] = None


# =============================================================================
# 2. Motor de Validación Musical de Digitaciones (Criterios 1, 2 y 3)
# =============================================================================

def calcular_clases_altura(trastes: List[int]) -> Tuple[Set[int], Optional[int]]:
    """
    Calcula el conjunto de clases de altura (0..11) que efectivamente suenan
    en la guitarra a partir de los trastes, y la nota más grave que suena (bajo).
    """
    if len(trastes) != 6:
        raise ValueError("Se requieren exactamente 6 valores de trastes.")

    pitches: Set[int] = set()
    bajo_pitch: Optional[int] = None

    for cuerda_idx, traste in enumerate(trastes):
        if traste >= 0:
            p = (CUERDAS_AFINACION_ESTANDAR[cuerda_idx] + traste) % 12
            pitches.add(p)
            if bajo_pitch is None:
                # La primera cuerda que suena (de 6ª a 1ª) define el bajo efectivo
                bajo_pitch = p

    return pitches, bajo_pitch


def validar_digitacion_musical(
    pitch_raiz: int,
    modificador: str,
    digitacion: DigitacionAcorde,
    bajo_pitch: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Comprueba que la digitación produzca las notas armónicas correspondientes
    al acorde indicado y que, para slash chords, el bajo más grave sea el requerido.
    """
    pitches, bajo_real = calcular_clases_altura(digitacion.trastes)

    # 1. Debe contener la raíz
    if pitch_raiz not in pitches:
        return False, f"Falta la nota fundamental ({pitch_raiz}) en las notas que suenan: {pitches}"

    # Intervalos clave
    segunda = (pitch_raiz + 2) % 12
    tercera_menor = (pitch_raiz + 3) % 12
    tercera_mayor = (pitch_raiz + 4) % 12
    cuarta_justa = (pitch_raiz + 5) % 12
    quinta_justa = (pitch_raiz + 7) % 12
    septima_menor = (pitch_raiz + 10) % 12
    septima_mayor = (pitch_raiz + 11) % 12

    mod_norm = normalizar_modificador(modificador)

    # 2. Acordes Mayores
    if mod_norm == '':
        if tercera_mayor not in pitches:
            return False, f"Acorde mayor requiere tercera mayor ({tercera_mayor})."
        if quinta_justa not in pitches:
            return False, f"Acorde mayor requiere quinta justa ({quinta_justa})."

    # 3. Acordes Menores
    elif mod_norm == 'm':
        if tercera_menor not in pitches:
            return False, f"Acorde menor requiere tercera menor ({tercera_menor})."
        if tercera_mayor in pitches:
            return False, "Acorde menor no debe contener tercera mayor."
        if quinta_justa not in pitches:
            return False, f"Acorde menor requiere quinta justa ({quinta_justa})."

    # 4. Sus2 (Criterio 2: sin tercera)
    elif mod_norm == 'sus2':
        if segunda not in pitches:
            return False, f"sus2 requiere segunda mayor ({segunda})."
        if tercera_mayor in pitches or tercera_menor in pitches:
            return False, "sus2 no debe contener tercera mayor ni menor."
        if quinta_justa not in pitches:
            return False, f"sus2 requiere quinta justa ({quinta_justa})."

    # 5. Sus4 (Criterio 1 y 2: sin tercera)
    elif mod_norm in ('sus4', 'sus'):
        if cuarta_justa not in pitches:
            return False, f"sus4 requiere cuarta justa ({cuarta_justa})."
        if tercera_mayor in pitches or tercera_menor in pitches:
            return False, "sus4 no debe contener tercera mayor ni menor."
        if quinta_justa not in pitches:
            return False, f"sus4 requiere quinta justa ({quinta_justa})."

    # 6. Dominante 7
    elif mod_norm == '7':
        if tercera_mayor not in pitches:
            return False, f"Séptima dominante requiere tercera mayor ({tercera_mayor})."
        if septima_menor not in pitches:
            return False, f"Séptima dominante requiere séptima menor ({septima_menor})."

    # 7. maj7
    elif mod_norm == 'maj7':
        if tercera_mayor not in pitches:
            return False, f"maj7 requiere tercera mayor ({tercera_mayor})."
        if septima_mayor not in pitches:
            return False, f"maj7 requiere séptima mayor ({septima_mayor})."

    # 8. m7
    elif mod_norm == 'm7':
        if tercera_menor not in pitches:
            return False, f"m7 requiere tercera menor ({tercera_menor})."
        if tercera_mayor in pitches:
            return False, "m7 no debe contener tercera mayor."
        if septima_menor not in pitches:
            return False, f"m7 requiere séptima menor ({septima_menor})."

    # 9. add9
    elif mod_norm in ('add9', 'add2'):
        if tercera_mayor not in pitches:
            return False, f"add9 requiere tercera mayor ({tercera_mayor})."
        if segunda not in pitches:
            return False, f"add9 requiere la novena/segunda ({segunda})."

    # 10. Slash Chords (Criterio 3: la nota más grave que suena debe ser el bajo)
    if bajo_pitch is not None:
        if bajo_real != bajo_pitch:
            return False, f"Slash chord exige bajo {bajo_pitch}, pero suena {bajo_real} en la cuerda más grave."

    return True, "Validación musical exitosa."


def normalizar_modificador(mod: str) -> str:
    """Normaliza variantes sinónimas de modificadores musicales."""
    m = (mod or '').strip()
    if m in ('M', ''):
        return ''
    if m in ('min', 'm', 'minor'):
        return 'm'
    if m in ('M7', 'maj7', 'Δ7', 'Δ'):
        return 'maj7'
    if m in ('min7', 'm7'):
        return 'm7'
    if m in ('sus', 'sus4', '7sus4'):
        return 'sus4'
    if m in ('sus2', '7sus2'):
        return 'sus2'
    if m in ('add', 'add9', 'add2'):
        return 'add9'
    return m


# =============================================================================
# 3. Biblioteca Inicial de Digitaciones Verificadas para Guitarra
# Clave: (pitch_raiz: 0..11, modificador_normalizado: str, bajo_pitch: Optional[int])
# =============================================================================

BIBLIOTECA_ACORDES: Dict[Tuple[int, str, Optional[int]], DigitacionAcorde] = {
    # -------------------------------------------------------------------------
    # MAYORES (Tríadas)
    # -------------------------------------------------------------------------
    # C (0) - x32010
    (0, '', None): DigitacionAcorde(trastes=[-1, 3, 2, 0, 1, 0], dedos=[0, 3, 2, 0, 1, 0]),
    # C# / Db (1) - x46664 (cejilla 4)
    (1, '', None): DigitacionAcorde(trastes=[-1, 4, 6, 6, 6, 4], base_fret=4, cejilla=(4, 5, 1)),
    # D (2) - xx0232
    (2, '', None): DigitacionAcorde(trastes=[-1, -1, 0, 2, 3, 2], dedos=[0, 0, 0, 1, 3, 2]),
    # Eb / D# (3) - xx1343
    (3, '', None): DigitacionAcorde(trastes=[-1, -1, 1, 3, 4, 3], base_fret=1, dedos=[0, 0, 1, 2, 4, 3]),
    # E (4) - 022100
    (4, '', None): DigitacionAcorde(trastes=[0, 2, 2, 1, 0, 0], dedos=[0, 2, 3, 1, 0, 0]),
    # F (5) - 133211 (cejilla 1)
    (5, '', None): DigitacionAcorde(trastes=[1, 3, 3, 2, 1, 1], base_fret=1, cejilla=(1, 6, 1)),
    # F# / Gb (6) - 244322 (cejilla 2)
    (6, '', None): DigitacionAcorde(trastes=[2, 4, 4, 3, 2, 2], base_fret=2, cejilla=(2, 6, 1)),
    # G (7) - 320003
    (7, '', None): DigitacionAcorde(trastes=[3, 2, 0, 0, 0, 3], dedos=[2, 1, 0, 0, 0, 3]),
    # Ab / G# (8) - 466544 (cejilla 4)
    (8, '', None): DigitacionAcorde(trastes=[4, 6, 6, 5, 4, 4], base_fret=4, cejilla=(4, 6, 1)),
    # A (9) - x02220
    (9, '', None): DigitacionAcorde(trastes=[-1, 0, 2, 2, 2, 0], dedos=[0, 0, 1, 2, 3, 0]),
    # Bb / A# (10) - x13331 (cejilla 1)
    (10, '', None): DigitacionAcorde(trastes=[-1, 1, 3, 3, 3, 1], base_fret=1, cejilla=(1, 5, 1)),
    # B (11) - x24442 (cejilla 2)
    (11, '', None): DigitacionAcorde(trastes=[-1, 2, 4, 4, 4, 2], base_fret=2, cejilla=(2, 5, 1)),

    # -------------------------------------------------------------------------
    # MENORES (Tríadas)
    # -------------------------------------------------------------------------
    # Cm (0) - x35543 (cejilla 3)
    (0, 'm', None): DigitacionAcorde(trastes=[-1, 3, 5, 5, 4, 3], base_fret=3, cejilla=(3, 5, 1)),
    # C#m / Dbm (1) - x46654 (cejilla 4)
    (1, 'm', None): DigitacionAcorde(trastes=[-1, 4, 6, 6, 5, 4], base_fret=4, cejilla=(4, 5, 1)),
    # Dm (2) - xx0231
    (2, 'm', None): DigitacionAcorde(trastes=[-1, -1, 0, 2, 3, 1], dedos=[0, 0, 0, 2, 3, 1]),
    # D#m / Ebm (3) - x68876 (cejilla 6)
    (3, 'm', None): DigitacionAcorde(trastes=[-1, 6, 8, 8, 7, 6], base_fret=6, cejilla=(6, 5, 1)),
    # Em (4) - 022000
    (4, 'm', None): DigitacionAcorde(trastes=[0, 2, 2, 0, 0, 0], dedos=[0, 2, 3, 0, 0, 0]),
    # Fm (5) - 133111 (cejilla 1)
    (5, 'm', None): DigitacionAcorde(trastes=[1, 3, 3, 1, 1, 1], base_fret=1, cejilla=(1, 6, 1)),
    # F#m (6) - 244222 (cejilla 2)
    (6, 'm', None): DigitacionAcorde(trastes=[2, 4, 4, 2, 2, 2], base_fret=2, cejilla=(2, 6, 1)),
    # Gm (7) - 355333 (cejilla 3)
    (7, 'm', None): DigitacionAcorde(trastes=[3, 5, 5, 3, 3, 3], base_fret=3, cejilla=(3, 6, 1)),
    # G#m / Abm (8) - 466444 (cejilla 4)
    (8, 'm', None): DigitacionAcorde(trastes=[4, 6, 6, 4, 4, 4], base_fret=4, cejilla=(4, 6, 1)),
    # Am (9) - x02210
    (9, 'm', None): DigitacionAcorde(trastes=[-1, 0, 2, 2, 1, 0], dedos=[0, 0, 2, 3, 1, 0]),
    # Bbm (10) - x13321 (cejilla 1)
    (10, 'm', None): DigitacionAcorde(trastes=[-1, 1, 3, 3, 2, 1], base_fret=1, cejilla=(1, 5, 1)),
    # Bm (11) - x24432 (cejilla 2)
    (11, 'm', None): DigitacionAcorde(trastes=[-1, 2, 4, 4, 3, 2], base_fret=2, cejilla=(2, 5, 1)),

    # -------------------------------------------------------------------------
    # SÉPTIMAS DOMINANTES (7)
    # -------------------------------------------------------------------------
    # C7 (0) - x32310
    (0, '7', None): DigitacionAcorde(trastes=[-1, 3, 2, 3, 1, 0], dedos=[0, 3, 2, 4, 1, 0]),
    # D7 (2) - xx0212
    (2, '7', None): DigitacionAcorde(trastes=[-1, -1, 0, 2, 1, 2], dedos=[0, 0, 0, 2, 1, 3]),
    # E7 (4) - 020100
    (4, '7', None): DigitacionAcorde(trastes=[0, 2, 0, 1, 0, 0], dedos=[0, 2, 0, 1, 0, 0]),
    # F7 (5) - 131211 (cejilla 1)
    (5, '7', None): DigitacionAcorde(trastes=[1, 3, 1, 2, 1, 1], base_fret=1, cejilla=(1, 6, 1)),
    # F#7 (6) - 242322 (cejilla 2)
    (6, '7', None): DigitacionAcorde(trastes=[2, 4, 2, 3, 2, 2], base_fret=2, cejilla=(2, 6, 1)),
    # G7 (7) - 320001
    (7, '7', None): DigitacionAcorde(trastes=[3, 2, 0, 0, 0, 1], dedos=[3, 2, 0, 0, 0, 1]),
    # A7 (9) - x02020
    (9, '7', None): DigitacionAcorde(trastes=[-1, 0, 2, 0, 2, 0], dedos=[0, 0, 2, 0, 3, 0]),
    # Bb7 (10) - x13131 (cejilla 1)
    (10, '7', None): DigitacionAcorde(trastes=[-1, 1, 3, 1, 3, 1], base_fret=1, cejilla=(1, 5, 1)),
    # B7 (11) - x21202
    (11, '7', None): DigitacionAcorde(trastes=[-1, 2, 1, 2, 0, 2], dedos=[0, 2, 1, 3, 0, 4]),

    # -------------------------------------------------------------------------
    # SÉPTIMAS MAYORES (maj7)
    # -------------------------------------------------------------------------
    # Cmaj7 (0) - x32000
    (0, 'maj7', None): DigitacionAcorde(trastes=[-1, 3, 2, 0, 0, 0], dedos=[0, 3, 2, 0, 0, 0]),
    # Dmaj7 (2) - xx0222
    (2, 'maj7', None): DigitacionAcorde(trastes=[-1, -1, 0, 2, 2, 2], dedos=[0, 0, 0, 1, 2, 3]),
    # Emaj7 (4) - 021100
    (4, 'maj7', None): DigitacionAcorde(trastes=[0, 2, 1, 1, 0, 0], dedos=[0, 3, 1, 2, 0, 0]),
    # Fmaj7 (5) - xx3210
    (5, 'maj7', None): DigitacionAcorde(trastes=[-1, -1, 3, 2, 1, 0], dedos=[0, 0, 3, 2, 1, 0]),
    # Gmaj7 (7) - 320002
    (7, 'maj7', None): DigitacionAcorde(trastes=[3, 2, 0, 0, 0, 2], dedos=[2, 1, 0, 0, 0, 3]),
    # Amaj7 (9) - x02120
    (9, 'maj7', None): DigitacionAcorde(trastes=[-1, 0, 2, 1, 2, 0], dedos=[0, 0, 2, 1, 3, 0]),
    # Bbmaj7 (10) - x13231 (cejilla 1)
    (10, 'maj7', None): DigitacionAcorde(trastes=[-1, 1, 3, 2, 3, 1], base_fret=1, cejilla=(1, 5, 1)),

    # -------------------------------------------------------------------------
    # MENORES SÉPTIMA (m7)
    # -------------------------------------------------------------------------
    # Cm7 (0) - x35343 (cejilla 3)
    (0, 'm7', None): DigitacionAcorde(trastes=[-1, 3, 5, 3, 4, 3], base_fret=3, cejilla=(3, 5, 1)),
    # C#m7 (1) - x46454 (cejilla 4)
    (1, 'm7', None): DigitacionAcorde(trastes=[-1, 4, 6, 4, 5, 4], base_fret=4, cejilla=(4, 5, 1)),
    # Dm7 (2) - xx0211
    (2, 'm7', None): DigitacionAcorde(trastes=[-1, -1, 0, 2, 1, 1], dedos=[0, 0, 0, 2, 1, 1]),
    # Em7 (4) - 020000
    (4, 'm7', None): DigitacionAcorde(trastes=[0, 2, 0, 0, 0, 0], dedos=[0, 1, 0, 0, 0, 0]),
    # F#m7 (6) - 242222 (cejilla 2)
    (6, 'm7', None): DigitacionAcorde(trastes=[2, 4, 2, 2, 2, 2], base_fret=2, cejilla=(2, 6, 1)),
    # Gm7 (7) - 353333 (cejilla 3)
    (7, 'm7', None): DigitacionAcorde(trastes=[3, 5, 3, 3, 3, 3], base_fret=3, cejilla=(3, 6, 1)),
    # Am7 (9) - x02010
    (9, 'm7', None): DigitacionAcorde(trastes=[-1, 0, 2, 0, 1, 0], dedos=[0, 0, 2, 0, 1, 0]),
    # Bm7 (11) - x20202
    (11, 'm7', None): DigitacionAcorde(trastes=[-1, 2, 0, 2, 0, 2], dedos=[0, 2, 0, 3, 0, 4]),

    # -------------------------------------------------------------------------
    # SUSPENDIDOS (sus2, sus4)
    # -------------------------------------------------------------------------
    # Csus2 (0) - x3001-1 -> usamos x30033: C(3), D(0), G(0), D(3), G(3)
    (0, 'sus2', None): DigitacionAcorde(trastes=[-1, 3, 0, 0, 3, 3], dedos=[0, 2, 0, 0, 3, 4]),
    # Dsus2 (2) - xx0230
    (2, 'sus2', None): DigitacionAcorde(trastes=[-1, -1, 0, 2, 3, 0], dedos=[0, 0, 0, 1, 2, 0]),
    # Asus2 (9) - x02200
    (9, 'sus2', None): DigitacionAcorde(trastes=[-1, 0, 2, 2, 0, 0], dedos=[0, 0, 2, 3, 0, 0]),

    # Csus4 (0) - x33011 (Criterio 1: sin la tercera mayor E en la 1ª cuerda)
    (0, 'sus4', None): DigitacionAcorde(trastes=[-1, 3, 3, 0, 1, 1], dedos=[0, 3, 4, 0, 1, 1]),
    # Dsus4 (2) - xx0233
    (2, 'sus4', None): DigitacionAcorde(trastes=[-1, -1, 0, 2, 3, 3], dedos=[0, 0, 0, 1, 2, 3]),
    # Esus4 (4) - 022200
    (4, 'sus4', None): DigitacionAcorde(trastes=[0, 2, 2, 2, 0, 0], dedos=[0, 2, 3, 4, 0, 0]),
    # Gsus4 (7) - 330013 -> G(3), C(3), G(0), D(0), C(1), G(3)
    (7, 'sus4', None): DigitacionAcorde(trastes=[3, 3, 0, 0, 1, 3], dedos=[3, 4, 0, 0, 1, 2]),
    # Asus4 (9) - x02230
    (9, 'sus4', None): DigitacionAcorde(trastes=[-1, 0, 2, 2, 3, 0], dedos=[0, 0, 1, 2, 3, 0]),

    # -------------------------------------------------------------------------
    # ADD (add9)
    # -------------------------------------------------------------------------
    # Cadd9 (0) - x32033 (C, E, G, D, G)
    (0, 'add9', None): DigitacionAcorde(trastes=[-1, 3, 2, 0, 3, 3], dedos=[0, 2, 1, 0, 3, 4]),
    # Gadd9 (7) - 320203 (G, B, D, A, B, G)
    (7, 'add9', None): DigitacionAcorde(trastes=[3, 2, 0, 2, 0, 3], dedos=[2, 1, 0, 3, 0, 4]),
    # Aadd9 (9) - x02420 (A, E, B, C#, E)
    (9, 'add9', None): DigitacionAcorde(trastes=[-1, 0, 2, 4, 2, 0], dedos=[0, 0, 1, 3, 2, 0]),

    # -------------------------------------------------------------------------
    # SLASH CHORDS FRECUENTES (Criterio 3: bajo real verificado)
    # -------------------------------------------------------------------------
    # G/B: 5ª cuerda en traste 2 es B (11). 6ª cuerda muteada (-1).
    (7, '', 11): DigitacionAcorde(trastes=[-1, 2, 0, 0, 3, 3], dedos=[0, 1, 0, 0, 3, 4]),
    # D/F#: 6ª cuerda en traste 2 es F# (6).
    (2, '', 6): DigitacionAcorde(trastes=[2, 0, 0, 2, 3, 2], dedos=[1, 0, 0, 2, 4, 3]),
    # C/G: 6ª cuerda en traste 3 es G (7).
    (0, '', 7): DigitacionAcorde(trastes=[3, 3, 2, 0, 1, 0], dedos=[3, 4, 2, 0, 1, 0]),
    # Am/G: 6ª cuerda en traste 3 es G (7).
    (9, 'm', 7): DigitacionAcorde(trastes=[3, 0, 2, 2, 1, 0], dedos=[3, 0, 2, 4, 1, 0]),
    # D/A: 5ª cuerda al aire es A (9). 6ª cuerda muteada (-1).
    (2, '', 9): DigitacionAcorde(trastes=[-1, 0, 0, 2, 3, 2], dedos=[0, 0, 0, 1, 3, 2]),
}


# =============================================================================
# 4. Búsqueda y Resolución de Acordes
# =============================================================================

def buscar_digitacion(
    pitch_raiz: int,
    modificador: str = '',
    bajo_pitch: Optional[int] = None
) -> Optional[DigitacionAcorde]:
    """
    Busca una digitación física para el acorde normalizado.
    Para slash chords (Criterio 3 y 19): SOLO retorna si existe digitación específica.
    Nunca sustituye silenciosamente un acorde slash por su versión sin bajo.
    """
    if pitch_raiz < 0 or pitch_raiz > 11:
        return None

    mod_norm = normalizar_modificador(modificador)

    if bajo_pitch is not None:
        if bajo_pitch < 0 or bajo_pitch > 11:
            return None
        # Búsqueda estricta de slash chord
        return BIBLIOTECA_ACORDES.get((pitch_raiz, mod_norm, bajo_pitch))

    return BIBLIOTECA_ACORDES.get((pitch_raiz, mod_norm, None))


# =============================================================================
# 5. Generador Seguro de SVG Vectorial Puro (Criterios 12, 13 y 14)
# =============================================================================

def generar_svg_acorde(
    digitacion: DigitacionAcorde,
    nombre_mostrar: str,
    ancho: int = 180,
    alto: int = 220
) -> str:
    """
    Genera un diagrama de guitarra vectorial puro en SVG.
    - Utiliza <circle> para cuerdas abiertas y pares de <line> para cuerdas muteadas (Criterio 12).
    - Incluye role="img" y <title> accesible sanitizado (Criterio 13).
    - Diseñado para tema oscuro de atril (#1c1c1c / #ff9800).
    """
    # Geometría del diapasón
    # ViewBox: 0 0 160 200
    vb_w, vb_h = 160, 200
    top_y = 52       # Y superior de la cejuela/primer traste
    fret_height = 28 # Altura de cada traste
    num_frets = 4    # Número de trastes visualizados
    bottom_y = top_y + (num_frets * fret_height)

    margin_x = 30
    string_spacing = 20 # 6 cuerdas -> ancho rejilla = 5 * 20 = 100px (x de 30 a 130)

    nombre_escapado = escape(nombre_mostrar)
    title_accesible = escape(f"Diagrama de acorde {nombre_mostrar}")

    partes: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vb_w} {vb_h}" '
        f'width="{ancho}" height="{alto}" role="img" class="diagrama-acorde-svg" '
        f'aria-label="{title_accesible}">',
        f'<title>{title_accesible}</title>',
        # Nombre del acorde en la cabecera
        f'<text x="{vb_w // 2}" y="32" text-anchor="middle" fill="#ff9800" '
        f'font-family="monospace, monospace" font-size="22" font-weight="700">{nombre_escapado}</text>'
    ]

    base_fret = digitacion.base_fret

    # Indicador de Traste Base si es mayor a 1 (ej: "2fr", "4fr")
    if base_fret > 1:
        fret_label = f"{base_fret}fr"
        partes.append(
            f'<text x="{margin_x - 10}" y="{top_y + (fret_height // 2) + 5}" '
            f'text-anchor="end" fill="#ffb74d" font-family="sans-serif" font-size="12" '
            f'font-weight="bold">{fret_label}</text>'
        )

    # Marcadores Superiores (Cuerdas Abiertas y Muteadas usando primitivas SVG, Criterio 12)
    # y = top_y - 12
    marker_y = top_y - 12
    for cuerda_idx, traste in enumerate(digitacion.trastes):
        x = margin_x + (cuerda_idx * string_spacing)

        if traste == -1:
            # Cuerda anulada: 2 líneas cruzadas en X
            d = 4.5
            partes.append(
                f'<line x1="{x - d}" y1="{marker_y - d}" x2="{x + d}" y2="{marker_y + d}" '
                f'stroke="#888888" stroke-width="2" stroke-linecap="round" />'
            )
            partes.append(
                f'<line x1="{x - d}" y1="{marker_y + d}" x2="{x + d}" y2="{marker_y - d}" '
                f'stroke="#888888" stroke-width="2" stroke-linecap="round" />'
            )
        elif traste == 0:
            # Cuerda abierta: círculo sin relleno
            partes.append(
                f'<circle cx="{x}" cy="{marker_y}" r="4.5" fill="none" '
                f'stroke="#cccccc" stroke-width="1.8" />'
            )

    # Líneas de Trastes (Horizontales)
    # Cejuela superior (línea gruesa si base_fret == 1)
    if base_fret == 1:
        partes.append(
            f'<line x1="{margin_x - 1}" y1="{top_y}" x2="{margin_x + (5 * string_spacing) + 1}" '
            f'y2="{top_y}" stroke="#e0e0e0" stroke-width="4.5" stroke-linecap="square" />'
        )
    else:
        partes.append(
            f'<line x1="{margin_x}" y1="{top_y}" x2="{margin_x + (5 * string_spacing)}" '
            f'y2="{top_y}" stroke="#666666" stroke-width="1.8" />'
        )

    for f_idx in range(1, num_frets + 1):
        fy = top_y + (f_idx * fret_height)
        partes.append(
            f'<line x1="{margin_x}" y1="{fy}" x2="{margin_x + (5 * string_spacing)}" '
            f'y2="{fy}" stroke="#444444" stroke-width="1.2" />'
        )

    # Líneas de Cuerdas (Verticales: 6ª cuerda a la izquierda, 1ª cuerda a la derecha)
    for c_idx in range(6):
        cx = margin_x + (c_idx * string_spacing)
        # 6ª y 5ª ligeramente más gruesas que la 1ª
        sw = 1.6 if c_idx < 2 else (1.3 if c_idx < 4 else 1.0)
        partes.append(
            f'<line x1="{cx}" y1="{top_y}" x2="{cx}" y2="{bottom_y}" '
            f'stroke="#555555" stroke-width="{sw}" />'
        )

    # Cejilla (Barre)
    if digitacion.cejilla:
        c_traste, c_desde, c_hasta = digitacion.cejilla
        rel_traste = c_traste - base_fret + 1
        if 1 <= rel_traste <= num_frets:
            barre_y = top_y + ((rel_traste - 1) * fret_height) + (fret_height // 2)
            cuerda_desde_idx = 6 - c_desde
            cuerda_hasta_idx = 6 - c_hasta
            bx1 = margin_x + (cuerda_desde_idx * string_spacing)
            bx2 = margin_x + (cuerda_hasta_idx * string_spacing)
            x_min = min(bx1, bx2) - 4
            barre_w = abs(bx2 - bx1) + 8
            partes.append(
                f'<rect x="{x_min}" y="{barre_y - 5.5}" width="{barre_w}" height="11" '
                f'rx="5.5" ry="5.5" fill="#ff9800" opacity="0.9" />'
            )

    # Puntos de Digitación (Círculos)
    for cuerda_idx, traste in enumerate(digitacion.trastes):
        if traste > 0:
            rel_fret = traste - base_fret + 1
            if 1 <= rel_fret <= num_frets:
                dot_x = margin_x + (cuerda_idx * string_spacing)
                dot_y = top_y + ((rel_fret - 1) * fret_height) + (fret_height // 2)
                partes.append(
                    f'<circle cx="{dot_x}" cy="{dot_y}" r="6.5" fill="#ffffff" '
                    f'stroke="#ff9800" stroke-width="2" />'
                )

                # Número de dedo si está disponible
                if digitacion.dedos and digitacion.dedos[cuerda_idx] > 0:
                    dedo_num = digitacion.dedos[cuerda_idx]
                    partes.append(
                        f'<text x="{dot_x}" y="{dot_y + 3.8}" text-anchor="middle" '
                        f'fill="#000000" font-family="sans-serif" font-size="10" '
                        f'font-weight="bold">{dedo_num}</text>'
                    )

    partes.append('</svg>')
    return mark_safe("".join(partes))


# =============================================================================
# 6. Servicio Integral de Obtención de Diagramas (Criterios 5, 6, 7, 19)
# =============================================================================

def es_afinacion_estandar(afinacion: Optional[str]) -> bool:
    """Verifica si la afinación corresponde a la estándar EADGBE."""
    if not afinacion or not afinacion.strip():
        return True
    a_limpia = afinacion.strip().lower()
    return any(p in a_limpia for p in ['estándar', 'estandar', 'standard', 'eadgbe'])


def obtener_info_diagrama(
    pitch_raiz: int,
    modificador: str = '',
    bajo_pitch: Optional[int] = None,
    notacion: str = 'american',
    usar_bemoles: bool = False,
    afinacion: Optional[str] = None
) -> Dict[str, object]:
    """
    Resuelve el diagrama del acorde solicitado de forma segura.
    Genera el nombre musicalmente coherente desde el servidor (Criterio 7).
    Si no hay posición, retorna mensaje exacto (Criterio 19).
    Si la afinación no es estándar, incluye advertencia discreta (Criterio 5).
    """
    mod_norm = normalizar_modificador(modificador)

    # Generar el nombre formal en servidor (Criterio 7)
    nombre_raiz = pitch_class_a_nota(pitch_raiz, usar_bemoles=usar_bemoles, notacion=notacion)
    nombre_bajo = ''
    if bajo_pitch is not None:
        nb = pitch_class_a_nota(bajo_pitch, usar_bemoles=usar_bemoles, notacion=notacion)
        nombre_bajo = f"/{nb}"

    nombre_completo = f"{nombre_raiz}{mod_norm}{nombre_bajo}"

    digitacion = buscar_digitacion(pitch_raiz, mod_norm, bajo_pitch)

    es_estandar = es_afinacion_estandar(afinacion)
    advertencia_afinacion = ""
    if not es_estandar:
        advertencia_afinacion = "Diagrama basado en afinación estándar EADGBE."

    if not digitacion:
        return {
            'disponible': False,
            'nombre': nombre_completo,
            'svg': None,
            'mensaje': "Diagrama aún no disponible para este acorde.",
            'advertencia_afinacion': advertencia_afinacion
        }

    svg = generar_svg_acorde(digitacion, nombre_mostrar=nombre_completo)

    return {
        'disponible': True,
        'nombre': nombre_completo,
        'svg': svg,
        'mensaje': "",
        'advertencia_afinacion': advertencia_afinacion
    }
