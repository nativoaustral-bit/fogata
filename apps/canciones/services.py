"""
Servicios y helpers de procesamiento de contenido musical para Canciones.

NOTA DE DISEÑO (Criterio 6):
El contenido original ingresado por el usuario se preserva siempre de forma íntegra.
`obtener_solo_letra()` es una capacidad futura y no debe realizar eliminación
agresiva de acordes que pudiera mutilar versos legítimos. Cuando se desarrolle,
debe ser estrictamente tolerante a errores y jamás modificar la fuente de datos original.
"""


from apps.canciones.parser import extraer_solo_letra


def obtener_solo_letra(contenido):
    """
    Helper para el Modo Invitado.
    Utiliza el parser musical para suprimir líneas de acordes y tablatura,
    y limpiar acordes embebidos [G], preservando las estrofas y versos intactos
    sin alterar el contenido original en la base de datos.
    """
    if not contenido:
        return ""
    return extraer_solo_letra(contenido)
