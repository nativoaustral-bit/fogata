from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailAuthBackend(ModelBackend):
    """
    Backend de autenticación que permite iniciar sesión utilizando
    el correo electrónico insensible a mayúsculas/minúsculas.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = kwargs.get('email', username)
        if not email or not password:
            return None

        email_limpio = email.strip().lower()

        try:
            # Buscar por username normalizado o por email
            user = User.objects.filter(username=email_limpio).first()
            if not user:
                user = User.objects.filter(email__iexact=email_limpio).first()

            if user and user.check_password(password) and self.user_can_authenticate(user):
                return user
        except Exception:
            return None

        return None
