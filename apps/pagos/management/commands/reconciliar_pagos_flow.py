"""
Comando de gestión para reconciliar órdenes de pago pendientes en Flow.
Ejecutable manualmente o programable mediante Cron en HostGator.
Recupera callbacks perdidos, medios de pago asíncronos y fallos temporales de red.
"""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.pagos.models import OrdenPago
from apps.pagos.services import procesar_confirmacion_flow


class Command(BaseCommand):
    help = "Revisa órdenes pendientes y consulta su estado oficial en Flow."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=7,
            help='Número de días hacia atrás a revisar para órdenes pendientes (por defecto: 7)'
        )

    def handle(self, *args, **options):
        dias = options['dias']
        limite = timezone.now() - timedelta(days=dias)

        ordenes_pendientes = OrdenPago.objects.filter(
            estado=OrdenPago.ESTADO_PENDIENTE,
            flow_token__isnull=False,
            creada_el__gte=limite
        ).order_by('creada_el')

        total = ordenes_pendientes.count()
        self.stdout.write(f"Iniciando reconciliación de {total} órdenes pendientes (últimos {dias} días)...")

        pagadas = 0
        rechazadas = 0
        anuladas = 0
        siguen_pendientes = 0
        errores = 0

        for orden in ordenes_pendientes:
            token = orden.flow_token
            try:
                orden_actualizada = procesar_confirmacion_flow(token)
                if orden_actualizada.estado == OrdenPago.ESTADO_PAGADA:
                    pagadas += 1
                    self.stdout.write(self.style.SUCCESS(f"[PAGADA] Orden {orden.commerce_order} confirmada y activada."))
                elif orden_actualizada.estado == OrdenPago.ESTADO_RECHAZADA:
                    rechazadas += 1
                    self.stdout.write(self.style.WARNING(f"[RECHAZADA] Orden {orden.commerce_order} rechazada por medio de pago."))
                elif orden_actualizada.estado == OrdenPago.ESTADO_ANULADA:
                    anuladas += 1
                    self.stdout.write(self.style.NOTICE(f"[ANULADA] Orden {orden.commerce_order} anulada o cancelada."))
                elif orden_actualizada.estado == OrdenPago.ESTADO_PENDIENTE:
                    siguen_pendientes += 1
                else:
                    errores += 1
                    self.stdout.write(self.style.ERROR(f"[ERROR] Orden {orden.commerce_order} en estado {orden_actualizada.estado}."))
            except Exception as e:
                errores += 1
                self.stdout.write(self.style.ERROR(f"Error al reconciliar {orden.commerce_order}: {str(e)}"))

        resumen = (
            f"Reconciliación completada: {total} procesadas. "
            f"Pagadas: {pagadas}, Rechazadas: {rechazadas}, Anuladas: {anuladas}, "
            f"Pendientes: {siguen_pendientes}, Errores/Excepciones: {errores}."
        )
        self.stdout.write(self.style.SUCCESS(resumen))
