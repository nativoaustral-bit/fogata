from django.core.management.base import BaseCommand
from apps.core.models import Invitacion


class Command(BaseCommand):
    help = "Crea un código de invitación para el piloto multiusuario de Fogata."

    def add_arguments(self, parser):
        parser.add_argument('--codigo', type=str, required=True, help="Código de invitación (ej: PILOTO2026)")
        parser.add_argument('--usos', type=int, default=None, help="Límite máximo de usos (opcional)")
        parser.add_argument('--descripcion', type=str, default='', help="Descripción o grupo destinatario")

    def handle(self, *args, **options):
        codigo = options['codigo'].strip().upper()
        max_usos = options['usos']
        descripcion = options['descripcion']

        invitacion, creada = Invitacion.objects.get_or_create(
            codigo=codigo,
            defaults={
                'max_usos': max_usos,
                'descripcion': descripcion,
                'activa': True
            }
        )

        if creada:
            self.stdout.write(self.style.SUCCESS(
                f"✓ Invitación «{codigo}» creada exitosamente (usos: {max_usos if max_usos is not None else 'ilimitados'})."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"La invitación «{codigo}» ya existe ({invitacion.usos_actuales}/{invitacion.max_usos or '∞'} usos)."
            ))
