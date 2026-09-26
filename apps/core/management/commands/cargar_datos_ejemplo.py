"""
Comando para cargar canciones ficticias creadas exclusivamente para pruebas de desarrollo (Fase 0.1).
Reemplaza cualquier letra protegida por material de prueba libre y controlado.
"""

from django.core.management.base import BaseCommand
from apps.canciones.models import Cancion
from apps.fogatas.models import Fogata, FogataCancion


class Command(BaseCommand):
    help = 'Carga datos de ejemplo con canciones ficticias creadas exclusivamente para pruebas'

    def handle(self, *args, **options):
        self.stdout.write("Cargando canciones ficticias de prueba...")

        c1, _ = Cancion.objects.update_or_create(
            titulo="Atardecer en la Quebrada",
            defaults={
                'artista': "Los Ecos del Valle (Ficticio)",
                'tonalidad': "G",
                'capo': 0,
                'afinacion': "Estándar (E A D G B E)",
                'notas_personales': "Intro con arpegio suave en G y Cadd9. Rasgueo constante en estrofas.",
                'contenido': (
                    "Intro:\n"
                    "G  Cadd9  G  Cadd9\n\n"
                    "G                Cadd9        G            D\n"
                    "Baja la tarde dorada sobre el cerro y el sauzal\n"
                    "G                  Cadd9          Em7          D\n"
                    "Vuelve el rumor de la leña que en el fuego va a brillar\n"
                    "Cadd9              G          Em7          D\n"
                    "Trae tu voz de horizonte y sentémonos a cantar\n\n"
                    "Coro:\n"
                    "G          Cadd9     Em7        D\n"
                    "Fuego de la noche, chispa de canción\n"
                    "G            Cadd9      D          G\n"
                    "Vibra en la guitarra todo el corazón\n\n"
                    "G               Cadd9         G            D\n"
                    "Pasan las horas serenas bajo un cielo de cristal\n"
                    "G                  Cadd9       Em7          D\n"
                    "Queda el rescoldo caliente y un acorde al final\n\n"
                    "Coro:\n"
                    "G          Cadd9     Em7        D\n"
                    "Fuego de la noche, chispa de canción\n"
                    "G            Cadd9      D          G\n"
                    "Vibra en la guitarra todo el corazón\n"
                )
            }
        )

        c2, _ = Cancion.objects.update_or_create(
            titulo="Río de Arena",
            defaults={
                'artista': "Banda Primitiva (Ficticio)",
                'tonalidad': "Am",
                'capo': 2,
                'afinacion': "Estándar (E A D G B E)",
                'notas_personales': "Capo al 2. Rasgueo lento de huayno o balada andina.",
                'contenido': (
                    "Am               Dm            G              C\n"
                    "Corre un río silencioso por la falda del volcán\n"
                    "F                 Dm             E7          Am\n"
                    "Lleva huellas del invierno que temprano pasará\n\n"
                    "Am             Dm           G               C\n"
                    "Sopla viento de la cumbre, no te canses de remar\n"
                    "F                Dm            E7            Am\n"
                    "Que una lumbre en la ribera ya comienza a despertar\n\n"
                    "Puente (Línea larga de prueba de scroll horizontal):\n"
                    "F                           G                           Em7                         Am\n"
                    "Y cuando llegue la medianoche fría sobre las colinas andinas cantaremos el verso que viaja con la corriente hasta el mar azul\n\n"
                    "Coro:\n"
                    "Dm        G       C       F\n"
                    "Río de arena, memoria y cantar\n"
                    "Dm        E7            Am\n"
                    "La noche empieza a clarear\n"
                )
            }
        )

        c3, _ = Cancion.objects.update_or_create(
            titulo="Noche de Viento Sur",
            defaults={
                'artista': "Solsticio Andino (Ficticio)",
                'tonalidad': "D",
                'capo': 0,
                'afinacion': "Estándar (E A D G B E)",
                'notas_personales': "Tiempo rápido 6/8. Acentuar el primer pulso con pulgar.",
                'contenido': (
                    "Intro:\n"
                    "D  A  Bm  G  (x2)\n\n"
                    "D             A            Bm          G\n"
                    "Cruza la ráfaga helada sacudiendo el ventanal\n"
                    "D               A             G          D\n"
                    "Arden las ramas de pino al compás del maderal\n\n"
                    "Bm          F#m           G            A\n"
                    "Nadie precisa de relojes para saber esperar\n"
                    "Bm         F#m           G           A\n"
                    "Solo una ronda sencilla dispuesta a festejar\n\n"
                    "Coro:\n"
                    "D         A        Bm        G\n"
                    "Gira la rueda del tiempo y la paz\n"
                    "D           A        G     D\n"
                    "Canta con fuerza y serenidad\n"
                )
            }
        )

        # Limpiar canciones protegidas anteriores si existían
        Cancion.objects.filter(titulo__in=[
            "De Música Ligera",
            "Muchacha (Ojos de Papel)",
            "Seguir Viviendo Sin Tu Amor",
            "De música ligera",
            "Muchacha (Ojos de papel)",
            "Seguir viviendo sin tu amor",
            "Spinetta - Seguir viviendo sin tu amor"
        ]).delete()

        self.stdout.write("Actualizando Fogata de prueba...")
        fogata, _ = Fogata.objects.get_or_create(
            nombre="🔥 Fogata Acústica de Prueba",
            defaults={
                'descripcion': "Setlist de prueba con canciones ficticias para verificar Modo Músico y Sesión Compartida."
            }
        )

        FogataCancion.objects.filter(fogata=fogata).delete()
        FogataCancion.objects.create(fogata=fogata, cancion=c1, orden=1, nota_sesion="Tema de apertura, arpegio suave")
        FogataCancion.objects.create(fogata=fogata, cancion=c2, orden=2, nota_sesion="Poner capo en traste 2")
        FogataCancion.objects.create(fogata=fogata, cancion=c3, orden=3, nota_sesion="Ritmo rápido, cierre festivo")

        self.stdout.write(self.style.SUCCESS("✓ Canciones ficticias de prueba cargadas correctamente."))
