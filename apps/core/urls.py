from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('registro/', views.registro_view, name='registro'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Recuperación de contraseña (Criterio 17)
    path('recuperar-password/', views.FogataPasswordResetView.as_view(), name='password_reset'),
    path('recuperar-password/enviado/', views.FogataPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('recuperar-password/<uidb64>/<token>/', views.FogataPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('recuperar-password/completado/', views.FogataPasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # Offline informativo
    path('offline/', views.offline_view, name='offline'),

    # Fogata Pro (Fase 8)
    path('pro/', views.pro_view, name='pro'),
]
