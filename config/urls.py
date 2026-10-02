"""
URL configuration for Fogata MVP (Fase 0).
"""

from django.contrib import admin
from django.urls import path, include
from apps.fogatas import views as fogatas_views
from apps.core import views as core_views
from apps.pagos import views as pagos_views

urlpatterns = [
    # PWA canónicas en la raíz (Fase 5)
    path('manifest.webmanifest', core_views.manifest_view, name='manifest'),
    path('sw.js', core_views.service_worker_view, name='service_worker'),
    path('offline/', core_views.offline_view, name='offline'),

    # Módulos principales
    path('', include('apps.core.urls')),
    path('login/', core_views.login_view, name='login'),
    path('logout/', core_views.logout_view, name='logout'),
    path('registro/', core_views.registro_view, name='registro'),
    path('recuperar-password/', core_views.FogataPasswordResetView.as_view(), name='password_reset'),
    path('recuperar-password/enviado/', core_views.FogataPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('canciones/', include('apps.canciones.urls')),
    path('fogatas/', include('apps.fogatas.urls')),
    path('pro/', core_views.pro_view, name='pro'),
    path('pagos/', include('apps.pagos.urls')),
    path('cuenta/', pagos_views.mi_cuenta_view, name='mi_cuenta'),

    # Rutas públicas directas para Modo Invitado (Sesiones Compartidas)
    path('s/<str:token>/', fogatas_views.sesion_compartida_detalle, name='sesion_compartida_publica'),
    path('s/<str:token>/cancion/<int:cancion_id>/', fogatas_views.sesion_compartida_cancion, name='sesion_compartida_cancion_publica'),

    # Panel de administración Django
    path('admin/', admin.site.urls),

    # Fogata Control Center (Fase 7)
    path('gestion/', include('apps.gestion.urls')),
]
