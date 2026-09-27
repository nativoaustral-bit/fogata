from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from apps.canciones.models import Cancion
from .models import Fogata, FogataCancion, SesionCompartida


class FogataModelAndSetlistTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='musico_fogata@fogata.app',
            email='musico_fogata@fogata.app',
            password='password123'
        )
        self.client.force_login(self.user)
        self.cancion1 = Cancion.objects.create(
            propietario=self.user,
            titulo="Canción Uno Ficticia",
            artista="Artista A",
            contenido="    G      C\nLetra ficticia uno con acordes"
        )
        self.cancion2 = Cancion.objects.create(
            propietario=self.user,
            titulo="Canción Dos Ficticia",
            artista="Artista B",
            contenido="    D      A\nLetra ficticia dos con acordes"
        )
        self.cancion3 = Cancion.objects.create(
            propietario=self.user,
            titulo="Canción Tres Ficticia",
            artista="Artista C",
            contenido="    Em     Bm\nLetra ficticia tres con acordes"
        )
        self.fogata = Fogata.objects.create(
            propietario=self.user,
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

    def test_tocar_sesion_renderiza_barra_inferior_atril(self):
        """
        Verifica que el modo sesión incluya la barra fija inferior de auto-scroll,
        bloques, velocidad y el espaciador de seguridad.
        """
        url = reverse('fogatas:tocar_sesion', args=[self.fogata.pk]) + '?pos=1'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="atril-bottom-bar"')
        self.assertContains(res, 'id="btn-scroll-toggle"')
        self.assertContains(res, 'id="btn-bloque-ant"')
        self.assertContains(res, 'id="btn-bloque-sig"')
        self.assertContains(res, 'id="indicador-velocidad"')
        self.assertContains(res, 'class="atril-bottom-spacer"')
        # Mantiene además la barra de navegación entre temas del setlist
        self.assertContains(res, 'class="sesion-nav-bar"')
        self.assertContains(res, 'Siguiente (#2)')



class SesionCompartidaTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='musico_compartida@fogata.app',
            email='musico_compartida@fogata.app',
            password='password123'
        )
        self.cancion = Cancion.objects.create(
            propietario=self.user,
            titulo="Canción Privada de Fogata",
            artista="Artista Exclusivo",
            contenido="    G      C\nLetra secreta de prueba que no debe filtrarse..."
        )
        self.fogata = Fogata.objects.create(
            propietario=self.user,
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


# =============================================================================
# Pruebas Automatizadas Fase 5: Modo Offline y PWA Deliberada
# =============================================================================

class FogataOfflineIntegrationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='musico_offline@fogata.app',
            email='musico_offline@fogata.app',
            password='password123'
        )
        self.client.force_login(self.user)
        self.fogata = Fogata.objects.create(
            propietario=self.user,
            nombre="Fogata Nocturna PWA",
            descripcion="Para tocar sin señal"
        )
        self.c1 = Cancion.objects.create(propietario=self.user, titulo="Tema Uno", contenido="[Intro]\nC   G\nLetra 1", tonalidad="C")
        self.c2 = Cancion.objects.create(propietario=self.user, titulo="Tema Dos", contenido="[Verso]\nAm  F\nLetra 2", tonalidad="Am")
        self.c3 = Cancion.objects.create(propietario=self.user, titulo="Tema Tres", contenido="[Coro]\nG   D\nLetra 3", tonalidad="G")

        FogataCancion.objects.create(fogata=self.fogata, cancion=self.c1, orden=1)
        FogataCancion.objects.create(fogata=self.fogata, cancion=self.c2, orden=2)
        FogataCancion.objects.create(fogata=self.fogata, cancion=self.c3, orden=3)

    def test_detalle_fogata_suspende_panel_offline_en_piloto(self):
        """
        Requisito 11 de Fase 6:
        En el piloto multiusuario, el botón '⬇ Disponible sin conexión' está suspendido
        para evitar filtraciones o riesgos entre usuarios en CacheStorage.
        """
        url = reverse('fogatas:detalle', args=[self.fogata.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertNotIn('id="btn-descargar-offline"', html)
        self.assertNotIn('⬇ Disponible sin conexión', html)

    def test_rutas_necesarias_para_preparar_fogata_offline(self):
        """
        Criterio 8:
        Para una Fogata con N canciones, deben existir y responder con 200:
        - /fogatas/<id>/
        - /fogatas/<id>/tocar/?pos=1..N
        - /canciones/diagramas/batch/
        """
        urls_requeridas = [
            reverse('fogatas:detalle', args=[self.fogata.pk]),
            f"{reverse('fogatas:tocar_sesion', args=[self.fogata.pk])}?pos=1",
            f"{reverse('fogatas:tocar_sesion', args=[self.fogata.pk])}?pos=2",
            f"{reverse('fogatas:tocar_sesion', args=[self.fogata.pk])}?pos=3",
            '/canciones/diagramas/batch/'
        ]

        for u in urls_requeridas:
            res = self.client.get(u)
            self.assertEqual(res.status_code, 200, f"Fallo al acceder a URL requerida offline: {u}")

    def test_fogata_js_gestion_offline_deliberada_y_es5(self):
        """
        Criterios 1, 3, 9, 17, 18, 19:
        Verifica que fogata.js contenga la lógica de almacenamiento offline deliberado,
        atómico, con preservación de versión anterior ante fallos y ES5 estricto.
        """
        with open('static/js/fogata.js', 'r', encoding='utf-8') as f:
            js = f.read()

        self.assertIn('initGestionFogatasOffline', js)
        self.assertIn('fogata_offline_repertorios', js)
        self.assertIn('fogata-offline', js)
        self.assertIn('No pudimos completar la descarga. Tu Fogata anterior no fue modificada.', js)
        self.assertIn('QuotaExceededError', js)
        self.assertIn('Esta acción necesita conexión.', js)

        # Verificar ES5 estricto
        self.assertNotIn('const ', js)
        self.assertNotIn('let ', js)
        self.assertNotIn('=>', js)

