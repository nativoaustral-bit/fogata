from django.test import TestCase
from django.urls import reverse
from .models import Cancion
from .services import obtener_solo_letra


class CancionModelTest(TestCase):
    def test_creacion_cancion_preserva_contenido_integro(self):
        """
        Verifica que el contenido con espacios, saltos de línea y acordes
        se preserve exactamente tal como fue ingresado (Criterio 2 y 6).
        """
        contenido_prueba = (
            "       Bm           G          D           A\n"
            "Ella durmió al calor de las masas\n"
            "   Bm            G           D        A\n"
            "Y yo desperté queriendo soñarla\n"
        )
        cancion = Cancion.objects.create(
            titulo="De música ligera",
            artista="Soda Stereo",
            tonalidad="Bm",
            capo=0,
            afinacion="Estándar (E A D G B E)",
            contenido=contenido_prueba,
            notas_personales="Rasgueo en corcheas acentuando el 2 y 4"
        )

        # Comprobar que no hubo mutilación de espacios
        self.assertEqual(cancion.contenido, contenido_prueba)
        self.assertEqual(str(cancion), "De música ligera - Soda Stereo")
        self.assertEqual(cancion.get_tocar_url(), reverse('canciones:tocar', args=[cancion.pk]))

    def test_servicio_obtener_solo_letra_no_destructivo(self):
        """
        Verifica que el helper futuro obtener_solo_letra sea tolerante
        y no destruya el contenido original (Criterio 6).
        """
        contenido = "  C    G    Am    F\nLet it be, let it be..."
        resultado = obtener_solo_letra(contenido)
        self.assertIn("Let it be", resultado)
        self.assertEqual(obtener_solo_letra(""), "")


class CancionViewsTest(TestCase):
    def setUp(self):
        self.cancion = Cancion.objects.create(
            titulo="Spinetta - Seguir viviendo sin tu amor",
            artista="Luis Alberto Spinetta",
            tonalidad="F",
            capo=0,
            contenido="    F        Bb\nSi algo callé es porque entendí todo..."
        )

    def test_lista_canciones(self):
        response = self.client.get(reverse('canciones:lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Seguir viviendo sin tu amor")

    def test_busqueda_canciones(self):
        response = self.client.get(reverse('canciones:lista') + '?q=Spinetta')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Luis Alberto Spinetta")

        response_vacia = self.client.get(reverse('canciones:lista') + '?q=Inexistente')
        self.assertEqual(response_vacia.status_code, 200)
        self.assertNotContains(response_vacia, "Seguir viviendo sin tu amor")

    def test_detalle_cancion(self):
        response = self.client.get(reverse('canciones:detalle', args=[self.cancion.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Luis Alberto Spinetta")

    def test_crear_cancion(self):
        data = {
            'titulo': 'Muchacha (Ojos de papel)',
            'artista': 'Almendra',
            'tonalidad': 'G',
            'capo': '0',
            'afinacion': 'Estándar',
            'contenido': '   G       Em\nMuchacha ojos de papel...',
            'notas_personales': 'Intro acústica suave'
        }
        response = self.client.post(reverse('canciones:crear'), data=data)
        self.assertEqual(response.status_code, 302)
        nueva = Cancion.objects.get(titulo='Muchacha (Ojos de papel)')
        self.assertEqual(nueva.artista, 'Almendra')
        self.assertEqual(nueva.contenido, data['contenido'])

    def test_modo_musico_tocar(self):
        """
        Verifica que la vista Tocar use Modo Músico y contenga
        los identificadores para preservación de espaciado y controles de atril.
        """
        response = self.client.get(reverse('canciones:tocar', args=[self.cancion.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="cuerpo-letra"')
        self.assertContains(response, 'letra-acordes-musico')
        self.assertContains(response, 'btn-zoom-menos')
        self.assertContains(response, 'btn-zoom-mas')
        self.assertContains(response, 'btn-wakelock')
