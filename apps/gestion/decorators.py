from functools import wraps
from django.shortcuts import render, redirect
from django.conf import settings
from django.urls import reverse
from django.http import HttpResponseForbidden


def staff_required(view_func):
    """
    Decorador estricto para rutas de Fogata Control Center (/gestion/).
    - Si el usuario es anónimo: Redirige a login preservando next.
    - Si el usuario está autenticado pero no es staff: Retorna HTTP 403 Forbidden
      con plantilla sobria informativa (nunca redirige silenciosamente al home).
    - Si es staff: Permite acceso a la administración.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_url = reverse(settings.LOGIN_URL)
            return redirect(f"{login_url}?next={request.path}")

        if not request.user.is_staff:
            response = render(request, 'gestion/403.html', status=403)
            return HttpResponseForbidden(response.content)

        return view_func(request, *args, **kwargs)

    return _wrapped_view
