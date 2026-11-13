from django.conf import settings
from .planes import obtener_tipo_cuenta


def plan_context(request):
    """
    Provee información ligera del plan comercial del usuario para templates globales.
    Evita queries costosas de conteo en cada carga de página.
    """
    entrenamiento_activo = getattr(settings, 'FOGATA_EAR_TRAINING_ENABLED', True)

    if getattr(request, 'user', None) and request.user.is_authenticated:
        tipo = obtener_tipo_cuenta(request.user)
        nombres = {
            'ADMIN': 'Administrador',
            'PILOTO': 'Piloto',
            'PRO': 'Pro',
            'GRATIS': 'Gratis',
        }
        return {
            'tipo_plan_usuario': tipo,
            'nombre_plan_usuario': nombres.get(tipo, 'Gratis'),
            'es_plan_pro': tipo in ('PRO', 'ADMIN', 'PILOTO'),
            'modulo_entrenamiento_activo': entrenamiento_activo,
        }
    return {
        'tipo_plan_usuario': 'ANONIMO',
        'nombre_plan_usuario': '',
        'es_plan_pro': False,
        'modulo_entrenamiento_activo': entrenamiento_activo,
    }
