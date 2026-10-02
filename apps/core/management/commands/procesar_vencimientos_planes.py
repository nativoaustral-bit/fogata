"""
Comando de gestión para procesar expiración de planes Fogata Pro.
Degrada formalmente en base de datos las cuentas cuya fecha_fin_plan ya venció.
Aplica downgrade no destructivo (sin borrar contenido existente).
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.core.models import PerfilPiloto


class Command(BaseCommand):
    help = "Actualiza registros de cuentas Pro expiradas a Gratis (Downgrade no destructivo)."

    def handle(self, *args, **options):
        ahora = timezone.now()

        # Cuentas con tipo PRO cuya fecha_fin_plan sea menor o igual a ahora
        perfiles_vencidos = PerfilPiloto.objects.filter(
            tipo_cuenta='PRO',
            fecha_fin_plan__isnull=False,
            fecha_fin_plan__lte=ahora
        )

        total = perfiles_vencidos.count()
        self.stdout.write(f"Procesando vencimientos de planes Pro ({total} cuentas detectadas)...")

        actualizados = 0
        for perfil in perfiles_vencidos:
            email = perfil.user.email
            fin = perfil.fecha_fin_plan.strftime('%d/%m/%Y %H:%M')
            perfil.tipo_cuenta = 'GRATIS'
            perfil.estado_suscripcion = 'VENCIDA'
            perfil.save(update_fields=['tipo_cuenta', 'estado_suscripcion'])
            actualizados += 1
            self.stdout.write(f"Cuenta {email} degradada a GRATIS (venció el {fin}).")

        self.stdout.write(
            self.style.SUCCESS(f"Proceso finalizado. Total de cuentas actualizadas: {actualizados}.")
        )
