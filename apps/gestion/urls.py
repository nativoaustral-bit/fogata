from django.urls import path
from . import views

app_name = 'gestion'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('usuarios/', views.usuarios_lista_view, name='usuarios_lista'),
    path('usuarios/<int:pk>/', views.usuario_detalle_view, name='usuario_detalle'),
    path('usuarios/<int:pk>/suspender/', views.usuario_suspender_view, name='usuario_suspender'),
    path('usuarios/<int:pk>/reactivar/', views.usuario_reactivar_view, name='usuario_reactivar'),
    path('usuarios/<int:pk>/enviar-reset/', views.usuario_enviar_reset_view, name='usuario_enviar_reset'),
    path('actividad/', views.actividad_lista_view, name='actividad_lista'),
    path('fogatas/', views.fogatas_metricas_view, name='fogatas_metricas'),
    path('metricas/', views.metricas_detalladas_view, name='metricas'),
    path('exportar/usuarios-csv/', views.exportar_usuarios_csv_view, name='exportar_usuarios_csv'),
]
