from django.urls import path
from . import views

app_name = 'gestion'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('usuarios/', views.usuarios_lista_view, name='usuarios_lista'),
    path('usuarios/<int:pk>/', views.usuario_detalle_view, name='usuario_detalle'),
    path('usuarios/<int:pk>/suspender/', views.usuario_suspender_view, name='usuario_suspender'),
    path('usuarios/<int:pk>/reactivar/', views.usuario_reactivar_view, name='usuario_reactivar'),
    path('usuarios/<int:pk>/eliminar/', views.usuario_eliminar_view, name='usuario_eliminar'),
    path('usuarios/<int:pk>/enviar-reset/', views.usuario_enviar_reset_view, name='usuario_enviar_reset'),
    path('usuarios/<int:pk>/cambiar-plan/', views.usuario_cambiar_plan_view, name='usuario_cambiar_plan'),
    path('actividad/', views.actividad_lista_view, name='actividad_lista'),
    path('actividad/usuario/<int:pk>/limpiar/', views.actividad_limpiar_usuario_view, name='actividad_limpiar_usuario'),
    path('actividad/limpiar-prueba/', views.actividad_limpiar_prueba_view, name='actividad_limpiar_prueba'),
    path('fogatas/', views.fogatas_metricas_view, name='fogatas_metricas'),
    path('metricas/', views.metricas_detalladas_view, name='metricas'),
    path('pagos/', views.pagos_lista_view, name='pagos_lista'),
    path('pagos/<int:pk>/eliminar/', views.pago_eliminar_sandbox_view, name='pago_eliminar_sandbox'),
    path('pagos/limpiar-sandbox/', views.pagos_limpiar_sandbox_view, name='pagos_limpiar_sandbox'),
    path('mantenimiento/', views.mantenimiento_view, name='mantenimiento'),
    path('mantenimiento/dry-run/', views.mantenimiento_dry_run_view, name='mantenimiento_dry_run'),
    path('exportar/usuarios-csv/', views.exportar_usuarios_csv_view, name='exportar_usuarios_csv'),
]
