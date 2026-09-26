from django.shortcuts import render
from apps.canciones.models import Cancion
from apps.fogatas.models import Fogata


def home(request):
    """
    Pantalla de inicio minimalista de Fogata.
    Muestra accesos directos principales y conteos rápidos.
    """
    total_canciones = Cancion.objects.count()
    total_fogatas = Fogata.objects.count()
    ultimas_canciones = Cancion.objects.order_by('-created_at')[:5]
    ultimas_fogatas = Fogata.objects.order_by('-created_at')[:5]

    context = {
        'total_canciones': total_canciones,
        'total_fogatas': total_fogatas,
        'ultimas_canciones': ultimas_canciones,
        'ultimas_fogatas': ultimas_fogatas,
    }
    return render(request, 'core/home.html', context)
