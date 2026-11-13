from django.conf import settings
from django.db import models
from django.utils import timezone


class SesionEntrenamiento(models.Model):
    """
    Registro liviano de sesión de entrenamiento auditivo.
    Permite persistir sesiones de 5 ejercicios para usuarios autenticados,
    distinguiendo entre ejercicios completados y aciertos declarados voluntariamente.
    """
    MODALIDADES = [
        ('notas', 'Notas'),
        ('acordes', 'Acordes'),
        ('progresiones', 'Progresiones'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sesiones_entrenamiento',
        verbose_name='Usuario'
    )
    modalidad = models.CharField(
        max_length=20,
        choices=MODALIDADES,
        db_index=True,
        verbose_name='Modalidad'
    )
    total_ejercicios = models.PositiveSmallIntegerField(
        default=5,
        verbose_name='Total de ejercicios'
    )
    ejercicios_completados = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Ejercicios completados'
    )
    aciertos_declarados = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Aciertos declarados voluntariamente'
    )
    completada = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Sesión completada'
    )
    iniciada_el = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name='Iniciada el'
    )
    finalizada_el = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Finalizada el'
    )

    class Meta:
        verbose_name = 'Sesión de Entrenamiento'
        verbose_name_plural = 'Sesiones de Entrenamiento'
        ordering = ['-iniciada_el']
        indexes = [
            models.Index(fields=['usuario', 'modalidad', '-iniciada_el']),
            models.Index(fields=['usuario', 'completada']),
        ]

    def __str__(self):
        estado = "Completada" if self.completada else f"{self.ejercicios_completados}/{self.total_ejercicios}"
        return f"Sesión {self.modalidad} ({estado}) - {self.usuario.email}"

