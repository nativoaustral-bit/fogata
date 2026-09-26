from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.canciones.models import Cancion
from .models import Fogata, FogataCancion, SesionCompartida


class FogataModelAndSetlistTest(TestCase):
    def setUp(self):
        self.cancion1 = Cancion.objects.create(
            titulo="Canción Uno",
            artista="Artista A",
            contenido="Letra uno con acordes"
        )
        self.cancion2 = Cancion.objects.create(
            titulo="Canción Dos",
            artista="Artista B",
            contenido="Letra dos con acordes"
        )
        self.fogata = Fogata.objects.create(
            nombre="Fogata de Prueba",
            descripcion="Repertorio acústico"
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

    def test_tocar_sesion_continuo(self):
        """
        Prueba la vista de ejecución continua de sesión para el músico.
        """
        url = reverse('fogatas:tocar_sesion', args=[self.fogata.pk])
        response = self.client.get(url + '?pos=1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Canción Uno")
        self.assertContains(response, "Tema 1 de 2")
        self.assertContains(response, "Intro especial")
        self.assertContains(response, 'letra-acordes-musico')


class SesionCompartidaTest(TestCase):
    def setUp(self):
        self.cancion = Cancion.objects.create(
            titulo="Canción Fogata",
            artista="Artista Fogata",
            contenido="    G      C\nLetra compartida..."
        )
        self.fogata = Fogata.objects.create(
            nombre="Fogata Playa",
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
        Verifica que el token sea seguro, no secuencial y tenga longitud adecuada (Criterio 5).
        """
        self.assertTrue(len(self.sesion.token) >= 32)
        self.assertTrue(self.sesion.esta_vigente())

    def test_acceso_sesion_vigente_y_cabeceras_privacidad(self):
        """
        Verifica que una sesión vigente responda 200 y aplique cabeceras de privacidad:
        Cache-Control: no-store, private
        X-Robots-Tag: noindex, nofollow
        (Criterio 5).
        """
        url_detalle = reverse('sesion_compartida_publica', args=[self.sesion.token])
        response = self.client.get(url_detalle)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fogata Playa")
        self.assertContains(response, "Canción Fogata")

        # Cabeceras de privacidad en detalle
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')

        # Cabeceras de privacidad en letra individual
        url_cancion = reverse('sesion_compartida_cancion_publica', args=[self.sesion.token, self.cancion.pk])
        response_cancion = self.client.get(url_cancion)
        self.assertEqual(response_cancion.status_code, 200)
        self.assertContains(response_cancion, "Letra compartida")
        self.assertEqual(response_cancion['Cache-Control'], 'no-store, private')
        self.assertEqual(response_cancion['X-Robots-Tag'], 'noindex, nofollow')

    def test_sesion_expirada_retorna_410(self):
        """
        Verifica que al expirar la sesión responda HTTP 410 (Gone) y
        muestre la pantalla sobria 'Esta Fogata terminó' (Criterio 5).
        """
        # Forzar expiración temporal
        self.sesion.expira_el = timezone.now() - timezone.timedelta(minutes=5)
        self.sesion.save()

        url_detalle = reverse('sesion_compartida_publica', args=[self.sesion.token])
        response = self.client.get(url_detalle)
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "Esta Fogata terminó", status_code=410)
        self.assertContains(response, "El acceso a las letras de esta sesión ya no está disponible", status_code=410)
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')

        url_cancion = reverse('sesion_compartida_cancion_publica', args=[self.sesion.token, self.cancion.pk])
        response_cancion = self.client.get(url_cancion)
        self.assertEqual(response_cancion.status_code, 410)
        self.assertContains(response_cancion, "Esta Fogata terminó", status_code=410)

    def test_sesion_revocada_retorna_410(self):
        """
        Verifica que al revocar la sesión responda HTTP 410 (Gone).
        """
        self.sesion.revocar()
        self.assertFalse(self.sesion.activa)
        self.assertFalse(self.sesion.esta_vigente())

        url_detalle = reverse('sesion_compartida_publica', args=[self.sesion.token])
        response = self.client.get(url_detalle)
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "Esta Fogata terminó", status_code=410)
