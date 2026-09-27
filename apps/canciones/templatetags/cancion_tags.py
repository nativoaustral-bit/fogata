from django import template
from apps.canciones.parser import (
    render_cancion_html,
    extraer_solo_letra,
    parse_cancion,
    extraer_acordes_unicos,
    determinar_preferencia_alteraciones,
    transponer_tonalidad,
)

register = template.Library()


@register.filter(name='formatear_contenido_musical')
def formatear_contenido_musical(contenido):
    """
    Template filter para transformar el contenido crudo de la canción
    en HTML seguro con acordes destacados y preservación espacial estricta.
    Incluye metadata por defecto para permitir interactividad en el cliente.
    """
    return render_cancion_html(contenido, incluir_metadata=True)


@register.simple_tag
def render_cancion(
    cancion,
    semitonos=0,
    notacion='original',
    incluir_metadata=True,
    modo_edicion=False,
    cancion_id=None,
    fogata_id=None,
    pos=None
):
    """
    Renderiza la canción con soporte completo de transposición, selección
    de notación, metadata para JS, modo edición rápida y enlaces a diagramas.
    """
    contenido = getattr(cancion, 'contenido', cancion)
    tonalidad = getattr(cancion, 'tonalidad', None)
    cid = cancion_id if cancion_id is not None else getattr(cancion, 'pk', None)
    return render_cancion_html(
        contenido=contenido,
        semitonos=semitonos,
        notacion=notacion,
        incluir_metadata=incluir_metadata,
        modo_edicion=modo_edicion,
        tonalidad=tonalidad,
        cancion_id=cid,
        fogata_id=fogata_id,
        pos=pos
    )


@register.simple_tag
def acordes_de_cancion(cancion, semitonos=0, notacion='original'):
    """
    Retorna la lista ordenada de acordes únicos detectados en la canción,
    reflejando la transposición y notación visual activa (Criterio 16).
    """
    contenido = getattr(cancion, 'contenido', cancion)
    tonalidad = getattr(cancion, 'tonalidad', None)
    semitonos_val = max(-6, min(6, semitonos))
    usar_bemoles = determinar_preferencia_alteraciones(contenido, tonalidad, semitonos_val)
    lineas = parse_cancion(contenido)
    return extraer_acordes_unicos(
        lineas,
        semitonos=semitonos_val,
        usar_bemoles=usar_bemoles,
        notacion=notacion
    )


@register.simple_tag
def texto_tonalidad(cancion, semitonos=0, notacion='original'):
    """
    Genera el texto descriptivo de la tonalidad según transposición (Criterio 17).
    Ejemplo con tonalidad:
      semitonos=0 -> "Tono: G"
      semitonos=2 -> "Original: G (+2: A)"
    Ejemplo sin tonalidad:
      semitonos=0 -> "Original"
      semitonos=2 -> "+2"
    """
    tonalidad = getattr(cancion, 'tonalidad', None)
    semitonos_val = max(-6, min(6, semitonos))
    signo = f"+{semitonos_val}" if semitonos_val > 0 else f"{semitonos_val}"

    if tonalidad and tonalidad.strip():
        t_orig = tonalidad.strip()
        contenido = getattr(cancion, 'contenido', '')
        usar_bemoles = determinar_preferencia_alteraciones(contenido, t_orig, semitonos_val)
        t_actual = transponer_tonalidad(t_orig, semitonos_val, usar_bemoles=usar_bemoles, notacion=notacion)
        if semitonos_val == 0:
            if notacion != 'original' and t_actual and t_actual != t_orig:
                return f"Tono: {t_actual}"
            return f"Tono: {t_orig}"
        return f"Original: {t_orig} ({signo}: {t_actual})"
    else:
        if semitonos_val == 0:
            return "Original"
        return signo


@register.filter(name='solo_letra')
def solo_letra(contenido):
    """
    Template filter para extraer solo letra de la canción (Modo Invitado).
    """
    return extraer_solo_letra(contenido)

