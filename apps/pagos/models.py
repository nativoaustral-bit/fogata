from django.db import models
from django.conf import settings
from django.utils import timezone


class OrdenPago(models.Model):
    """
    Modelo transaccional y contable para compras de planes Fogata Pro.
    Garantiza unicidad de órdenes de comercio, control de ambiente y bandera
    atómica de idempotencia (pro_aplicado) compatible con SQLite y PostgreSQL.
    """
    PLAN_PRO_6M = 'PRO_6M'
    PLAN_PRO_12M = 'PRO_12M'
    PLAN_CHOICES = [
        (PLAN_PRO_6M, 'Fogata Pro Semestral (6 meses)'),
        (PLAN_PRO_12M, 'Fogata Pro Anual (12 meses)'),
    ]

    ESTADO_CREADA = 'CREADA'
    ESTADO_PENDIENTE = 'PENDIENTE'
    ESTADO_PAGADA = 'PAGADA'
    ESTADO_RECHAZADA = 'RECHAZADA'
    ESTADO_ANULADA = 'ANULADA'
    ESTADO_ERROR_TECNICO = 'ERROR_TECNICO'
    ESTADO_ERROR_VALIDACION = 'ERROR_VALIDACION'
    ESTADO_CHOICES = [
        (ESTADO_CREADA, 'Creada localmente'),
        (ESTADO_PENDIENTE, 'En espera de pago (Checkout Flow)'),
        (ESTADO_PAGADA, 'Pagada y confirmada'),
        (ESTADO_RECHAZADA, 'Rechazada por medio de pago'),
        (ESTADO_ANULADA, 'Anulada o expirada por usuario'),
        (ESTADO_ERROR_TECNICO, 'Error de conectividad transitorio'),
        (ESTADO_ERROR_VALIDACION, 'Discrepancia en monto/moneda/orden'),
    ]

    AMBIENTE_SANDBOX = 'SANDBOX'
    AMBIENTE_PRODUCTION = 'PRODUCTION'
    AMBIENTE_CHOICES = [
        (AMBIENTE_SANDBOX, 'Sandbox (Pruebas)'),
        (AMBIENTE_PRODUCTION, 'Producción (Real)'),
    ]

    # Relación protegida para preservar el historial financiero del usuario
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='ordenes_pago',
        verbose_name='Usuario'
    )

    # Identificadores de orden
    commerce_order = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name='Orden de Comercio (Fogata)'
    )
    flow_order = models.BigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Orden oficial Flow'
    )
    flow_token = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        verbose_name='Token de sesión Flow'
    )
    checkout_request_id = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        verbose_name='ID de solicitud de checkout (Prevención doble submit)'
    )

    # Ambiente de ejecución registrado al momento de creación
    ambiente = models.CharField(
        max_length=20,
        choices=AMBIENTE_CHOICES,
        default=AMBIENTE_SANDBOX,
        db_index=True,
        verbose_name='Ambiente'
    )

    # Parámetros comerciales (determinados exclusivamente por el servidor)
    plan = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        verbose_name='Plan contratado'
    )
    monto = models.PositiveIntegerField(
        verbose_name='Monto en CLP'
    )
    moneda = models.CharField(
        max_length=5,
        default='CLP',
        verbose_name='Moneda'
    )

    # Máquina de estados
    estado = models.CharField(
        max_length=25,
        choices=ESTADO_CHOICES,
        default=ESTADO_CREADA,
        db_index=True,
        verbose_name='Estado'
    )

    # Bandera atómica de idempotencia estricta para SQLite
    pro_aplicado = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Beneficio Pro aplicado'
    )

    # Marcas temporales
    creada_el = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Creada el'
    )
    actualizada_el = models.DateTimeField(
        auto_now=True,
        verbose_name='Actualizada el'
    )
    pagada_el = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Pagada el'
    )

    # Vigencia asignada por esta orden específica
    fecha_inicio_plan = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha inicio del período'
    )
    fecha_fin_plan = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha fin del período'
    )

    # Diagnóstico técnico y auditoría interna (sin secretos ni datos bancarios)
    detalles_error = models.TextField(
        blank=True,
        verbose_name='Detalles técnicos / Discrepancias'
    )
    # Whitelist estricta de metadatos devueltos por Flow (NUNCA raw response, ni payer, ni paymentData completo)
    flow_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadatos técnicos sanitizados de Flow'
    )

    class Meta:
        verbose_name = 'Orden de Pago'
        verbose_name_plural = 'Órdenes de Pago'
        ordering = ['-creada_el']
        indexes = [
            models.Index(fields=['usuario', 'estado']),
            models.Index(fields=['ambiente', 'estado']),
            models.Index(fields=['estado', 'creada_el']),
        ]

    def __str__(self):
        return f"{self.commerce_order} [{self.plan} - ${self.monto} {self.moneda}] ({self.estado})"

    @property
    def es_pagada(self) -> bool:
        return self.estado == self.ESTADO_PAGADA

    @property
    def es_sandbox(self) -> bool:
        return self.ambiente == self.AMBIENTE_SANDBOX

    @property
    def plan_nombre_legible(self) -> str:
        for p, label in self.PLAN_CHOICES:
            if p == self.plan:
                return label
        return self.plan

    @property
    def monto_formateado(self) -> str:
        return f"{self.monto:,}".replace(",", ".")
