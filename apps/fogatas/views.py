from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.http import HttpResponseGone
from django.db import transaction
from django.db.models import Max
from .models import Fogata, FogataCancion, SesionCompartida
from .forms import FogataForm, AgregarCancionForm, CrearSesionCompartidaForm
from apps.canciones.models import Cancion
from apps.canciones.services import obtener_solo_letra


# ==========================================
# Helpers de Privacidad y Sesiones
# ==========================================

def aplicar_cabeceras_privacidad(response):
    """
    Aplica cabeceras estrictas de privacidad y no-caché a todas las respuestas
    de sesiones compartidas (Criterio 5).
    """
    response['Cache-Control'] = 'no-store, private'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


def respuesta_sesion_expirada(request):
    """
    Retorna respuesta HTTP 410 (Gone) con pantalla sobria informativa.
    """
    response = render(request, 'fogatas/sesion_compartida/expirada.html', status=410)
    return aplicar_cabeceras_privacidad(response)


# ==========================================
# Vistas de Gestión de Fogatas (Músico)
# ==========================================

def lista(request):
    """
    Listado de todas las Fogatas creadas.
    """
    fogatas = Fogata.objects.all().prefetch_related('canciones_asociadas')
    context = {
        'fogatas': fogatas,
        'total': fogatas.count(),
    }
    return render(request, 'fogatas/lista.html', context)


def detalle(request, pk):
    """
    Detalle de una Fogata con su setlist ordenado, sesiones compartidas activas
    y opciones de gestión.
    """
    fogata = get_object_or_404(Fogata, pk=pk)
    canciones_asociadas = fogata.canciones_asociadas.select_related('cancion').order_by('orden')
    sesiones_activas = [s for s in fogata.sesiones_compartidas.filter(activa=True) if s.esta_vigente()]

    context = {
        'fogata': fogata,
        'canciones_asociadas': canciones_asociadas,
        'sesiones_activas': sesiones_activas,
        'form_compartir': CrearSesionCompartidaForm(),
    }
    return render(request, 'fogatas/detalle.html', context)


def crear(request):
    """
    Crea una nueva Fogata.
    """
    if request.method == 'POST':
        form = FogataForm(request.POST)
        if form.is_valid():
            fogata = form.save()
            return redirect('fogatas:detalle', pk=fogata.pk)
    else:
        form = FogataForm()

    context = {
        'form': form,
        'accion': 'Nueva Fogata',
    }
    return render(request, 'fogatas/crear_editar.html', context)


def editar(request, pk):
    """
    Edita nombre o descripción de la Fogata.
    """
    fogata = get_object_or_404(Fogata, pk=pk)
    if request.method == 'POST':
        form = FogataForm(request.POST, instance=fogata)
        if form.is_valid():
            fogata = form.save()
            return redirect('fogatas:detalle', pk=fogata.pk)
    else:
        form = FogataForm(instance=fogata)

    context = {
        'form': form,
        'fogata': fogata,
        'accion': 'Editar Fogata',
    }
    return render(request, 'fogatas/crear_editar.html', context)


def eliminar(request, pk):
    """
    Elimina una Fogata (las canciones originales no se eliminan).
    """
    fogata = get_object_or_404(Fogata, pk=pk)
    if request.method == 'POST':
        fogata.delete()
        return redirect('fogatas:lista')

    context = {
        'fogata': fogata,
    }
    return render(request, 'fogatas/eliminar.html', context)


def agregar_cancion(request, pk):
    """
    Agrega una canción existente al setlist de la Fogata.
    """
    fogata = get_object_or_404(Fogata, pk=pk)
    if request.method == 'POST':
        form = AgregarCancionForm(request.POST, fogata=fogata)
        if form.is_valid():
            cancion = form.cleaned_data['cancion']
            nota_sesion = form.cleaned_data.get('nota_sesion', '')

            # Calcular siguiente orden
            max_orden = fogata.canciones_asociadas.aggregate(Max('orden'))['orden__max'] or 0
            siguiente_orden = max_orden + 1

            FogataCancion.objects.create(
                fogata=fogata,
                cancion=cancion,
                orden=siguiente_orden,
                nota_sesion=nota_sesion
            )
            return redirect('fogatas:detalle', pk=fogata.pk)
    else:
        form = AgregarCancionForm(fogata=fogata)

    context = {
        'fogata': fogata,
        'form': form,
    }
    return render(request, 'fogatas/agregar_cancion.html', context)


def quitar_cancion(request, fogata_pk, cancion_pk):
    """
    Quita una canción del setlist y reordena las restantes.
    """
    fogata = get_object_or_404(Fogata, pk=fogata_pk)
    if request.method == 'POST':
        FogataCancion.objects.filter(fogata=fogata, cancion_id=cancion_pk).delete()

        # Reordenar correlativamente
        with transaction.atomic():
            for i, item in enumerate(fogata.canciones_asociadas.order_by('orden'), start=1):
                item.orden = i
                item.save(update_fields=['orden'])

    return redirect('fogatas:detalle', pk=fogata.pk)


def mover_cancion(request, fogata_pk, cancion_pk, direccion):
    """
    Sube o baja una canción en el setlist.
    direccion: 'subir' | 'bajar'
    """
    fogata = get_object_or_404(Fogata, pk=fogata_pk)
    if request.method == 'POST':
        asociaciones = list(fogata.canciones_asociadas.order_by('orden'))
        indice_actual = next((i for i, a in enumerate(asociaciones) if a.cancion_id == cancion_pk), None)

        if indice_actual is not None:
            if direccion == 'subir' and indice_actual > 0:
                asociaciones[indice_actual], asociaciones[indice_actual - 1] = asociaciones[indice_actual - 1], asociaciones[indice_actual]
            elif direccion == 'bajar' and indice_actual < len(asociaciones) - 1:
                asociaciones[indice_actual], asociaciones[indice_actual + 1] = asociaciones[indice_actual + 1], asociaciones[indice_actual]

            with transaction.atomic():
                for i, item in enumerate(asociaciones, start=1):
                    item.orden = i
                    item.save(update_fields=['orden'])

    return redirect('fogatas:detalle', pk=fogata.pk)


def tocar_sesion(request, pk):
    """
    Modo Músico para una Fogata completa (ejecución continua de setlist).
    Permite avanzar tema a tema (Anterior / Siguiente) sin abandonar la pantalla completa.
    Lectura siempre en columna única vertical.
    """
    fogata = get_object_or_404(Fogata, pk=pk)
    items = list(fogata.canciones_asociadas.select_related('cancion').order_by('orden'))

    if not items:
        return redirect('fogatas:detalle', pk=fogata.pk)

    pos_param = request.GET.get('pos', '1')
    try:
        pos = int(pos_param)
    except ValueError:
        pos = 1

    if pos < 1:
        pos = 1
    elif pos > len(items):
        pos = len(items)

    item_actual = items[pos - 1]
    cancion_actual = item_actual.cancion

    anterior_pos = pos - 1 if pos > 1 else None
    siguiente_pos = pos + 1 if pos < len(items) else None

    context = {
        'fogata': fogata,
        'item_actual': item_actual,
        'cancion': cancion_actual,
        'pos': pos,
        'total_canciones': len(items),
        'anterior_pos': anterior_pos,
        'siguiente_pos': siguiente_pos,
        'items': items,
        'modo_musico': True,
    }
    return render(request, 'fogatas/tocar_sesion.html', context)


# ==========================================
# Gestión de Sesiones Compartidas
# ==========================================

def compartir_crear(request, pk):
    """
    Genera un nuevo enlace temporal criptográficamente seguro para la Fogata.
    """
    fogata = get_object_or_404(Fogata, pk=pk)
    if request.method == 'POST':
        form = CrearSesionCompartidaForm(request.POST)
        if form.is_valid():
            duracion = int(form.cleaned_data['duracion_horas'])
            expira = timezone.now() + timezone.timedelta(hours=duracion)
            sesion = SesionCompartida.objects.create(
                fogata=fogata,
                expira_el=expira
            )
            return redirect('fogatas:compartir_exito', pk=fogata.pk, sesion_id=sesion.pk)

    return redirect('fogatas:detalle', pk=fogata.pk)


def compartir_exito(request, pk, sesion_id):
    """
    Muestra el enlace generado y los detalles de la sesión compartida.
    """
    fogata = get_object_or_404(Fogata, pk=pk)
    sesion = get_object_or_404(SesionCompartida, pk=sesion_id, fogata=fogata)
    url_publica = request.build_absolute_uri(sesion.get_absolute_url())

    context = {
        'fogata': fogata,
        'sesion': sesion,
        'url_publica': url_publica,
    }
    return render(request, 'fogatas/compartir_sesion.html', context)


def compartir_revocar(request, pk, sesion_id):
    """
    Revoca un enlace compartido antes de su fecha natural de expiración.
    """
    fogata = get_object_or_404(Fogata, pk=pk)
    sesion = get_object_or_404(SesionCompartida, pk=sesion_id, fogata=fogata)
    if request.method == 'POST':
        sesion.revocar()
    return redirect('fogatas:detalle', pk=fogata.pk)


# ==========================================
# Experiencia de Invitado (Rutas Públicas /s/<token>/)
# ==========================================

def sesion_compartida_detalle(request, token):
    """
    Vista pública para invitados del setlist de la Fogata.
    Aplica HTTP 410 si ha expirado o revocado.
    Aplica cabeceras X-Robots-Tag y Cache-Control en todas las respuestas.
    """
    try:
        sesion = SesionCompartida.objects.select_related('fogata').get(token=token)
    except SesionCompartida.DoesNotExist:
        return respuesta_sesion_expirada(request)

    if not sesion.esta_vigente():
        return respuesta_sesion_expirada(request)

    canciones_asociadas = sesion.fogata.canciones_asociadas.select_related('cancion').order_by('orden')

    context = {
        'sesion': sesion,
        'fogata': sesion.fogata,
        'canciones_asociadas': canciones_asociadas,
    }
    response = render(request, 'fogatas/sesion_compartida/detalle.html', context)
    return aplicar_cabeceras_privacidad(response)


def sesion_compartida_cancion(request, token, cancion_id):
    """
    Vista pública de letra para invitados.
    Muestra la letra en formato de lectura vertical y fluido.
    Aplica cabeceras de privacidad y validación HTTP 410.
    """
    try:
        sesion = SesionCompartida.objects.select_related('fogata').get(token=token)
    except SesionCompartida.DoesNotExist:
        return respuesta_sesion_expirada(request)

    if not sesion.esta_vigente():
        return respuesta_sesion_expirada(request)

    item = get_object_or_404(
        FogataCancion.objects.select_related('cancion'),
        fogata=sesion.fogata,
        cancion_id=cancion_id
    )

    # Preparado para extraer letra con helper tolerante
    letra = obtener_solo_letra(item.cancion.contenido)

    context = {
        'sesion': sesion,
        'fogata': sesion.fogata,
        'item': item,
        'cancion': item.cancion,
        'letra': letra,
    }
    response = render(request, 'fogatas/sesion_compartida/cancion.html', context)
    return aplicar_cabeceras_privacidad(response)
