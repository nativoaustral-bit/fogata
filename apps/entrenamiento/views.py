import json
import random
from dataclasses import asdict
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.planes import obtener_tipo_cuenta
from apps.gestion.services import registrar_evento
from .models import SesionEntrenamiento
from .musical import (
    obtener_catalogo_notas,
    obtener_catalogo_acordes,
    obtener_catalogo_progresiones,
    NOTA_REFERENCIA_DEFAULT,
)


def es_usuario_pro(user) -> bool:
    """Verifica si el usuario cuenta con suscripción o acceso Pro activo."""
    tipo = obtener_tipo_cuenta(user)
    return tipo in ('PRO', 'ADMIN', 'PILOTO')


def _verificar_modulo_activo():
    """Comprueba la activación controlada del módulo. Si está desactivado, arroja 404."""
    if not getattr(settings, 'FOGATA_EAR_TRAINING_ENABLED', True):
        raise Http404("El módulo Entrena tu oído no está habilitado actualmente.")


@login_required
def portada_entrenamiento(request: HttpRequest) -> HttpResponse:
    """
    Pantalla principal de «Entrena tu oído».
    Muestra la filosofía «Escucha. Encuentra. Toca.» y da acceso directo
    a las 3 modalidades: Notas, Acordes y Progresiones.
    """
    _verificar_modulo_activo()

    # Registro de métrica de acceso
    registrar_evento(
        usuario=request.user,
        tipo_evento='acceder_entrenamiento',
        objeto_tipo='modulo',
    )

    # Estadísticas voluntarias y ligeras del usuario
    sesiones_completadas = SesionEntrenamiento.objects.filter(
        usuario=request.user,
        completada=True
    ).count()

    ultima_sesion = SesionEntrenamiento.objects.filter(
        usuario=request.user,
        completada=True
    ).order_by('-finalizada_el').first()

    es_pro = es_usuario_pro(request.user)

    context = {
        'sesiones_completadas': sesiones_completadas,
        'ultima_sesion': ultima_sesion,
        'es_pro': es_pro,
    }
    return render(request, 'entrenamiento/portada.html', context)


@login_required
def entrenar_notas_view(request: HttpRequest) -> HttpResponse:
    """
    Modalidad 1 — Entrena notas.
    Prepara una sesión de 5 ejercicios con notas en un registro cómodo de guitarra,
    con posiciones exactas en el diapasón y nota de referencia opcional.
    Usuarios Gratis: Las 7 notas naturales (C, D, E, F, G, A, B).
    Usuarios Pro: Notas naturales y cromáticas con registros extendidos.
    """
    _verificar_modulo_activo()

    # Crear registro de sesión
    sesion = SesionEntrenamiento.objects.create(
        usuario=request.user,
        modalidad='notas',
        total_ejercicios=5,
    )

    registrar_evento(
        usuario=request.user,
        tipo_evento='iniciar_ejercicio_entrenamiento',
        objeto_tipo='sesion_entrenamiento',
        objeto_id=sesion.pk,
        metadata={'modalidad': 'notas', 'ejercicio_num': 1}
    )

    es_pro = es_usuario_pro(request.user)
    catalogo = obtener_catalogo_notas(solo_gratis=(not es_pro))
    # Tomar 5 notas aleatorias sin repetir en la misma sesión
    seleccion = random.sample(catalogo, k=min(5, len(catalogo)))

    ejercicios_data = []
    for ej in seleccion:
        ejercicios_data.append({
            'id': ej.id,
            'midi': ej.midi,
            'frecuencia': ej.frecuencia,
            'nombre_latino': ej.nombre_latino,
            'nombre_americano': ej.nombre_americano,
            'octava': ej.octava,
            'posiciones': [asdict(p) for p in ej.posiciones],
            'fretboard_svg': ej.fretboard_svg,
            'es_pro': ej.es_pro,
        })

    context = {
        'modalidad': 'notas',
        'titulo_modalidad': 'Encuentra la nota',
        'instruccion': 'Escucha la nota e intenta encontrarla en tu guitarra.',
        'sesion_id': sesion.pk,
        'ejercicios_json': json.dumps(ejercicios_data),
        'referencia_json': json.dumps(NOTA_REFERENCIA_DEFAULT),
        'total_ejercicios': 5,
        'es_pro': es_pro,
    }
    return render(request, 'entrenamiento/ejercicio_notas.html', context)


@login_required
def entrenar_acordes_view(request: HttpRequest) -> HttpResponse:
    """
    Modalidad 2 — Entrena acordes (Experiencia central).
    Prepara una sesión de 5 ejercicios basados en el catálogo musical de Fogata:
    Usuarios Gratis: 8 acordes estándar (C, G, D, A, E, Am, Em, Dm).
    Usuarios Pro: Catálogo completo ampliado con cejillas (F, B, Bm, F#m) y séptimas (C7, D7, G7, A7, E7, B7).
    """
    _verificar_modulo_activo()

    sesion = SesionEntrenamiento.objects.create(
        usuario=request.user,
        modalidad='acordes',
        total_ejercicios=5,
    )

    registrar_evento(
        usuario=request.user,
        tipo_evento='iniciar_ejercicio_entrenamiento',
        objeto_tipo='sesion_entrenamiento',
        objeto_id=sesion.pk,
        metadata={'modalidad': 'acordes', 'ejercicio_num': 1}
    )

    es_pro = es_usuario_pro(request.user)
    catalogo = obtener_catalogo_acordes(solo_gratis=(not es_pro))
    seleccion = random.sample(catalogo, k=min(5, len(catalogo)))

    ejercicios_data = []
    for ej in seleccion:
        ejercicios_data.append({
            'codigo': ej.codigo,
            'nombre_latino': ej.nombre_latino,
            'nombre_americano': ej.nombre_americano,
            'notas_componentes': ej.notas_componentes,
            'trastes_referencia': ej.trastes_referencia,
            'midi_referencia': ej.midi_referencia,
            'svg_referencia': ej.svg_referencia,
            'trastes_alternativa': ej.trastes_alternativa,
            'midi_alternativa': ej.midi_alternativa,
            'svg_alternativa': ej.svg_alternativa,
            'descripcion_alternativa': ej.descripcion_alternativa,
            'es_pro': ej.es_pro,
        })

    context = {
        'modalidad': 'acordes',
        'titulo_modalidad': 'Encuentra el acorde',
        'instruccion': 'Escucha el acorde. Intenta reproducirlo en tu guitarra. Cuando creas que lo encontraste, revela la respuesta.',
        'sesion_id': sesion.pk,
        'ejercicios_json': json.dumps(ejercicios_data),
        'total_ejercicios': 5,
        'es_pro': es_pro,
    }
    return render(request, 'entrenamiento/ejercicio_acordes.html', context)


@login_required
def entrenar_progresiones_view(request: HttpRequest) -> HttpResponse:
    """
    Modalidad 3 — Entrena progresiones.
    Prepara una sesión de 5 secuencias de acordes ordenadas progresivamente:
    Usuarios Gratis: Progresiones de 2 acordes básicos (G-D, Am-Em, C-G, D-A, C-Am, E-A, Dm-Am, Em-C).
    Usuarios Pro: Progresiones variadas de 2, 3 y 4 acordes (I-IV-V, i-iv-v, círculos armónicos).
    """
    _verificar_modulo_activo()

    sesion = SesionEntrenamiento.objects.create(
        usuario=request.user,
        modalidad='progresiones',
        total_ejercicios=5,
    )

    registrar_evento(
        usuario=request.user,
        tipo_evento='iniciar_ejercicio_entrenamiento',
        objeto_tipo='sesion_entrenamiento',
        objeto_id=sesion.pk,
        metadata={'modalidad': 'progresiones', 'ejercicio_num': 1}
    )

    es_pro = es_usuario_pro(request.user)
    catalogo = obtener_catalogo_progresiones(solo_gratis=(not es_pro))
    # Tomar 5 progresiones asegurando variedad
    seleccion = random.sample(catalogo, k=min(5, len(catalogo)))

    ejercicios_data = []
    for ej in seleccion:
        ejercicios_data.append({
            'id': ej.id,
            'titulo': ej.titulo,
            'acordes': ej.acordes,
            'acordes_str': ej.acordes_str,
            'explicacion': ej.explicacion,
            'diagramas_svg': ej.diagramas_svg,
            'audio_chords': ej.audio_chords,
            'es_pro': ej.es_pro,
        })

    context = {
        'modalidad': 'progresiones',
        'titulo_modalidad': 'Sigue la progresión',
        'instruccion': 'Escucha cómo cambian los acordes. Intenta seguirlos con tu guitarra.',
        'sesion_id': sesion.pk,
        'ejercicios_json': json.dumps(ejercicios_data),
        'total_ejercicios': 5,
        'es_pro': es_pro,
    }
    return render(request, 'entrenamiento/ejercicio_progresiones.html', context)


@login_required
@require_POST
def registrar_evento_api(request: HttpRequest) -> JsonResponse:
    """
    Endpoint JSON seguro para registrar telemetría de uso y progreso de sesión.
    No bloquea la experiencia en caso de falla y respeta la privacidad estricta.
    """
    _verificar_modulo_activo()

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    evento = data.get('tipo', '')
    modalidad = data.get('modalidad', '')
    sesion_id = data.get('sesion_id')

    sesion = None
    if sesion_id:
        sesion = SesionEntrenamiento.objects.filter(pk=sesion_id, usuario=request.user).first()

    if evento == 'reproducir_audio':
        es_rep = bool(data.get('es_repeticion', False))
        tipo = 'repetir_audio_entrenamiento' if es_rep else 'reproducir_audio_entrenamiento'
        registrar_evento(
            usuario=request.user,
            tipo_evento=tipo,
            metadata={'modalidad': modalidad, 'es_repeticion': es_rep}
        )

    elif evento == 'revelar_respuesta':
        ej_num = int(data.get('ejercicio_num', 1))
        registrar_evento(
            usuario=request.user,
            tipo_evento='revelar_respuesta_entrenamiento',
            metadata={'modalidad': modalidad, 'ejercicio_num': ej_num}
        )

    elif evento == 'autoevaluacion':
        resultado = str(data.get('resultado', 'practicar')).strip().lower()
        if resultado not in ('encontre', 'practicar'):
            resultado = 'practicar'

        if sesion:
            sesion.ejercicios_completados += 1
            if resultado == 'encontre':
                sesion.aciertos_declarados += 1
            sesion.save(update_fields=['ejercicios_completados', 'aciertos_declarados'])

        registrar_evento(
            usuario=request.user,
            tipo_evento='autoevaluacion_entrenamiento',
            metadata={'modalidad': modalidad, 'resultado_declarado': resultado}
        )

    elif evento == 'completar_sesion':
        total = int(data.get('total_ejercicios', 5))
        aciertos = int(data.get('aciertos_declarados', 0))

        if sesion:
            sesion.completada = True
            sesion.finalizada_el = timezone.now()
            sesion.save(update_fields=['completada', 'finalizada_el'])

        registrar_evento(
            usuario=request.user,
            tipo_evento='completar_sesion_entrenamiento',
            objeto_tipo='sesion_entrenamiento',
            objeto_id=sesion.pk if sesion else None,
            metadata={
                'modalidad': modalidad,
                'total_ejercicios': total,
                'aciertos_declarados': aciertos,
            }
        )

    return JsonResponse({'ok': True})

