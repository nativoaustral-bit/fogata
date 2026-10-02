from django.conf import settings
from django.db import models
from django.utils import timezone


class EventoUso(models.Model):
    """
    Modelo liviano de eventos de comportamiento de producto.
    Registra exclusivamente acciones operativas sin contenido privado (sin letras ni acordes).
    """
    TIPOS_EVENTO = [
        ('registro', 'Registro de cuenta'),
        ('login', 'Inicio de sesión'),
        ('crear_cancion', 'Creación de canción'),
        ('editar_cancion', 'Edición de canción'),
        ('tocar_cancion', 'Uso de Modo Tocar (Canción en atril)'),
        ('crear_fogata', 'Creación de Fogata'),
        ('editar_fogata', 'Edición de Fogata'),
        ('tocar_fogata', 'Uso de Modo Tocar (Fogata en atril)'),
        ('crear_sesion_compartida', 'Creación de sesión compartida'),
        ('abrir_sesion_compartida', 'Apertura de sesión compartida por invitado'),
        ('ver_pro', 'Visualización de página Fogata Pro'),
        ('alcanzar_limite_canciones', 'Intento de creación sobre límite de canciones'),
        ('alcanzar_limite_fogatas', 'Intento de creación sobre límite de Fogatas'),
        ('iniciar_pago', 'Inicio de checkout Flow'),
        ('pago_confirmado', 'Confirmación de pago aprobado Flow'),
        ('pago_rechazado', 'Notificación de pago rechazado Flow'),
        ('upgrade_pro', 'Primera activación de Fogata Pro'),
        ('renovacion_pro', 'Renovación de vigencia Fogata Pro'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_uso',
        db_index=True,
        verbose_name='Usuario'
    )
    tipo_evento = models.CharField(
        max_length=40,
        choices=TIPOS_EVENTO,
        db_index=True,
        verbose_name='Tipo de evento'
    )
    fecha = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name='Fecha y hora'
    )
    objeto_tipo = models.CharField(
        max_length=40,
        blank=True,
        db_index=True,
        verbose_name='Tipo de objeto'
    )
    objeto_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='ID del objeto'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadatos mínimos'
    )

    class Meta:
        verbose_name = 'Evento de Uso'
        verbose_name_plural = 'Eventos de Uso'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['tipo_evento', 'fecha']),
            models.Index(fields=['usuario', 'fecha']),
            models.Index(fields=['usuario', 'tipo_evento']),
        ]

    def __str__(self):
        usr = self.usuario.email if self.usuario else "Invitado/Público"
        return f"[{self.fecha.strftime('%Y-%m-%d %H:%M')}] {usr} -> {self.tipo_evento}"


class AuditoriaAdmin(models.Model):
    """
    Registro inmutable de auditoría para acciones sensibles ejecutadas desde Control Center.
    usuario_afectado utiliza on_delete=PROTECT para garantizar que la auditoría no se pierda.
    """
    ACCIONES = [
        ('suspender_usuario', 'Suspensión de cuenta'),
        ('reactivar_usuario', 'Reactivación de cuenta'),
        ('enviar_reset_password', 'Envío de recuperación de contraseña'),
        ('cambiar_plan', 'Cambio manual de plan'),
    ]

    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='auditorias_admin_ejecutadas',
        verbose_name='Administrador'
    )
    usuario_afectado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='auditorias_admin_recibidas',
        verbose_name='Usuario afectado'
    )
    accion = models.CharField(
        max_length=40,
        choices=ACCIONES,
        verbose_name='Acción'
    )
    fecha = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name='Fecha y hora'
    )
    detalles = models.TextField(
        blank=True,
        verbose_name='Detalles / Motivo'
    )

    class Meta:
        verbose_name = 'Auditoría Administrativa'
        verbose_name_plural = 'Auditorías Administrativas'
        ordering = ['-fecha']

    def __str__(self):
        admin_email = self.admin.email if self.admin else "Sistema"
        return f"{self.fecha.strftime('%Y-%m-%d %H:%M')} | {admin_email} -> {self.accion} sobre {self.usuario_afectado.email}"
