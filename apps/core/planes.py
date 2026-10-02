from django.conf import settings
from django.utils import timezone
from apps.canciones.models import Cancion
from apps.fogatas.models import Fogata


def obtener_tipo_cuenta(user) -> str:
    """
    Retorna la modalidad o tipo de cuenta efectivo del usuario:
    - 'ADMIN': Si el usuario es staff o superusuario.
    - 'PILOTO', 'PRO', 'GRATIS': Según PerfilPiloto.tipo_cuenta.
      Si el usuario es 'PRO' pero su fecha_fin_plan ya venció, se degrada
      inmediatamente a 'GRATIS' en tiempo real (defensa en profundidad).
    - 'ANONIMO': Si el usuario no está autenticado.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return 'ANONIMO'
    if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
        return 'ADMIN'

    perfil = getattr(user, 'perfil_piloto', None)
    if perfil and perfil.tipo_cuenta:
        if perfil.tipo_cuenta == 'PRO':
            if perfil.fecha_fin_plan and perfil.fecha_fin_plan <= timezone.now():
                return 'GRATIS'
            return 'PRO'
        return perfil.tipo_cuenta

    return 'PILOTO'


def limite_canciones(user):
    """
    Retorna el número máximo de canciones permitidas según el plan:
    - None: Ilimitado (ADMIN, PILOTO, PRO).
    - int: Límite numérico (GRATIS, por defecto settings.FOGATA_FREE_MAX_SONGS).
    """
    tipo = obtener_tipo_cuenta(user)
    if tipo in ('ADMIN', 'PILOTO', 'PRO'):
        return None
    return getattr(settings, 'FOGATA_FREE_MAX_SONGS', 10)


def limite_fogatas(user):
    """
    Retorna el número máximo de Fogatas simultáneas permitidas:
    - None: Ilimitado (ADMIN, PILOTO, PRO).
    - int: Límite numérico (GRATIS, por defecto settings.FOGATA_FREE_MAX_FOGATAS).
    """
    tipo = obtener_tipo_cuenta(user)
    if tipo in ('ADMIN', 'PILOTO', 'PRO'):
        return None
    return getattr(settings, 'FOGATA_FREE_MAX_FOGATAS', 1)


def canciones_utilizadas(user) -> int:
    """
    Conteo de canciones activas creadas por el usuario en su biblioteca.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return 0
    return Cancion.objects.filter(propietario=user).count()


def fogatas_utilizadas(user) -> int:
    """
    Conteo de Fogatas activas creadas por el usuario.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return 0
    return Fogata.objects.filter(propietario=user).count()


def puede_crear_cancion(user, bloquear: bool = False) -> bool:
    """
    Determina si el usuario tiene cupo para crear una nueva canción.
    Si bloquear=True (dentro de una transacción), adquiere bloqueo select_for_update.
    Nota de arquitectura: En PostgreSQL esto aplica bloqueo de fila fuerte; en SQLite
    la serialización descansa en la transacción atómica a nivel de base de datos.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    limite = limite_canciones(user)
    if limite is None:
        return True

    if bloquear:
        from django.contrib.auth.models import User
        try:
            User.objects.select_for_update().filter(pk=user.pk).exists()
        except Exception:
            pass

    return Cancion.objects.filter(propietario=user).count() < limite


def puede_crear_fogata(user, bloquear: bool = False) -> bool:
    """
    Determina si el usuario tiene cupo para crear una nueva Fogata.
    Si bloquear=True (dentro de una transacción), adquiere bloqueo select_for_update.
    Nota de arquitectura: En PostgreSQL esto aplica bloqueo de fila fuerte; en SQLite
    la serialización descansa en la transacción atómica a nivel de base de datos.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    limite = limite_fogatas(user)
    if limite is None:
        return True

    if bloquear:
        from django.contrib.auth.models import User
        try:
            User.objects.select_for_update().filter(pk=user.pk).exists()
        except Exception:
            pass

    return Fogata.objects.filter(propietario=user).count() < limite


def obtener_estado_capacidad(user) -> dict:
    """
    Estructura unificada de estado comercial y capacidad para vistas y plantillas.
    """
    tipo = obtener_tipo_cuenta(user)
    es_ilimitado = (tipo in ('ADMIN', 'PILOTO', 'PRO'))

    nombres_plan = {
        'ADMIN': 'Administrador',
        'PILOTO': 'Piloto',
        'PRO': 'Fogata Pro',
        'GRATIS': 'Fogata Gratis',
        'ANONIMO': 'Invitado',
    }
    nombre_plan = nombres_plan.get(tipo, 'Fogata Gratis')

    c_usadas = canciones_utilizadas(user)
    c_limite = limite_canciones(user)
    c_disponibles = (c_limite - c_usadas) if c_limite is not None else None

    f_usadas = fogatas_utilizadas(user)
    f_limite = limite_fogatas(user)
    f_disponibles = (f_limite - f_usadas) if f_limite is not None else None

    # Estado de advertencia cercana (8 o 9 canciones en Gratis)
    cercano_limite = (c_limite is not None and c_usadas >= (c_limite - 2) and c_usadas < c_limite)

    return {
        'tipo_cuenta': tipo,
        'nombre_plan': nombre_plan,
        'es_ilimitado': es_ilimitado,
        'canciones_usadas': c_usadas,
        'canciones_limite': c_limite,
        'canciones_disponibles': c_disponibles,
        'puede_crear_cancion': (c_limite is None or c_usadas < c_limite),
        'sobre_limite_canciones': (c_limite is not None and c_usadas >= c_limite),
        'es_cercano_limite_canciones': cercano_limite,
        'fogatas_usadas': f_usadas,
        'fogatas_limite': f_limite,
        'fogatas_disponibles': f_disponibles,
        'puede_crear_fogata': (f_limite is None or f_usadas < f_limite),
        'sobre_limite_fogatas': (f_limite is not None and f_usadas >= f_limite),
    }
