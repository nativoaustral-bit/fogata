from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Invitacion


class RegistroForm(forms.Form):
    """
    Formulario minimalista de registro para el piloto multiusuario de Fogata.
    Pide únicamente: Nombre, Correo electrónico, Contraseña y Código de invitación.
    """
    nombre = forms.CharField(
        max_length=60,
        required=True,
        label='Nombre',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Tu nombre o apodo',
            'autocomplete': 'name',
            'autofocus': 'autofocus'
        })
    )
    email = forms.EmailField(
        max_length=150,
        required=True,
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'tunombre@ejemplo.cl',
            'autocomplete': 'email'
        })
    )
    codigo_invitacion = forms.CharField(
        max_length=32,
        required=True,
        label='Código de invitación',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: HUMM2026',
            'style': 'text-transform: uppercase;'
        })
    )
    password = forms.CharField(
        label='Contraseña',
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Mínimo 8 caracteres',
            'autocomplete': 'new-password'
        })
    )
    password_confirm = forms.CharField(
        label='Confirmar contraseña',
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Repite tu contraseña',
            'autocomplete': 'new-password'
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise ValidationError("El correo electrónico es obligatorio.")
        if len(email) > 150:
            raise ValidationError("El correo electrónico no puede superar los 150 caracteres.")
        # Validación de unicidad usando username normalizado
        if User.objects.filter(username=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Ya existe una cuenta registrada con este correo electrónico.")
        return email

    def clean_codigo_invitacion(self):
        codigo = self.cleaned_data.get('codigo_invitacion', '').strip().upper()
        if not codigo:
            raise ValidationError("El código de invitación es obligatorio.")

        try:
            inv = Invitacion.objects.get(codigo=codigo)
        except Invitacion.DoesNotExist:
            raise ValidationError("El código de invitación no existe.")

        if not inv.activa:
            raise ValidationError("Este código de invitación está desactivado.")

        if inv.expira_el and timezone.now() >= inv.expira_el:
            raise ValidationError("Este código de invitación ha expirado.")

        if inv.max_usos is not None and inv.usos_actuales >= inv.max_usos:
            raise ValidationError("Este código de invitación ha agotado todos sus cupos disponibles.")

        return codigo

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')

        if p1 and p2:
            if p1 != p2:
                self.add_error('password_confirm', "Las contraseñas no coinciden.")
            else:
                try:
                    validate_password(p1)
                except ValidationError as e:
                    self.add_error('password', e)

        return cleaned_data


class LoginForm(forms.Form):
    """
    Formulario de inicio de sesión de Fogata.
    Presenta al usuario: Correo electrónico + Contraseña.
    Internamente normaliza a minúsculas y valida credenciales.
    """
    email = forms.EmailField(
        label='Correo electrónico',
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'tunombre@ejemplo.cl',
            'autocomplete': 'email',
            'autofocus': 'autofocus'
        })
    )
    password = forms.CharField(
        label='Contraseña',
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Tu contraseña',
            'autocomplete': 'current-password'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email', '').strip().lower()
        password = cleaned_data.get('password')

        if email and password:
            # Autenticar usando el username normalizado (que coincide con el email)
            self.user_cache = authenticate(username=email, password=password)
            if self.user_cache is None:
                # Fallback por si acaso fue creado con email distinto a username
                try:
                    u = User.objects.get(email__iexact=email)
                    self.user_cache = authenticate(username=u.username, password=password)
                except (User.DoesNotExist, User.MultipleObjectsReturned):
                    self.user_cache = None

            if self.user_cache is None:
                raise ValidationError("Correo o contraseña incorrectos. Verifica tus datos e intenta nuevamente.")
            elif not self.user_cache.is_active:
                raise ValidationError("Esta cuenta está desactivada.")

        return cleaned_data

    def get_user(self):
        return getattr(self, 'user_cache', None)
