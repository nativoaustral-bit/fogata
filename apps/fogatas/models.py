import secrets
from django.db import models
from django.utils import timezone
from django.urls import reverse
from apps.canciones.models import Cancion


def generar_token_seguro():
    """
    Genera un token criptográficamente seguro con ~192 bits de entropía
    (24 bytes codificados en base64 urlsafe producen 32 caracteres).
    Cumple con el criterio de no ser secuencial, no contener datos de usuario
    y ser prácticamente imposible de adivinar.
    """
    return secrets.token_urlsafe(24)


def fecha_expiracion_por_defecto():
    """
    Expiración por defecto: 8 horas tras su creación.
    """
    return timezone.now() + timezone.timedelta(hours=8)


class Fogata(models.Model):
    """
    Representa una sesión o setlist de canciones ordenadas para tocar en vivo.
    """
    nombre = models.CharField(
        max_length=150,
        verbose_name='Nombre de la Fogata',
        help_text='Ej: Fogata en la playa, Acústicos 90s, Ensayo viernes'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción / Contexto',
        help_text='Notas generales del repertorio o evento'
    )
    canciones = models.ManyToManyField(
        Cancion,
        through='FogataCancion',
        related_name='fogatas',
        blank=True,
        verbose_name='Canciones'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado el')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizado el')

    class Meta:
        verbose_name = 'Fogata'
        verbose_name_plural = 'Fogatas'
        ordering = ['-created_at']

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        return reverse('fogatas:detalle', args=[self.pk])

    def get_tocar_url(self):
        return reverse('fogatas:tocar_sesion', args=[self.pk])


class FogataCancion(models.Model):
    """
    Tabla intermedia explícita que asocia una Canción a una Fogata,
    preservando el orden secuencial de interpretación y notas de sesión.
    """
    fogata = models.ForeignKey(
        Fogata,
        on_delete=models.CASCADE,
        related_name='canciones_asociadas',
        verbose_name='Fogata'
    )
    cancion = models.ForeignKey(
        Cancion,
        on_delete=models.CASCADE,
        related_name='en_fogatas',
        verbose_name='Canción'
    )
    orden = models.PositiveIntegerField(
        default=1,
        verbose_name='Orden en el setlist'
    )
    nota_sesion = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Nota para esta sesión',
        help_text='Ej: Bajar un tono, solo primera estrofa, unir con siguiente'
    )

    class Meta:
        verbose_name = 'Canción en Fogata'
        verbose_name_plural = 'Canciones en Fogata'
        ordering = ['orden']
        constraints = [
            models.UniqueConstraint(
                fields=['fogata', 'cancion'],
                name='unique_fogata_cancion'
            )
        ]

    def __str__(self):
        return f"{self.orden}. {self.cancion.titulo} ({self.fogata.nombre})"


class SesionCompartida(models.Model):
    """
    Enlace temporal compartido para acceso público de invitados.
    Utiliza tokens criptográficamente seguros, revocación manual y expiración automática.
    """
    fogata = models.ForeignKey(
        Fogata,
        on_delete=models.CASCADE,
        related_name='sesiones_compartidas',
        verbose_name='Fogata'
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default=generar_token_seguro,
        verbose_name='Token de acceso'
    )
    creado_el = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado el'
    )
    expira_el = models.DateTimeField(
        default=fecha_expiracion_por_defecto,
        verbose_name='Expira el'
    )
    activa = models.BooleanField(
        default=True,
        verbose_name='Activa'
    )

    class Meta:
        verbose_name = 'Sesión Compartida'
        verbose_name_plural = 'Sesiones Compartidas'
        ordering = ['-creado_el']

    def __str__(self):
        return f"Sesión {self.token[:8]}... - {self.fogata.nombre}"

    def esta_vigente(self):
        """
        Determina si el enlace sigue siendo válido en el momento presente.
        """
        return self.activa and (timezone.now() < self.expira_el)

    def revocar(self):
        """
        Revoca inmediatamente el acceso al enlace.
        """
        self.activa = False
        self.save(update_fields=['activa'])

    def get_absolute_url(self):
        return reverse('sesion_compartida_publica', args=[self.token])
