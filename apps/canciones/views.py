from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from .models import Cancion
from .forms import CancionForm


def lista(request):
    """
    Listado general de canciones.
    Permite búsqueda simple por título o artista.
    """
    query = request.GET.get('q', '').strip()
    canciones = Cancion.objects.all()

    if query:
        canciones = canciones.filter(
            Q(titulo__icontains=query) | Q(artista__icontains=query)
        )

    context = {
        'canciones': canciones,
        'query': query,
        'total': canciones.count(),
    }
    return render(request, 'canciones/lista.html', context)


def detalle(request, pk):
    """
    Ficha de detalle de una canción con acceso directo a 'Modo Músico (Tocar)',
    edición, eliminación y Fogatas en las que participa.
    """
    cancion = get_object_or_404(Cancion, pk=pk)
    fogatas_asociadas = cancion.en_fogatas.select_related('fogata').all()
    context = {
        'cancion': cancion,
        'fogatas_asociadas': fogatas_asociadas,
    }
    return render(request, 'canciones/detalle.html', context)


def crear(request):
    """
    Crear una nueva canción en el repertorio.
    Soporta flujo directo 'Pegar y Tocar' con el botón Guardar y Tocar.
    """
    if request.method == 'POST':
        form = CancionForm(request.POST)
        if form.is_valid():
            cancion = form.save()
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


def editar(request, pk):
    """
    Editar los metadatos o el contenido íntegro de la canción.
    """
    cancion = get_object_or_404(Cancion, pk=pk)
    if request.method == 'POST':
        form = CancionForm(request.POST, instance=cancion)
        if form.is_valid():
            cancion = form.save()
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


def eliminar(request, pk):
    """
    Confirmación y eliminación de canción.
    """
    cancion = get_object_or_404(Cancion, pk=pk)
    if request.method == 'POST':
        cancion.delete()
        return redirect('canciones:lista')

    context = {
        'cancion': cancion,
    }
    return render(request, 'canciones/eliminar.html', context)


def tocar(request, pk):
    """
    Modo Músico / Pantalla de Atril.
    Prioriza legibilidad extrema en atril, contraste alto, tipografía monoespaciada
    y preservación espacial estricta (white-space: pre).
    Lectura siempre en columna única.
    """
    cancion = get_object_or_404(Cancion, pk=pk)
    context = {
        'cancion': cancion,
        'modo_musico': True,
    }
    return render(request, 'canciones/tocar.html', context)
