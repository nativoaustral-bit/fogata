import json
from django.test import TestCase, Client
from django.urls import reverse


class ManifestPwaTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_manifest_endpoint_status_y_cabeceras(self):
        response = self.client.get('/manifest.webmanifest')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/manifest+json', response['Content-Type'])

    def test_manifest_contenido_requerido(self):
        response = self.client.get('/manifest.webmanifest')
        data = json.loads(response.content.decode('utf-8'))

        self.assertEqual(data.get('id'), '/')
        self.assertEqual(data.get('scope'), '/')
        self.assertEqual(data.get('start_url'), '/')
        self.assertEqual(data.get('display'), 'standalone')
        self.assertEqual(data.get('orientation'), 'any')
        self.assertEqual(data.get('background_color'), '#0d0d0d')
        self.assertEqual(data.get('theme_color'), '#0d0d0d')
        self.assertEqual(data.get('name'), 'Fogata')
        self.assertEqual(data.get('short_name'), 'Fogata')

        # Iconos requeridos
        iconos = data.get('icons', [])
        self.assertGreaterEqual(len(iconos), 2)
        sizes = [icon.get('sizes') for icon in iconos]
        self.assertIn('192x192', sizes)
        self.assertIn('512x512', sizes)


class ServiceWorkerEndpointTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_sw_endpoint_status_y_cabeceras(self):
        response = self.client.get('/sw.js')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/javascript', response['Content-Type'])
        self.assertEqual(response.get('Service-Worker-Allowed'), '/')
        self.assertIn('no-cache', response.get('Cache-Control', ''))

    def test_sw_criterios_arquitectura(self):
        response = self.client.get('/sw.js')
        contenido = response.content.decode('utf-8')

        # Criterio Fase 6: Versionado estático v2 y limpieza de fogata-offline
        self.assertIn("CACHE_STATIC = 'fogata-static-v2'", contenido)
        self.assertIn("fogata-offline", contenido)
        self.assertIn("STATIC_ASSETS", contenido)

        # Criterio 2: NO usar skipWaiting ni clients.claim agresivos durante la sesión
        self.assertNotIn("self.skipWaiting()", contenido)
        self.assertNotIn("self.clients.claim()", contenido)

        # Criterio 4: Exclusivamente peticiones seguras GET y HEAD
        self.assertIn("req.method !== 'GET' && req.method !== 'HEAD'", contenido)

        # Criterio 10 & 11: Fallback seguro a /offline/
        self.assertIn("'/offline/'", contenido)


class OfflineViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_offline_view_status_y_elementos(self):
        url = reverse('core:offline')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/offline.html')

        html = response.content.decode('utf-8')
        self.assertIn('Fogata Offline', html)
        self.assertIn('Biblioteca privada protegida', html)
        self.assertIn('Reintentar conexión', html)


class BaseTemplatePwaTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_base_incluye_meta_pwa_y_banner(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')

        self.assertIn('/manifest.webmanifest', html)
        self.assertIn('/static/icons/icon-192.png', html)
        self.assertIn('apple-mobile-web-app-capable', html)
        self.assertIn('indicador-sin-conexion', html)
        self.assertIn('btn-instalar-pwa', html)
        self.assertIn('Todos los derechos reservados Humm Co-Creation', html)
