"""
Servicios y helpers de procesamiento de contenido musical para Canciones.

NOTA DE DISEÑO (Criterio 6):
El contenido original ingresado por el usuario se preserva siempre de forma íntegra.
`obtener_solo_letra()` es una capacidad futura y no debe realizar eliminación
agresiva de acordes que pudiera mutilar versos legítimos. Cuando se desarrolle,
debe ser estrictamente tolerante a errores y jamás modificar la fuente de datos original.
"""


def obtener_solo_letra(contenido):
    """
    Helper preparado para el futuro Modo Invitado.
    Por ahora, devuelve el texto de forma segura y tolerante sin aplicar
    filtros destructivos sobre el contenido original.
    """
    if not contenido:
        return ""
    # En Fase 0 devolvemos el texto íntegro para evitar destrucción o cortes accidentales.
    return str(contenido)
