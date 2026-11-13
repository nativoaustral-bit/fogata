from django.urls import path
from . import views

app_name = 'entrenamiento'

urlpatterns = [
    path('', views.portada_entrenamiento, name='portada'),
    path('notas/', views.entrenar_notas_view, name='notas'),
    path('acordes/', views.entrenar_acordes_view, name='acordes'),
    path('progresiones/', views.entrenar_progresiones_view, name='progresiones'),
    path('api/evento/', views.registrar_evento_api, name='api_evento'),
]

