from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from .models import Cancion
from .forms import CancionForm
from .parser import reemplazar_acorde_en_contenido
from apps.gestion.services import registrar_evento
from apps.core.planes import puede_crear_cancion, canciones_utilizadas, limite_canciones, obtener_estado_capacidad


def obtener_parametros_musicales(request):
    """
    Extrae y valida parámetros de transposición (-6 a +6) y notación visual
    para renderizado server-side / fallback sin JavaScript (Criterios 10, 11, 12, 14).
    """
    semitonos_raw = request.GET.get('semitonos', '0').strip()
    try:
        semitonos = int(semitonos_raw)
        if semitonos < -6 or semitonos > 6:
            semitonos = 0
    except (ValueError, TypeError):
        semitonos = 0

    notacion = request.GET.get('notacion', 'original').strip().lower()
    if notacion not in ('original', 'american', 'latin'):
        notacion = 'original'

    return semitonos, notacion


@login_required
def lista(request):
    """
    Listado general de canciones del usuario autenticado.
    Permite búsqueda simple por título o artista dentro de su propia biblioteca.
    """
    query = request.GET.get('q', '').strip()
    canciones = Cancion.objects.filter(propietario=request.user)

    if query:
        canciones = canciones.filter(
            Q(titulo__icontains=query) | Q(artista__icontains=query)
        )

    context = {
        'canciones': canciones,
        'query': query,
        'total': canciones.count(),
        'capacidad': obtener_estado_capacidad(request.user),
    }
    return render(request, 'canciones/lista.html', context)


@login_required
def detalle(request, pk):
    """
    Ficha de detalle de una canción con acceso directo a 'Modo Músico (Tocar)',
    edición, eliminación, edición rápida de acordes y Fogatas en las que participa.
    """
    cancion = get_object_or_404(Cancion, pk=pk, propietario=request.user)
    fogatas_asociadas = cancion.en_fogatas.filter(fogata__propietario=request.user).select_related('fogata')
    context = {
        'cancion': cancion,
        'fogatas_asociadas': fogatas_asociadas,
    }
    return render(request, 'canciones/detalle.html', context)


@login_required
def crear(request):
    """
    Crear una nueva canción en el repertorio del usuario.
    Soporta flujo directo 'Pegar y Tocar' con el botón Guardar y Tocar.
    Protegido por límites comerciales Freemium (Fase 8).
    """
    # 1. Verificación comercial inicial (GET o previo a validación)
    if not puede_crear_cancion(request.user):
        clave_sesion = 'evento_limite_canciones'
        ahora_ts = timezone.now().timestamp()
        ultima_alerta = request.session.get(clave_sesion)
        if not ultima_alerta or (ahora_ts - float(ultima_alerta)) >= 300:
            registrar_evento(
                usuario=request.user,
                tipo_evento='alcanzar_limite_canciones',
                objeto_tipo='cancion',
                metadata={'intentos': 1}
            )
            request.session[clave_sesion] = ahora_ts

        context = {
            'canciones_utilizadas': canciones_utilizadas(request.user),
            'limite_canciones': limite_canciones(request.user),
        }
        return render(request, 'canciones/limite_alcanzado.html', context)

    if request.method == 'POST':
        form = CancionForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Re-validación atómica con bloqueo ante peticiones concurrentes (Criterios 12 y 13)
                if not puede_crear_cancion(request.user, bloquear=True):
                    clave_sesion = 'evento_limite_canciones'
                    ahora_ts = timezone.now().timestamp()
                    ultima_alerta = request.session.get(clave_sesion)
                    if not ultima_alerta or (ahora_ts - float(ultima_alerta)) >= 300:
                        registrar_evento(
                            usuario=request.user,
                            tipo_evento='alcanzar_limite_canciones',
                            objeto_tipo='cancion',
                            metadata={'intentos': 1}
                        )
                        request.session[clave_sesion] = ahora_ts
                    context = {
                        'canciones_utilizadas': canciones_utilizadas(request.user),
                        'limite_canciones': limite_canciones(request.user),
                    }
                    return render(request, 'canciones/limite_alcanzado.html', context)

                cancion = form.save(commit=False)
                cancion.propietario = request.user
                cancion.save()

            registrar_evento(
                usuario=request.user,
                tipo_evento='crear_cancion',
                objeto_tipo='cancion',
                objeto_id=cancion.pk
            )
            if request.POST.get('accion_guardar') == 'tocar':
                return redirect('canciones:tocar', pk=cancion.pk)
            return redirect('canciones:detalle', pk=cancion.pk)
    else:
        form = CancionForm()

    context = {
        'form': form,
        'accion': 'Nueva Canción',
    }
    return render(request, 'canciones/crear_editar.html', context)


@login_required
def editar(request, pk):
    """
    Editar los metadatos o el contenido íntegro de la canción del usuario.
    """
    cancion = get_object_or_404(Cancion, pk=pk, propietario=request.user)
    if request.method == 'POST':
        form = CancionForm(request.POST, instance=cancion)
        if form.is_valid():
            cancion = form.save()
            registrar_evento(
                usuario=request.user,
                tipo_evento='editar_cancion',
                objeto_tipo='cancion',
                objeto_id=cancion.pk
            )
            if request.POST.get('accion_guardar') == 'tocar':
                return redirect('canciones:tocar', pk=cancion.pk)
            return redirect('canciones:detalle', pk=cancion.pk)
    else:
        form = CancionForm(instance=cancion)

    context = {
        'form': form,
        'cancion': cancion,
        'accion': 'Editar Canción',
    }
    return render(request, 'canciones/crear_editar.html', context)


@login_required
def eliminar(request, pk):
    """
    Confirmación y eliminación de canción propia.
    """
    cancion = get_object_or_404(Cancion, pk=pk, propietario=request.user)
    if request.method == 'POST':
        cancion.delete()
        return redirect('canciones:lista')

    context = {
        'cancion': cancion,
    }
    return render(request, 'canciones/eliminar.html', context)


@login_required
def tocar(request, pk):
    """
    Modo Músico / Pantalla de Atril para canción propia.
    Debounce de 5 minutos por canción en la sesión para evitar spam por refresh (Criterio 9).
    """
    cancion = get_object_or_404(Cancion, pk=pk, propietario=request.user)
    semitonos, notacion = obtener_parametros_musicales(request)

    clave_sesion = f'ultima_apertura_cancion_{cancion.pk}'
    ultima_apertura = request.session.get(clave_sesion)
    ahora_ts = timezone.now().timestamp()
    if not ultima_apertura or (ahora_ts - float(ultima_apertura)) >= 300:
        registrar_evento(
            usuario=request.user,
            tipo_evento='tocar_cancion',
            objeto_tipo='cancion',
            objeto_id=cancion.pk,
            metadata={'origen': 'directo'}
        )
        request.session[clave_sesion] = ahora_ts

    context = {
        'cancion': cancion,
        'modo_musico': True,
        'semitonos': semitonos,
        'notacion': notacion,
        'semitonos_mas_uno': min(6, semitonos + 1),
        'semitonos_menos_uno': max(-6, semitonos - 1),
    }
    return render(request, 'canciones/tocar.html', context)


@login_required
def editar_acordes(request, pk):
    """
    Ficha de Canción -> Editar Acordes propia (Criterios 2, 3, 4, 5).
    """
    cancion = get_object_or_404(Cancion, pk=pk, propietario=request.user)
    context = {
        'cancion': cancion,
        'modo_edicion': True,
    }
    return render(request, 'canciones/editar_acordes.html', context)


@login_required
def guardar_edicion_acorde(request, pk):
    """
    Endpoint para guardar la corrección rápida de un acorde (Requisitos 2, 3, 4, 5).
    """
    cancion = get_object_or_404(Cancion, pk=pk, propietario=request.user)
    if request.method != 'POST':
        return redirect('canciones:editar_acordes', pk=cancion.pk)

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')

    try:
        num_linea = int(request.POST.get('num_linea', -1))
        col_inicio = int(request.POST.get('col_inicio', -1))
        col_fin = int(request.POST.get('col_fin', -1))
    except (ValueError, TypeError):
        error_msg = "Parámetros de posición inválidos."
        if is_ajax:
            return JsonResponse({'ok': False, 'error': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect('canciones:editar_acordes', pk=cancion.pk)

    texto_original = request.POST.get('texto_original', '')
    nuevo_acorde = request.POST.get('nuevo_acorde', '').strip()
    modo = request.POST.get('modo', 'uno')

    exito, nuevo_contenido, error_msg = reemplazar_acorde_en_contenido(
        contenido=cancion.contenido,
        num_linea=num_linea,
        col_inicio=col_inicio,
        col_fin=col_fin,
        texto_original=texto_original,
        nuevo_acorde=nuevo_acorde,
        modo=modo
    )

    if not exito:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect('canciones:editar_acordes', pk=cancion.pk)

    cancion.contenido = nuevo_contenido
    cancion.save(update_fields=['contenido', 'updated_at'])
    registrar_evento(
        usuario=request.user,
        tipo_evento='editar_cancion',
        objeto_tipo='cancion',
        objeto_id=cancion.pk
    )

    if modo == 'todos':
        msg = f"Se actualizaron todas las apariciones de «{texto_original}» por «{nuevo_acorde}»."
    else:
        msg = f"Se actualizó el acorde «{texto_original}» por «{nuevo_acorde}»."

    if is_ajax:
        return JsonResponse({
            'ok': True,
            'mensaje': msg,
            'nuevo_acorde': nuevo_acorde,
            'modo': modo
        })

    messages.success(request, msg)
    return redirect('canciones:editar_acordes', pk=cancion.pk)


VOCABULARIO_MODIFICADORES_VALIDOS = {
    '', 'm', 'min', 'minor', 'M',
    '7', 'maj7', 'M7', 'Δ7', 'Δ', 'min7', 'm7',
    'sus4', 'sus2', 'sus', '7sus4', '7sus2',
    'add9', 'add2', 'add', '6', '6/9', 'dim', 'dim7', 'aug', 'm7b5'
}


def ver_diagrama(request):
    """
    Endpoint canónico para consulta de diagramas de acordes (Criterios 6, 7, 15, 16, 17).
    Parámetros validados:
      - root: 0..11
      - mod: vocabulario musical conocido
      - bass: opcional 0..11
      - notacion: 'american' | 'latin'
      - cancion_id: opcional int
      - fogata_id: opcional int
      - pos: opcional int
      - semitonos: opcional int (-6..6)
      - anchor: opcional str (ancla segura)
    """
    import re
    from django.http import HttpResponseBadRequest
    from .diagramas import obtener_info_diagrama

    root_raw = request.GET.get('root', '').strip()
    try:
        root = int(root_raw)
        if root < 0 or root > 11:
            raise ValueError()
    except (ValueError, TypeError):
        return HttpResponseBadRequest("Parámetro 'root' inválido (debe ser un entero entre 0 y 11).")

    mod = request.GET.get('mod', '').strip()
    if mod not in VOCABULARIO_MODIFICADORES_VALIDOS:
        return HttpResponseBadRequest("Modificador musical no reconocido.")

    bass_raw = request.GET.get('bass', '').strip()
    bajo_pitch = None
    if bass_raw:
        try:
            bajo_pitch = int(bass_raw)
            if bajo_pitch < 0 or bajo_pitch > 11:
                raise ValueError()
        except (ValueError, TypeError):
            return HttpResponseBadRequest("Parámetro 'bass' inválido (debe ser un entero entre 0 y 11).")

    notacion = request.GET.get('notacion', 'american').strip().lower()
    if notacion not in ('american', 'latin'):
        notacion = 'american'

    # Parámetros contextuales para retorno seguro (Criterios 15, 16, 17)
    cancion_id = request.GET.get('cancion_id', '').strip()
    fogata_id = request.GET.get('fogata_id', '').strip()
    pos = request.GET.get('pos', '').strip()
    semitonos_raw = request.GET.get('semitonos', '0').strip()
    try:
        semitonos = int(semitonos_raw)
        if semitonos < -6 or semitonos > 6:
            semitonos = 0
    except (ValueError, TypeError):
        semitonos = 0

    anchor_raw = request.GET.get('anchor', '').strip()
    anchor = ''
    if re.match(r'^[a-zA-Z0-9_\-]+$', anchor_raw):
        anchor = anchor_raw

    from apps.fogatas.models import Fogata

    cancion = None
    if cancion_id.isdigit() and request.user.is_authenticated:
        cancion = Cancion.objects.filter(pk=int(cancion_id), propietario=request.user).first()

    fogata = None
    if fogata_id.isdigit() and request.user.is_authenticated:
        fogata = Fogata.objects.filter(pk=int(fogata_id), propietario=request.user).first()

    afinacion = cancion.afinacion if cancion else None
    tonalidad = cancion.tonalidad if cancion else None
    usar_bemoles = False
    if tonalidad:
        t_clean = tonalidad.strip().upper()
        if 'B' in t_clean or '♭' in t_clean:
            usar_bemoles = True

    info = obtener_info_diagrama(
        pitch_raiz=root,
        modificador=mod,
        bajo_pitch=bajo_pitch,
        notacion=notacion,
        usar_bemoles=usar_bemoles,
        afinacion=afinacion
    )

    # Respuesta JSON para peticiones AJAX / XHR desde el cliente (Criterio 8)
    is_ajax = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
        or request.GET.get('format') == 'json'
    )
    if is_ajax:
        return JsonResponse({
            'ok': True,
            'disponible': info['disponible'],
            'nombre': info['nombre'],
            'svg': info['svg'],
            'mensaje': info['mensaje'],
            'advertencia_afinacion': info['advertencia_afinacion']
        })

    # Construcción de URL de retorno segura sin redirecciones abiertas (Criterio 16 y 17)
    from django.urls import reverse
    if fogata and pos.isdigit():
        return_url = reverse('fogatas:tocar_sesion', args=[fogata.pk]) + f"?pos={pos}&semitonos={semitonos}&notacion={notacion}"
    elif cancion:
        return_url = reverse('canciones:tocar', args=[cancion.pk]) + f"?semitonos={semitonos}&notacion={notacion}"
    else:
        return_url = reverse('canciones:lista')

    if anchor:
        return_url += f"#{anchor}"

    context = {
        'info': info,
        'cancion': cancion,
        'return_url': return_url,
    }
    return render(request, 'canciones/diagrama_detalle.html', context)


def diagramas_batch(request):
    """
    Retorna la biblioteca completa de 64 digitaciones verificadas en un único
    payload JSON estructurado para precarga atómica en caché offline (Fase 5).
    Incluye variantes en notación americana y latina para cada acorde.
    """
    from apps.canciones.diagramas import (
        BIBLIOTECA_ACORDES,
        pitch_class_a_nota,
        generar_svg_acorde
    )

    items = {}
    for (root, mod, bass), digitacion in BIBLIOTECA_ACORDES.items():
        bass_key = str(bass) if bass is not None else ""
        key = f"{root}|{mod}|{bass_key}"

        nom_am = pitch_class_a_nota(root, notacion='american') + mod
        nom_lat = pitch_class_a_nota(root, notacion='latin') + mod
        if bass is not None:
            nom_am += f"/{pitch_class_a_nota(bass, notacion='american')}"
            nom_lat += f"/{pitch_class_a_nota(bass, notacion='latin')}"

        svg_am = generar_svg_acorde(digitacion, nombre_mostrar=nom_am)
        svg_lat = generar_svg_acorde(digitacion, nombre_mostrar=nom_lat)

        items[key] = {
            'root': root,
            'mod': mod,
            'bass': bass,
            'nombre_american': nom_am,
            'nombre_latin': nom_lat,
            'svg_american': svg_am,
            'svg_latin': svg_lat
        }

    return JsonResponse({
        'ok': True,
        'total': len(items),
        'diagramas': items
    })


