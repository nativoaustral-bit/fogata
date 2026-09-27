from django.urls import path
from . import views

app_name = 'canciones'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nueva/', views.crear, name='crear'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    path('<int:pk>/tocar/', views.tocar, name='tocar'),
    path('<int:pk>/acordes/', views.editar_acordes, name='editar_acordes'),
    path('<int:pk>/acordes/guardar/', views.guardar_edicion_acorde, name='guardar_edicion_acorde'),
    path('diagramas/batch/', views.diagramas_batch, name='diagramas_batch'),
    path('diagrama/', views.ver_diagrama, name='ver_diagrama'),
]


