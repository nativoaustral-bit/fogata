from datetime import datetime
from django.conf import settings
from django.utils import timezone


def obtener_analytics_start_date():
    configured_date = getattr(settings, 'FOGATA_ANALYTICS_START_DATE', '2026-09-28')
    tz = timezone.get_current_timezone()
    dt = datetime.strptime(configured_date, '%Y-%m-%d')
    return timezone.make_aware(dt, tz)


def obtener_analytics_start_date_str():
    return obtener_analytics_start_date().strftime('%d/%m/%Y')


ANALYTICS_START_DATE_STR = "28/09/2026"


# Acciones reales de producto que demuestran uso activo y adopción
# Excluyen 'login', 'registro' y aperturas de invitados
ACCIONES_USO_REAL = {
    'crear_cancion',
    'editar_cancion',
    'tocar_cancion',
    'crear_fogata',
    'editar_fogata',
    'tocar_fogata',
    'crear_sesion_compartida',
}

# Whitelist estricta de metadatos permitidos por tipo de evento
METADATA_WHITELIST = {
    'crear_cancion': set(),
    'editar_cancion': set(),
    'tocar_cancion': {'origen'},
    'crear_fogata': set(),
    'editar_fogata': {'accion_detalle'},  # ej: agregar, quitar, mover
    'tocar_fogata': {'total_canciones'},
    'crear_sesion_compartida': {'duracion_horas'},
    'abrir_sesion_compartida': set(),
    'login': set(),
    'registro': set(),
    'ver_pro': {'origen'},
    'alcanzar_limite_canciones': {'total_actual'},
    'alcanzar_limite_fogatas': {'total_actual'},
}

# Palabras prohibidas que jamás deben ingresar a metadata
FORBIDDEN_METADATA_KEYS = {
    'titulo', 'artista', 'letra', 'acordes', 'contenido',
    'notas', 'token', 'email', 'password', 'clave', 'hash',
    'ip', 'user_agent', 'fingerprint', 'tonalidad', 'capo',
    'afinacion', 'nota_sesion'
}
