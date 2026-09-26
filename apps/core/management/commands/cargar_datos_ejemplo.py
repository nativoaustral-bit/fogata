from django.core.management.base import BaseCommand
from apps.canciones.models import Cancion
from apps.fogatas.models import Fogata, FogataCancion


class Command(BaseCommand):
    help = 'Carga datos de ejemplo con canciones y una Fogata de demostración'

    def handle(self, *args, **options):
        self.stdout.write("Cargando canciones de ejemplo...")

        c1, _ = Cancion.objects.get_or_create(
            titulo="De Música Ligera",
            defaults={
                'artista': "Soda Stereo",
                'tonalidad': "Bm",
                'capo': 0,
                'afinacion': "Estándar (E A D G B E)",
                'notas_personales': "Intro: Bm - G - D - A con ritmo constante de 4 compases. Rasgueo enérgico.",
                'contenido': (
                    "Intro:\n"
                    "Bm  G  D  A  (x2)\n\n"
                    "Bm         G            D           A\n"
                    "Ella durmió al calor de las masas\n"
                    "Bm       G             D        A\n"
                    "Y yo desperté queriendo soñarla\n"
                    "Bm          G          D          A\n"
                    "Algún tiempo atrás pensé en escribirle\n"
                    "Bm         G           D            A\n"
                    "Que nunca sorteé las trampas del amor\n\n"
                    "Coro:\n"
                    "Bm         G     D        A\n"
                    "De aquel amor de música ligera\n"
                    "Bm      G       D        A\n"
                    "Nada nos libra, nada más queda\n\n"
                    "Bm         G            D           A\n"
                    "No le envié cenizas de rosas\n"
                    "Bm          G         D        A\n"
                    "Ni quise evitar un roce secreto\n\n"
                    "Coro:\n"
                    "Bm         G     D        A\n"
                    "De aquel amor de música ligera\n"
                    "Bm      G       D        A\n"
                    "Nada nos libra, nada más queda\n\n"
                    "Outro:\n"
                    "Bm  G  D  A\n"
                    "¡Gracias... totales!\n"
                )
            }
        )

        c2, _ = Cancion.objects.get_or_create(
            titulo="Muchacha (Ojos de Papel)",
            defaults={
                'artista': "Almendra",
                'tonalidad': "G",
                'capo': 0,
                'afinacion': "Estándar (E A D G B E)",
                'notas_personales': "Arpegio suave en guitarra acústica. Tiempo lento y expresivo.",
                'contenido': (
                    "G              D/F#  Em          C\n"
                    "Muchacha ojos de papel, ¿a dónde vas?\n"
                    "G/B          Am7    D7\n"
                    "Quédate hasta el alba\n"
                    "G              D/F#  Em          C\n"
                    "Muchacha pequeños pies, no corras más\n"
                    "G/B          Am7    D7\n"
                    "Quédate hasta el alba\n\n"
                    "Em             Em/D       C\n"
                    "Sueña un sueño despacito entre mis manos\n"
                    "G/B           Am7       D7\n"
                    "Hasta que todo el día ilumine\n"
                    "G              D/F#   Em          C\n"
                    "Muchacha corteza de mi corazón\n"
                    "G/B            Am7    D7       G\n"
                    "Ven a mí, para siempre en esta noche\n"
                )
            }
        )

        c3, _ = Cancion.objects.get_or_create(
            titulo="Seguir Viviendo Sin Tu Amor",
            defaults={
                'artista': "Luis Alberto Spinetta",
                'tonalidad': "F",
                'capo': 0,
                'afinacion': "Estándar (E A D G B E)",
                'notas_personales': "Balada acústica con rasgueo sincopado. Cuidar transiciones en puentes.",
                'contenido': (
                    "Intro:\n"
                    "F  Bbmaj7  Gm7  C7\n\n"
                    "F          Bbmaj7\n"
                    "Si algo callé\n"
                    "Gm7           C7\n"
                    "Es porque entendí todo\n"
                    "F           Bbmaj7\n"
                    "Menos la distancia\n\n"
                    "Dm            Am7\n"
                    "Desfiguré el corazón\n"
                    "Bbmaj7        Gm7          C7\n"
                    "De tanto esperar un nuevo día\n\n"
                    "Coro:\n"
                    "F          Bbmaj7\n"
                    "Y hoy que enloquecí\n"
                    "Gm7           C7\n"
                    "Siento el vacío en mi voz\n"
                    "Dm        Am7       Bbmaj7    C7\n"
                    "¿Y cómo hacer para seguir viviendo sin tu amor?\n"
                )
            }
        )

        self.stdout.write("Creando Fogata de ejemplo...")
        fogata, _ = Fogata.objects.get_or_create(
            nombre="🔥 Acústicos Clásicos de Fogata",
            defaults={
                'descripcion': "Setlist probado para tocar al aire libre o en fogata nocturna. Clásicos que todos cantan."
            }
        )

        # Asociar canciones con orden
        FogataCancion.objects.get_or_create(
            fogata=fogata,
            cancion=c1,
            defaults={'orden': 1, 'nota_sesion': "Arrancar con fuerza para animar la ronda"}
        )
        FogataCancion.objects.get_or_create(
            fogata=fogata,
            cancion=c2,
            defaults={'orden': 2, 'nota_sesion': "Bajar volumen, arpegio íntimo"}
        )
        FogataCancion.objects.get_or_create(
            fogata=fogata,
            cancion=c3,
            defaults={'orden': 3, 'nota_sesion': "Cierre emotivo para cantar todos"}
        )

        self.stdout.write(self.style.SUCCESS("✓ Datos de ejemplo cargados correctamente."))
