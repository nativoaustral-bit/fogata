from django.db import models, transaction
from django.utils import timezone


class Invitacion(models.Model):
    """
    Control de acceso por invitación para el piloto multiusuario de Fogata.
    Soporta códigos únicos, expiración temporal y límite de usos con protección concurrente.
    """
    codigo = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        verbose_name='Código de invitación',
        help_text='Código alfanumérico en mayúsculas (ej: HUMM2026, PILOTO-VALPO)'
    )
    descripcion = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Descripción / Destinatario',
        help_text='Contexto o grupo del piloto asignado a esta invitación'
    )
    activa = models.BooleanField(
        default=True,
        verbose_name='Activa'
    )
    max_usos = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Límite de usos',
        help_text='Dejar vacío para usos ilimitados (código general de control)'
    )
    usos_actuales = models.PositiveIntegerField(
        default=0,
        verbose_name='Usos registrados'
    )
    creada_el = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creada el'
    )
    expira_el = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Expira el',
        help_text='Fecha y hora límite de validez. Dejar vacío si no expira.'
    )

    class Meta:
        verbose_name = 'Invitación'
        verbose_name_plural = 'Invitaciones'
        ordering = ['-creada_el']

    def __str__(self):
        usos_txt = f"{self.usos_actuales}/{self.max_usos}" if self.max_usos is not None else f"{self.usos_actuales}/∞"
        return f"{self.codigo} ({usos_txt})"

    def save(self, *args, **kwargs):
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        super().save(*args, **kwargs)

    def esta_vigente(self):
        """
        Determina si la invitación puede seguir siendo utilizada en este instante.
        """
        if not self.activa:
            return False
        if self.expira_el and timezone.now() >= self.expira_el:
            return False
        if self.max_usos is not None and self.usos_actuales >= self.max_usos:
            return False
        return True

    @classmethod
    def consumir_codigo(cls, codigo_raw):
        """
        Valida y consume atómicamente un uso de la invitación.
        Utiliza un UPDATE condicional a nivel de base de datos (Q + F expression)
        para garantizar concurrencia atómica estricta tanto en SQLite como en PostgreSQL.
        Retorna la instancia si fue consumida exitosamente, o lanza ValueError con el motivo.
        """
        if not codigo_raw:
            raise ValueError("Debes ingresar un código de invitación.")

        codigo_limpio = codigo_raw.strip().upper()

        with transaction.atomic():
            try:
                inv = cls.objects.get(codigo=codigo_limpio)
            except cls.DoesNotExist:
                raise ValueError("El código de invitación ingresado no existe.")

            if not inv.activa:
                raise ValueError("Este código de invitación está desactivado.")

            if inv.expira_el and timezone.now() >= inv.expira_el:
                raise ValueError("Este código de invitación ha expirado.")

            if inv.max_usos is not None and inv.usos_actuales >= inv.max_usos:
                raise ValueError("Este código de invitación ha agotado todos sus cupos disponibles.")

            # Operación atómica condicional a nivel de SQL (garantía de concurrencia)
            ahora = timezone.now()
            filtro = (
                models.Q(id=inv.id, activa=True) &
                (models.Q(expira_el__isnull=True) | models.Q(expira_el__gt=ahora)) &
                (models.Q(max_usos__isnull=True) | models.Q(usos_actuales__lt=models.F('max_usos')))
            )
            filas_actualizadas = cls.objects.filter(filtro).update(usos_actuales=models.F('usos_actuales') + 1)
            if filas_actualizadas == 0:
                raise ValueError("Este código de invitación ha agotado todos sus cupos disponibles.")

            inv.refresh_from_db()
            if inv.max_usos is not None and inv.usos_actuales >= inv.max_usos:
                cls.objects.filter(id=inv.id, usos_actuales__gte=models.F('max_usos')).update(activa=False)
                inv.activa = False

            return inv


class PerfilPiloto(models.Model):
    """
    Metadatos del piloto para auditoría en Django Admin.
    Asocia al usuario con el código de invitación que utilizó al registrarse.
    """
    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='perfil_piloto',
        verbose_name='Usuario'
    )
    codigo_invitacion = models.CharField(
        max_length=32,
        blank=True,
        verbose_name='Código de invitación utilizado'
    )
    registrado_el = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Registrado el'
    )

    class Meta:
        verbose_name = 'Perfil de Piloto'
        verbose_name_plural = 'Perfiles de Piloto'

    def __str__(self):
        return f"{self.user.email} [{self.codigo_invitacion or 'Directo'}]"
