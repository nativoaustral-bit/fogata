from django import template
from apps.canciones.parser import render_cancion_html, extraer_solo_letra

register = template.Library()


@register.filter(name='formatear_contenido_musical')
def formatear_contenido_musical(contenido):
    """
    Template filter para transformar el contenido crudo de la canción
    en HTML seguro con acordes destacados y preservación espacial estricta.
    """
    return render_cancion_html(contenido)


@register.filter(name='solo_letra')
def solo_letra(contenido):
    """
    Template filter para extraer solo letra de la canción (Modo Invitado).
    """
    return extraer_solo_letra(contenido)
