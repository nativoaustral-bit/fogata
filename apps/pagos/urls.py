from django.urls import path
from . import views

app_name = 'pagos'

urlpatterns = [
    # Inicio de checkout
    path('crear/', views.crear_pago_view, name='crear_pago'),

    # Endpoints Flow
    path('flow/confirmacion/', views.flow_confirmacion_view, name='flow_confirmacion'),
    path('flow/retorno/', views.flow_retorno_view, name='flow_retorno'),

    # Resultado amigable recargable para usuario
    path('resultado/<str:commerce_order>/', views.resultado_pago_view, name='resultado'),

    # Historial y estado de cuenta
    path('cuenta/', views.mi_cuenta_view, name='mi_cuenta'),
]
