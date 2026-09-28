from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.urls import reverse_lazy
from django.contrib.auth import views as auth_views
from django.http import HttpResponseNotAllowed

from django.conf import settings
from django.utils import timezone
from .models import Invitacion, PerfilPiloto
from .forms import RegistroForm, LoginForm
from .planes import obtener_estado_capacidad
from apps.canciones.models import Cancion
from apps.fogatas.models import Fogata
from apps.gestion.services import registrar_evento



def home(request):
    """
    Pantalla principal de Fogata:
    - Si el usuario es anónimo: Muestra la Landing pública sobria.
    - Si el usuario está autenticado: Muestra su repertorio privado (canciones y Fogatas propias)
      o el estado de bienvenida si su repertorio está vacío.
    """
    if not request.user.is_authenticated:
        return render(request, 'core/landing.html')

    # Filtrar estrictamente por propietario (Criterio 11)
    canciones_usuario = Cancion.objects.filter(propietario=request.user)
    fogatas_usuario = Fogata.objects.filter(propietario=request.user)

    total_canciones = canciones_usuario.count()
    total_fogatas = fogatas_usuario.count()
    ultimas_canciones = canciones_usuario.order_by('-created_at')[:5]
    ultimas_fogatas = fogatas_usuario.order_by('-created_at')[:5]

    context = {
        'total_canciones': total_canciones,
        'total_fogatas': total_fogatas,
        'ultimas_canciones': ultimas_canciones,
        'ultimas_fogatas': ultimas_fogatas,
    }
    return render(request, 'core/home.html', context)


def registro_view(request):
    """
    Registro por invitación para el piloto multiusuario de Fogata.
    Valida código de invitación con protección de concurrencia y crea cuenta
    con correo electrónico normalizado como identificador.
    """
    if request.user.is_authenticated:
        return redirect('core:home')

    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            codigo = form.cleaned_data['codigo_invitacion']
            email = form.cleaned_data['email']
            nombre = form.cleaned_data['nombre']
            password = form.cleaned_data['password']

            try:
                from django.db import transaction
                from .models import PerfilPiloto

                with transaction.atomic():
                    # Consumo atómico con select_for_update (Criterio 4)
                    Invitacion.consumir_codigo(codigo)

                    # Crear usuario con username y email idénticos
                    user = User.objects.create_user(
                        username=email,
                        email=email,
                        password=password,
                        first_name=nombre
                    )
                    PerfilPiloto.objects.create(
                        user=user,
                        codigo_invitacion=codigo,
                        tipo_cuenta='GRATIS'
                    )
                    registrar_evento(usuario=user, tipo_evento='registro', objeto_tipo='usuario', objeto_id=user.id)

                # Iniciar sesión automáticamente
                auth_login(request, user, backend='apps.core.backends.EmailAuthBackend')
                registrar_evento(usuario=user, tipo_evento='login', objeto_tipo='usuario', objeto_id=user.id)
                messages.success(request, f"¡Bienvenido a Fogata, {user.first_name}!")
                return redirect('core:home')
            except ValueError as e:
                form.add_error('codigo_invitacion', str(e))
    else:
        # Soporta precarga desde query string ?codigo=ABC123 sin confiar ciegamente en él
        codigo_inicial = request.GET.get('codigo', '').strip().upper()
        initial_data = {}
        if codigo_inicial:
            initial_data['codigo_invitacion'] = codigo_inicial
        form = RegistroForm(initial=initial_data)

    return render(request, 'core/registro.html', {'form': form})


def login_view(request):
    """
    Inicio de sesión con correo electrónico y contraseña.
    """
    if request.user.is_authenticated:
        return redirect('core:home')

    next_url = request.GET.get('next', '')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user, backend='apps.core.backends.EmailAuthBackend')
            registrar_evento(usuario=user, tipo_evento='login', objeto_tipo='usuario', objeto_id=user.id)
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect('core:home')
    else:
        form = LoginForm()

    context = {
        'form': form,
        'next': next_url,
    }
    return render(request, 'core/login.html', context)


def logout_view(request):
    """
    Cierre de sesión seguro.
    Criterio 13: Mantener logout exclusivamente mediante POST. GET no debe cerrar sesión.
    """
    if request.method == 'POST':
        auth_logout(request)
        messages.info(request, "Has cerrado tu sesión en Fogata.")
        return redirect('core:home')
    # Si intentan acceder por GET, se rechaza o redirige sin cerrar sesión
    return HttpResponseNotAllowed(['POST'], "El cierre de sesión solo está permitido mediante POST.")


# ==========================================
# Recuperación de Contraseña (Flujo Ciego)
# ==========================================

class FogataPasswordResetView(auth_views.PasswordResetView):
    template_name = 'core/password_reset.html'
    email_template_name = 'core/password_reset_email.html'
    subject_template_name = 'core/password_reset_subject.txt'
    success_url = reverse_lazy('core:password_reset_done')


class FogataPasswordResetDoneView(auth_views.PasswordResetDoneView):
    """
    Criterio 17: Respuesta ciega idéntica para correos existentes o inexistentes.
    """
    template_name = 'core/password_reset_done.html'


class FogataPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'core/password_reset_confirm.html'
    success_url = reverse_lazy('core:password_reset_complete')


class FogataPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = 'core/password_reset_complete.html'


# ==========================================
# Endpoints Técnicos PWA y Manifest
# ==========================================

def manifest_view(request):
    """
    Entrega el Web App Manifest PWA con scope raíz e identidad estable (Fase 5).
    """
    from django.http import JsonResponse
    manifest_data = {
        "id": "/",
        "name": "Fogata",
        "short_name": "Fogata",
        "description": "Repertorio y atril digital de acordes para guitarra",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#0d0d0d",
        "theme_color": "#0d0d0d",
        "icons": [
            {
                "src": "/static/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/static/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/static/icons/icon.svg",
                "sizes": "any",
                "type": "image/svg+xml"
            }
        ]
    }
    response = JsonResponse(manifest_data)
    response['Content-Type'] = 'application/manifest+json'
    return response


def service_worker_view(request):
    """
    Sirve el Service Worker desde la raíz con cabecera Service-Worker-Allowed: /
    """
    import os
    from django.conf import settings
    from django.http import HttpResponse

    sw_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'sw.js')
    if os.path.exists(sw_path):
        with open(sw_path, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = "// Fogata Service Worker placeholder"

    response = HttpResponse(content, content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


def offline_view(request):
    """
    Pantalla informativa de estado offline.
    En la Fase 6 (Piloto Multiusuario), se suspende el almacenamiento privado
    en CacheStorage para garantizar aislamiento absoluto entre usuarios.
    """
    return render(request, 'core/offline.html')


def pro_view(request):
    """
    Landing interna de Fogata Pro (Fase 8).
    Exhibe comparativa Freemium, capacidad y precios referenciales sin medios de pago reales.
    Emite evento comercial 'ver_pro' con debounce de 15 minutos en sesión.
    """
    origen = request.GET.get('origen', 'directo')
    clave_sesion = 'ultima_visita_pro'
    ultima_visita = request.session.get(clave_sesion)
    ahora_ts = timezone.now().timestamp()
    if not ultima_visita or (ahora_ts - float(ultima_visita)) >= 900:
        registrar_evento(
            usuario=request.user if request.user.is_authenticated else None,
            tipo_evento='ver_pro',
            metadata={'origen': origen[:50]}
        )
        request.session[clave_sesion] = ahora_ts

    estado_capacidad = obtener_estado_capacidad(request.user) if request.user.is_authenticated else None

    precio_sem = getattr(settings, 'FOGATA_PRO_SEMESTRAL_PRICE_CLP', 5990)
    precio_anu = getattr(settings, 'FOGATA_PRO_ANUAL_PRICE_CLP', 9990)

    context = {
        'precio_semestral': f"{precio_sem:,}".replace(",", "."),
        'precio_anual': f"{precio_anu:,}".replace(",", "."),
        'max_canciones_gratis': getattr(settings, 'FOGATA_FREE_MAX_SONGS', 10),
        'max_fogatas_gratis': getattr(settings, 'FOGATA_FREE_MAX_FOGATAS', 1),
        'capacidad': estado_capacidad,
        'origen': origen,
    }
    return render(request, 'core/pro.html', context)

