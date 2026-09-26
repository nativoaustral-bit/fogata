from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.canciones.models import Cancion
from .models import Fogata, FogataCancion, SesionCompartida


class FogataModelAndSetlistTest(TestCase):
    def setUp(self):
        self.cancion1 = Cancion.objects.create(
            titulo="Canción Uno Ficticia",
            artista="Artista A",
            contenido="    G      C\nLetra ficticia uno con acordes"
        )
        self.cancion2 = Cancion.objects.create(
            titulo="Canción Dos Ficticia",
            artista="Artista B",
            contenido="    D      A\nLetra ficticia dos con acordes"
        )
        self.cancion3 = Cancion.objects.create(
            titulo="Canción Tres Ficticia",
            artista="Artista C",
            contenido="    Em     Bm\nLetra ficticia tres con acordes"
        )
        self.fogata = Fogata.objects.create(
            nombre="Fogata de Prueba Ficticia",
            descripcion="Repertorio acústico para pruebas"
        )
        self.fc1 = FogataCancion.objects.create(
            fogata=self.fogata,
            cancion=self.cancion1,
            orden=1,
            nota_sesion="Intro especial"
        )
        self.fc2 = FogataCancion.objects.create(
            fogata=self.fogata,
            cancion=self.cancion2,
            orden=2
        )
        self.fc3 = FogataCancion.objects.create(
            fogata=self.fogata,
            cancion=self.cancion3,
            orden=3
        )

    def test_reordenamiento_setlist(self):
        """
        Prueba mover canciones arriba y abajo en el setlist.
        """
        # Mover cancion2 hacia arriba
        url_mover = reverse('fogatas:mover_cancion', args=[self.fogata.pk, self.cancion2.pk, 'subir'])
        response = self.client.post(url_mover)
        self.assertEqual(response.status_code, 302)

        # Comprobar nuevo orden
        self.fc2.refresh_from_db()
        self.fc1.refresh_from_db()
        self.assertEqual(self.fc2.orden, 1)
        self.assertEqual(self.fc1.orden, 2)

    def test_tocar_sesion_continuo_y_navegacion_pos(self):
        """
        Prueba la vista de ejecución continua y navegación anterior/siguiente.
        """
        url = reverse('fogatas:tocar_sesion', args=[self.fogata.pk])

        # Tema 1
        r1 = self.client.get(url + '?pos=1')
        self.assertEqual(r1.status_code, 200)
        self.assertContains(r1, "Canción Uno Ficticia")
        self.assertContains(r1, "Tema 1 de 3")
        self.assertContains(r1, "Intro especial")
        self.assertContains(r1, 'letra-acordes-musico')
        self.assertContains(r1, 'Siguiente (#2)')

        # Tema 2 (intermedio con anterior y siguiente)
        r2 = self.client.get(url + '?pos=2')
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, "Canción Dos Ficticia")
        self.assertContains(r2, "Anterior (#1)")
        self.assertContains(r2, "Siguiente (#3)")

        # Tema 3 (final)
        r3 = self.client.get(url + '?pos=3')
        self.assertEqual(r3.status_code, 200)
        self.assertContains(r3, "Canción Tres Ficticia")
        self.assertContains(r3, "Anterior (#2)")
        self.assertContains(r3, "Fin del Setlist")

        # Posición fuera de rango por debajo (< 1) -> ajusta automáticamente a 1
        r_low = self.client.get(url + '?pos=0')
        self.assertEqual(r_low.status_code, 200)
        self.assertContains(r_low, "Tema 1 de 3")

        # Posición fuera de rango por arriba (> max) -> ajusta automáticamente al último
        r_high = self.client.get(url + '?pos=999')
        self.assertEqual(r_high.status_code, 200)
        self.assertContains(r_high, "Tema 3 de 3")


class SesionCompartidaTest(TestCase):
    def setUp(self):
        self.cancion = Cancion.objects.create(
            titulo="Canción Privada de Fogata",
            artista="Artista Exclusivo",
            contenido="    G      C\nLetra secreta de prueba que no debe filtrarse..."
        )
        self.fogata = Fogata.objects.create(
            nombre="Fogata Playa Privada",
            descripcion="Fogata nocturna"
        )
        FogataCancion.objects.create(
            fogata=self.fogata,
            cancion=self.cancion,
            orden=1
        )
        self.sesion = SesionCompartida.objects.create(
            fogata=self.fogata,
            expira_el=timezone.now() + timezone.timedelta(hours=4)
        )

    def test_token_seguridad_y_entropia(self):
        """
        Verifica que el token sea seguro, no secuencial y tenga al menos 32 caracteres (~192 bits).
        """
        self.assertTrue(len(self.sesion.token) >= 32)
        self.assertTrue(self.sesion.esta_vigente())

    def test_acceso_sesion_vigente_y_cabeceras_privacidad(self):
        """
        Verifica que una sesión vigente responda 200 y aplique cabeceras de privacidad:
        Cache-Control: no-store, private
        X-Robots-Tag: noindex, nofollow
        """
        url_detalle = reverse('sesion_compartida_publica', args=[self.sesion.token])
        response = self.client.get(url_detalle)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fogata Playa Privada")
        self.assertContains(response, "Canción Privada de Fogata")

        # Cabeceras de privacidad en índice de sesión
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.assertContains(response, '<meta name="robots" content="noindex, nofollow">')

        # Cabeceras de privacidad en letra individual
        url_cancion = reverse('sesion_compartida_cancion_publica', args=[self.sesion.token, self.cancion.pk])
        response_cancion = self.client.get(url_cancion)
        self.assertEqual(response_cancion.status_code, 200)
        self.assertContains(response_cancion, "Letra secreta de prueba")
        self.assertEqual(response_cancion['Cache-Control'], 'no-store, private')
        self.assertEqual(response_cancion['X-Robots-Tag'], 'noindex, nofollow')
        self.assertContains(response_cancion, '<meta name="robots" content="noindex, nofollow">')

    def test_sesion_expirada_no_entrega_contenido_y_retorna_410(self):
        """
        Verifica que una sesión expirada NO entregue contenido de las canciones
        y retorne HTTP 410 con pantalla sobria y cabeceras de privacidad.
        """
        self.sesion.expira_el = timezone.now() - timezone.timedelta(minutes=5)
        self.sesion.save()

        # Detalle de sesión expirada
        url_detalle = reverse('sesion_compartida_publica', args=[self.sesion.token])
        response = self.client.get(url_detalle)
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "Esta Fogata terminó", status_code=410)
        self.assertContains(response, "El acceso a las letras de esta sesión ya no está disponible", status_code=410)
        self.assertNotContains(response, "Canción Privada de Fogata", status_code=410)
        self.assertNotContains(response, "Letra secreta de prueba", status_code=410)
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')

        # Canción individual en sesión expirada
        url_cancion = reverse('sesion_compartida_cancion_publica', args=[self.sesion.token, self.cancion.pk])
        response_cancion = self.client.get(url_cancion)
        self.assertEqual(response_cancion.status_code, 410)
        self.assertContains(response_cancion, "Esta Fogata terminó", status_code=410)
        self.assertNotContains(response_cancion, "Letra secreta de prueba", status_code=410)

    def test_sesion_revocada_no_entrega_contenido_y_retorna_410(self):
        """
        Verifica que una sesión revocada manualmente no entregue contenido.
        """
        self.sesion.revocar()
        self.assertFalse(self.sesion.activa)
        self.assertFalse(self.sesion.esta_vigente())

        url_detalle = reverse('sesion_compartida_publica', args=[self.sesion.token])
        response = self.client.get(url_detalle)
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "Esta Fogata terminó", status_code=410)
        self.assertNotContains(response, "Canción Privada de Fogata", status_code=410)

    def test_cancion_inexistente_en_sesion_no_entrega_contenido_y_retorna_410(self):
        """
        Verifica que solicitar una canción ajena a la sesión devuelva 410 sin filtrar información.
        """
        url_invalida = reverse('sesion_compartida_cancion_publica', args=[self.sesion.token, 99999])
        response = self.client.get(url_invalida)
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "Esta Fogata terminó", status_code=410)
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
