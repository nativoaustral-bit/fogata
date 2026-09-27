from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction
from apps.canciones.models import Cancion
from apps.fogatas.models import Fogata


class Command(BaseCommand):
    help = 'Asigna las canciones y Fogatas existentes sin propietario a una cuenta real inicial.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Correo electrónico del usuario que será el propietario inicial.'
        )
        parser.add_argument(
            '--crear-si-no-existe',
            action='store_true',
            help='Si el usuario no existe, crearlo como superusuario/administrador.'
        )
        parser.add_argument(
            '--password',
            type=str,
            default=None,
            help='Contraseña para el usuario si se crea mediante --crear-si-no-existe.'
        )

    def handle(self, *args, **options):
        email_raw = options['email'].strip()
        email = email_raw.lower()
        crear_si_no_existe = options.get('crear_si_no_existe', False)
        password = options.get('password')

        self.stdout.write("=" * 70)
        self.stdout.write("FOGATA — ASIGNACIÓN DE PROPIETARIO INICIAL DE REPERTORIO")
        self.stdout.write("=" * 70)
        self.stdout.write(f"Buscando cuenta con correo normalizado: '{email}'...")

        # 1. Comprobar que existe el usuario indicado
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            # También buscar por username por compatibilidad
            user = User.objects.filter(username__iexact=email).first()

        if not user:
            if crear_si_no_existe:
                if not password:
                    raise CommandError(
                        f"El usuario '{email}' no existe. Si usas --crear-si-no-existe debes proporcionar --password=<clave>."
                    )
                self.stdout.write(f"Creando cuenta administrativa inicial para '{email}'...")
                user = User.objects.create_superuser(
                    username=email,
                    email=email,
                    password=password,
                    first_name='Administrador Fogata'
                )
                self.stdout.write(self.style.SUCCESS(f"✓ Cuenta '{email}' creada con éxito como superusuario."))
            else:
                raise CommandError(
                    f"No existe ningún usuario registrado con el correo '{email}'.\n"
                    f"Primero crea la cuenta (por ejemplo mediante createsuperuser) o pasa el flag --crear-si-no-existe --password=<clave>."
                )

        self.stdout.write(f"✓ Usuario identificado: ID #{user.pk} ({user.email or user.username})")

        # 2. Mostrar cuántas canciones y Fogatas sin propietario existen
        canciones_sin_dueno = Cancion.objects.filter(propietario__isnull=True)
        fogatas_sin_dueno = Fogata.objects.filter(propietario__isnull=True)

        total_c = canciones_sin_dueno.count()
        total_f = fogatas_sin_dueno.count()

        self.stdout.write("\nAuditoría de registros huérfanos:")
        self.stdout.write(f"  - Canciones sin propietario: {total_c}")
        self.stdout.write(f"  - Fogatas sin propietario:   {total_f}")

        if total_c == 0 and total_f == 0:
            self.stdout.write(self.style.WARNING("\nNo existen canciones ni Fogatas sin propietario. Nada que asignar."))
            return

        # 3. Asignarlas dentro de una transacción atómica
        with transaction.atomic():
            c_actualizadas = canciones_sin_dueno.update(propietario=user)
            f_actualizadas = fogatas_sin_dueno.update(propietario=user)

        self.stdout.write(f"\nAsignando a usuario ID #{user.pk}...")
        self.stdout.write(f"  ✓ {c_actualizadas} canciones asignadas.")
        self.stdout.write(f"  ✓ {f_actualizadas} Fogatas asignadas.")

        # 4. Comprobar que no quedan registros huérfanos
        huerfanos_c = Cancion.objects.filter(propietario__isnull=True).count()
        huerfanos_f = Fogata.objects.filter(propietario__isnull=True).count()

        if huerfanos_c > 0 or huerfanos_f > 0:
            raise CommandError(
                f"Error crítico de integridad: Aún quedan {huerfanos_c} canciones y {huerfanos_f} Fogatas sin propietario."
            )

        # 5. Terminar con confirmación clara
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS(
            f"ÉXITO: Catálogo del MVP Personal asignado íntegramente a '{user.email or user.username}'.\n"
            f"0 registros huérfanos. La base de datos está lista para aplicar Migración 2 (null=False)."
        ))
        self.stdout.write("=" * 70)
