from django.urls import path
from . import views

app_name = 'fogatas'

urlpatterns = [
    # Músico - Gestión de Fogatas
    path('', views.lista, name='lista'),
    path('nueva/', views.crear, name='crear'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    path('<int:pk>/agregar-cancion/', views.agregar_cancion, name='agregar_cancion'),
    path('<int:fogata_pk>/quitar-cancion/<int:cancion_pk>/', views.quitar_cancion, name='quitar_cancion'),
    path('<int:fogata_pk>/mover-cancion/<int:cancion_pk>/<str:direccion>/', views.mover_cancion, name='mover_cancion'),
    path('<int:pk>/tocar/', views.tocar_sesion, name='tocar_sesion'),

    # Músico - Compartir Sesión
    path('<int:pk>/compartir/', views.compartir_crear, name='compartir_crear'),
    path('<int:pk>/compartir/<int:sesion_id>/', views.compartir_exito, name='compartir_exito'),
    path('<int:pk>/compartir/<int:sesion_id>/revocar/', views.compartir_revocar, name='compartir_revocar'),

    # Invitados - Acceso por Token Seguro
    path('s/<str:token>/', views.sesion_compartida_detalle, name='sesion_compartida_detalle'),
    path('s/<str:token>/cancion/<int:cancion_id>/', views.sesion_compartida_cancion, name='sesion_compartida_cancion'),
]
