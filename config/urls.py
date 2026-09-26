"""
URL configuration for Fogata MVP (Fase 0).
"""

from django.contrib import admin
from django.urls import path, include
from apps.fogatas import views as fogatas_views

urlpatterns = [
    # Módulos principales
    path('', include('apps.core.urls')),
    path('canciones/', include('apps.canciones.urls')),
    path('fogatas/', include('apps.fogatas.urls')),

    # Rutas públicas directas para Modo Invitado (Sesiones Compartidas)
    path('s/<str:token>/', fogatas_views.sesion_compartida_detalle, name='sesion_compartida_publica'),
    path('s/<str:token>/cancion/<int:cancion_id>/', fogatas_views.sesion_compartida_cancion, name='sesion_compartida_cancion_publica'),

    # Panel de administración Django
    path('admin/', admin.site.urls),
]
