import logging
import json
from django.db import transaction
from django.utils import timezone
from ..models import EventoUso, AuditoriaAdmin
from ..constants import METADATA_WHITELIST, FORBIDDEN_METADATA_KEYS

logger = logging.getLogger(__name__)

TIPOS_VALIDOS = {t[0] for t in EventoUso.TIPOS_EVENTO}


def sanitizar_metadata(tipo_evento, metadata_raw):
    """
    Sanitiza y filtra estrictamente la metadata según whitelist del evento.
    Rechaza cualquier clave prohibida (letras, acordes, emails, tokens, etc.)
    y asegura que el contenido sea ligero y seguro.
    """
    if not isinstance(metadata_raw, dict):
        return {}

    permitidas = METADATA_WHITELIST.get(tipo_evento, set())
    metadata_limpia = {}

    for k, v in metadata_raw.items():
        k_str = str(k).strip().lower()
        if k_str in FORBIDDEN_METADATA_KEYS:
            logger.warning("Intento de almacenar metadato prohibido '%s' en evento '%s'. Omitido.", k_str, tipo_evento)
            continue
        if k_str in permitidas:
            if isinstance(v, (str, int, float, bool)):
                if isinstance(v, str) and len(v) > 100:
                    v = v[:100]
                metadata_limpia[k_str] = v

    try:
        serialized = json.dumps(metadata_limpia)
        if len(serialized) > 1000:
            return {}
    except (TypeError, ValueError):
        return {}

    return metadata_limpia


def _ejecutar_guardado_evento(usuario_id, tipo_evento, objeto_tipo, objeto_id, metadata_limpia, fecha=None):
    """
    Inserción a nivel de base de datos aislada contra excepciones.
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        usuario = User.objects.filter(pk=usuario_id).first() if usuario_id else None
        EventoUso.objects.create(
            usuario=usuario,
            tipo_evento=tipo_evento,
            objeto_tipo=objeto_tipo or '',
            objeto_id=objeto_id,
            metadata=metadata_limpia,
            fecha=fecha or timezone.now()
        )
    except Exception as e:
        logger.error("Error al persistir EventoUso '%s': %s", tipo_evento, e, exc_info=True)


def registrar_evento(usuario=None, tipo_evento="", objeto_tipo="", objeto_id=None, metadata=None, fecha=None):
    """
    Único punto normal de creación de eventos de comportamiento de producto.
    - Valida que tipo_evento sea conocido.
    - Filtra metadata según whitelist.
    - Si existe una transacción activa en curso, programa la persistencia vía on_commit()
      para garantizar que operaciones con rollback no generen eventos fantasma.
    - Captura cualquier error silenciosamente para no interrumpir la experiencia de usuario.
    """
    try:
        if tipo_evento not in TIPOS_VALIDOS:
            logger.warning("Evento desconocido '%s' descartado por registrar_evento.", tipo_evento)
            return None

        usuario_id = getattr(usuario, 'pk', usuario) if usuario else None
        metadata_limpia = sanitizar_metadata(tipo_evento, metadata or {})

        connection = transaction.get_connection()
        if connection.in_atomic_block:
            transaction.on_commit(
                lambda: _ejecutar_guardado_evento(
                    usuario_id=usuario_id,
                    tipo_evento=tipo_evento,
                    objeto_tipo=objeto_tipo,
                    objeto_id=objeto_id,
                    metadata_limpia=metadata_limpia,
                    fecha=fecha
                )
            )
        else:
            _ejecutar_guardado_evento(
                usuario_id=usuario_id,
                tipo_evento=tipo_evento,
                objeto_tipo=objeto_tipo,
                objeto_id=objeto_id,
                metadata_limpia=metadata_limpia,
                fecha=fecha
            )
    except Exception as e:
        logger.error("Fallo inesperado en registrar_evento: %s", e, exc_info=True)
        return None


def registrar_auditoria_admin(admin, usuario_afectado, accion, detalles=""):
    """
    Registra una acción administrativa sensible en AuditoriaAdmin.
    """
    try:
        return AuditoriaAdmin.objects.create(
            admin=admin,
            usuario_afectado=usuario_afectado,
            accion=accion,
            detalles=detalles,
            fecha=timezone.now()
        )
    except Exception as e:
        logger.error("Error al registrar AuditoriaAdmin '%s': %s", accion, e, exc_info=True)
        return None
