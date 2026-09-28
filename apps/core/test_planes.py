from django.test import TestCase, TransactionTestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings

from apps.core.models import PerfilPiloto, Invitacion
from apps.core.planes import (
    obtener_tipo_cuenta,
    limite_canciones,
    limite_fogatas,
    canciones_utilizadas,
    fogatas_utilizadas,
    puede_crear_cancion,
    puede_crear_fogata,
    obtener_estado_capacidad,
)
from apps.canciones.models import Cancion
from apps.fogatas.models import Fogata, FogataCancion, SesionCompartida
from apps.gestion.models import EventoUso, AuditoriaAdmin
from apps.gestion.metrics import obtener_metricas_comerciales


class PlanesServiceTests(TestCase):
    """
    Pruebas unitarias para el servicio central de límites y planes (Criterios 2, 3, 4, 5, 6).
    """
    def setUp(self):
        self.user_anonimo = None
        self.user_admin = User.objects.create_user(
            username='admin@test.cl', email='admin@test.cl', password='password123', is_staff=True
        )
        self.user_piloto = User.objects.create_user(
            username='piloto@test.cl', email='piloto@test.cl', password='password123'
        )
        PerfilPiloto.objects.create(user=self.user_piloto, tipo_cuenta='PILOTO')

        self.user_pro = User.objects.create_user(
            username='pro@test.cl', email='pro@test.cl', password='password123'
        )
        PerfilPiloto.objects.create(user=self.user_pro, tipo_cuenta='PRO')

        self.user_gratis = User.objects.create_user(
            username='gratis@test.cl', email='gratis@test.cl', password='password123'
        )
        PerfilPiloto.objects.create(user=self.user_gratis, tipo_cuenta='GRATIS')

        # Usuario sin perfil (caso legado / existente)
        self.user_legado = User.objects.create_user(
            username='legado@test.cl', email='legado@test.cl', password='password123'
        )

    def test_obtener_tipo_cuenta(self):
        self.assertEqual(obtener_tipo_cuenta(self.user_anonimo), 'ANONIMO')
        self.assertEqual(obtener_tipo_cuenta(self.user_admin), 'ADMIN')
        self.assertEqual(obtener_tipo_cuenta(self.user_piloto), 'PILOTO')
        self.assertEqual(obtener_tipo_cuenta(self.user_pro), 'PRO')
        self.assertEqual(obtener_tipo_cuenta(self.user_gratis), 'GRATIS')
        self.assertEqual(obtener_tipo_cuenta(self.user_legado), 'PILOTO')

    def test_limites_segun_tipo(self):
        # ADMIN, PILOTO, PRO son ilimitados (None)
        self.assertIsNone(limite_canciones(self.user_admin))
        self.assertIsNone(limite_fogatas(self.user_admin))

        self.assertIsNone(limite_canciones(self.user_piloto))
        self.assertIsNone(limite_fogatas(self.user_piloto))

        self.assertIsNone(limite_canciones(self.user_pro))
        self.assertIsNone(limite_fogatas(self.user_pro))

        # GRATIS tiene límites numéricos configurados
        self.assertEqual(limite_canciones(self.user_gratis), 10)
        self.assertEqual(limite_fogatas(self.user_gratis), 1)

    def test_obtener_estado_capacidad(self):
        cap_gratis = obtener_estado_capacidad(self.user_gratis)
        self.assertEqual(cap_gratis['tipo_cuenta'], 'GRATIS')
        self.assertEqual(cap_gratis['nombre_plan'], 'Fogata Gratis')
        self.assertFalse(cap_gratis['es_ilimitado'])
        self.assertEqual(cap_gratis['canciones_usadas'], 0)
        self.assertEqual(cap_gratis['canciones_limite'], 10)
        self.assertEqual(cap_gratis['canciones_disponibles'], 10)
        self.assertTrue(cap_gratis['puede_crear_cancion'])
        self.assertFalse(cap_gratis['sobre_limite_canciones'])
        self.assertFalse(cap_gratis['es_cercano_limite_canciones'])

        cap_pro = obtener_estado_capacidad(self.user_pro)
        self.assertEqual(cap_pro['tipo_cuenta'], 'PRO')
        self.assertEqual(cap_pro['nombre_plan'], 'Fogata Pro')
        self.assertTrue(cap_pro['es_ilimitado'])
        self.assertIsNone(cap_pro['canciones_limite'])
        self.assertIsNone(cap_pro['canciones_disponibles'])
        self.assertTrue(cap_pro['puede_crear_cancion'])


class FreemiumLimitesCancionesTests(TestCase):
    """
    Pruebas de límites de canciones, rechazo amigable en servidor y preservación de Modo Tocar (Criterios 7, 8, 12).
    """
    def setUp(self):
        self.user_gratis = User.objects.create_user(
            username='gratis@test.cl', email='gratis@test.cl', password='password123'
        )
        PerfilPiloto.objects.create(user=self.user_gratis, tipo_cuenta='GRATIS')

        self.user_pro = User.objects.create_user(
            username='pro@test.cl', email='pro@test.cl', password='password123'
        )
        PerfilPiloto.objects.create(user=self.user_pro, tipo_cuenta='PRO')

    def test_usuario_gratis_puede_crear_hasta_10_canciones(self):
        self.client.login(username='gratis@test.cl', password='password123')

        for i in range(1, 11):
            response = self.client.post(reverse('canciones:crear'), {
                'titulo': f'Canción {i}',
                'artista': 'Artista Test',
                'contenido': f'Letra de la cancion {i}',
                'tonalidad': 'C',
                'capo': 0
            })
            self.assertEqual(response.status_code, 302, f"Falló al crear canción {i}")

        self.assertEqual(Cancion.objects.filter(propietario=self.user_gratis).count(), 10)

    def test_cancion_11_es_rechazada_en_servidor_y_muestra_pantalla_comercial(self):
        self.client.login(username='gratis@test.cl', password='password123')

        # Crear 10 canciones
        for i in range(1, 11):
            Cancion.objects.create(
                propietario=self.user_gratis,
                titulo=f'Canción {i}',
                contenido='Contenido de prueba'
            )

        self.assertEqual(Cancion.objects.filter(propietario=self.user_gratis).count(), 10)

        # 1. Intentar GET /canciones/nueva/
        response_get = self.client.get(reverse('canciones:crear'))
        self.assertEqual(response_get.status_code, 200)
        self.assertTemplateUsed(response_get, 'canciones/limite_alcanzado.html')
        self.assertContains(response_get, 'Tu repertorio está creciendo')
        self.assertContains(response_get, 'Conocer Fogata Pro')

        # 2. Intentar POST forzado /canciones/nueva/
        response_post = self.client.post(reverse('canciones:crear'), {
            'titulo': 'Canción 11 Prohibida',
            'artista': 'Hacker',
            'contenido': 'No debería crearse',
            'tonalidad': 'D',
            'capo': 0
        })
        self.assertEqual(response_post.status_code, 200)
        self.assertTemplateUsed(response_post, 'canciones/limite_alcanzado.html')
        # El conteo se mantiene en 10 estrictamente
        self.assertEqual(Cancion.objects.filter(propietario=self.user_gratis).count(), 10)

    def test_usuario_gratis_en_limite_puede_usar_todas_las_funciones_musicales(self):
        self.client.login(username='gratis@test.cl', password='password123')

        cancion = None
        for i in range(1, 11):
            cancion = Cancion.objects.create(
                propietario=self.user_gratis,
                titulo=f'Canción {i}',
                contenido='[C]Letra con [G]acordes'
            )

        # Modo Tocar
        response_tocar = self.client.get(reverse('canciones:tocar', kwargs={'pk': cancion.pk}))
        self.assertEqual(response_tocar.status_code, 200)

        # Transposición
        response_trans = self.client.get(reverse('canciones:tocar', kwargs={'pk': cancion.pk}) + '?semitonos=2')
        self.assertEqual(response_trans.status_code, 200)

        # Edición
        response_edit = self.client.post(reverse('canciones:editar', kwargs={'pk': cancion.pk}), {
            'titulo': 'Canción 10 Editada',
            'artista': 'Nuevo Artista',
            'contenido': '[D]Letra editada',
            'tonalidad': 'D',
            'capo': 2
        })
        self.assertEqual(response_edit.status_code, 302)
        cancion.refresh_from_db()
        self.assertEqual(cancion.titulo, 'Canción 10 Editada')

    def test_usuario_pro_puede_crear_mas_de_10_canciones(self):
        self.client.login(username='pro@test.cl', password='password123')

        for i in range(1, 12):
            response = self.client.post(reverse('canciones:crear'), {
                'titulo': f'Canción Pro {i}',
                'artista': 'Artista Pro',
                'contenido': f'Letra pro {i}',
                'tonalidad': 'A',
                'capo': 0
            })
            self.assertEqual(response.status_code, 302)

        self.assertEqual(Cancion.objects.filter(propietario=self.user_pro).count(), 11)


class FreemiumLimitesFogatasTests(TestCase):
    """
    Pruebas de límite de Fogatas en cuentas Gratis y Pro (Criterios 9, 10, 11).
    """
    def setUp(self):
        self.user_gratis = User.objects.create_user(
            username='gratis_f@test.cl', email='gratis_f@test.cl', password='password123'
        )
        PerfilPiloto.objects.create(user=self.user_gratis, tipo_cuenta='GRATIS')

        self.user_pro = User.objects.create_user(
            username='pro_f@test.cl', email='pro_f@test.cl', password='password123'
        )
        PerfilPiloto.objects.create(user=self.user_pro, tipo_cuenta='PRO')

    def test_usuario_gratis_puede_crear_una_fogata_y_segunda_es_rechazada(self):
        self.client.login(username='gratis_f@test.cl', password='password123')

        # 1ra Fogata: permitida
        response_1 = self.client.post(reverse('fogatas:crear'), {
            'nombre': 'Fogata Sábado',
            'descripcion': 'Ensayo de banda'
        })
        self.assertEqual(response_1.status_code, 302)
        self.assertEqual(Fogata.objects.filter(propietario=self.user_gratis).count(), 1)

        # 2da Fogata: rechazada en GET
        response_get = self.client.get(reverse('fogatas:crear'))
        self.assertEqual(response_get.status_code, 200)
        self.assertTemplateUsed(response_get, 'fogatas/limite_alcanzado.html')
        self.assertContains(response_get, '¿Otra Fogata?')

        # 2da Fogata: rechazada en POST forzado
        response_post = self.client.post(reverse('fogatas:crear'), {
            'nombre': 'Fogata Domingo No Permitida',
            'descripcion': 'Segunda sesión'
        })
        self.assertEqual(response_post.status_code, 200)
        self.assertTemplateUsed(response_post, 'fogatas/limite_alcanzado.html')
        self.assertEqual(Fogata.objects.filter(propietario=self.user_gratis).count(), 1)

    def test_usuario_gratis_puede_reutilizar_editar_y_compartir_su_fogata(self):
        self.client.login(username='gratis_f@test.cl', password='password123')

        fogata = Fogata.objects.create(propietario=self.user_gratis, nombre='Fogata Única')
        cancion = Cancion.objects.create(propietario=self.user_gratis, titulo='Tema 1', contenido='Letra')
        FogataCancion.objects.create(fogata=fogata, cancion=cancion, orden=1)

        # Editar nombre
        response_edit = self.client.post(reverse('fogatas:editar', kwargs={'pk': fogata.pk}), {
            'nombre': 'Fogata Renombrada',
            'descripcion': 'Nueva descripción'
        })
        self.assertEqual(response_edit.status_code, 302)
        fogata.refresh_from_db()
        self.assertEqual(fogata.nombre, 'Fogata Renombrada')

        # Compartir sesión (Criterio 11)
        response_compartir = self.client.post(reverse('fogatas:compartir_crear', kwargs={'pk': fogata.pk}), {
            'duracion_horas': 4
        })
        self.assertEqual(response_compartir.status_code, 302)
        sesion = SesionCompartida.objects.filter(fogata=fogata).first()
        self.assertIsNotNone(sesion)
        self.assertTrue(sesion.esta_vigente())

    def test_usuario_pro_puede_crear_multiples_fogatas(self):
        self.client.login(username='pro_f@test.cl', password='password123')

        for i in range(1, 4):
            response = self.client.post(reverse('fogatas:crear'), {
                'nombre': f'Fogata Pro {i}',
                'descripcion': f'Descripción {i}'
            })
            self.assertEqual(response.status_code, 302)

        self.assertEqual(Fogata.objects.filter(propietario=self.user_pro).count(), 3)


class DowngradeTests(TestCase):
    """
    Pruebas de cambio de plan PRO → GRATIS (Criterio 19):
    Nunca borrar, ocultar o bloquear contenido preexistente.
    """
    def setUp(self):
        self.user = User.objects.create_user(
            username='downgrade@test.cl', email='downgrade@test.cl', password='password123'
        )
        self.perfil = PerfilPiloto.objects.create(user=self.user, tipo_cuenta='PRO')

        # Crear 15 canciones y 3 Fogatas como PRO
        for i in range(1, 16):
            Cancion.objects.create(propietario=self.user, titulo=f'Canción {i}', contenido='Acordes')

        for i in range(1, 4):
            Fogata.objects.create(propietario=self.user, nombre=f'Fogata {i}')

    def test_downgrade_preserva_todo_el_contenido_y_bloquea_nuevas_creaciones(self):
        self.assertEqual(Cancion.objects.filter(propietario=self.user).count(), 15)
        self.assertEqual(Fogata.objects.filter(propietario=self.user).count(), 3)

        # Aplicar Downgrade
        self.perfil.tipo_cuenta = 'GRATIS'
        self.perfil.save()

        # 1. Contenido existente permanece íntegro
        self.assertEqual(Cancion.objects.filter(propietario=self.user).count(), 15)
        self.assertEqual(Fogata.objects.filter(propietario=self.user).count(), 3)

        # 2. Puede ver, tocar y editar canciones existentes
        self.client.login(username='downgrade@test.cl', password='password123')
        cancion_1 = Cancion.objects.filter(propietario=self.user).first()
        res_tocar = self.client.get(reverse('canciones:tocar', kwargs={'pk': cancion_1.pk}))
        self.assertEqual(res_tocar.status_code, 200)

        # 3. No puede crear la canción 16
        res_crear_c = self.client.post(reverse('canciones:crear'), {
            'titulo': 'Canción 16',
            'contenido': 'Letra',
        })
        self.assertEqual(res_crear_c.status_code, 200)
        self.assertTemplateUsed(res_crear_c, 'canciones/limite_alcanzado.html')
        self.assertEqual(Cancion.objects.filter(propietario=self.user).count(), 15)

        # 4. No puede crear la 4ta Fogata
        res_crear_f = self.client.post(reverse('fogatas:crear'), {
            'nombre': 'Fogata 4',
        })
        self.assertEqual(res_crear_f.status_code, 200)
        self.assertTemplateUsed(res_crear_f, 'fogatas/limite_alcanzado.html')
        self.assertEqual(Fogata.objects.filter(propietario=self.user).count(), 3)


class ControlCenterCambioPlanTests(TestCase):
    """
    Pruebas de cambio manual de plan en Control Center con AuditoriaAdmin (Criterios 17, 18).
    """
    def setUp(self):
        self.staff_admin = User.objects.create_user(
            username='admin@control.cl', email='admin@control.cl', password='password123', is_staff=True
        )
        self.user_comun = User.objects.create_user(
            username='usuario@comun.cl', email='usuario@comun.cl', password='password123'
        )
        PerfilPiloto.objects.create(user=self.user_comun, tipo_cuenta='GRATIS')

    def test_cambio_plan_requiere_staff(self):
        self.client.login(username='usuario@comun.cl', password='password123')
        url = reverse('gestion:usuario_cambiar_plan', kwargs={'pk': self.user_comun.pk})
        response = self.client.post(url, {'nuevo_plan': 'PRO'})
        self.assertEqual(response.status_code, 403)

    def test_cambio_plan_requiere_post(self):
        self.client.login(username='admin@control.cl', password='password123')
        url = reverse('gestion:usuario_cambiar_plan', kwargs={'pk': self.user_comun.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_staff_puede_cambiar_plan_y_genera_auditoria(self):
        self.client.login(username='admin@control.cl', password='password123')
        url = reverse('gestion:usuario_cambiar_plan', kwargs={'pk': self.user_comun.pk})

        response = self.client.post(url, {'nuevo_plan': 'PRO'})
        self.assertEqual(response.status_code, 302)

        self.user_comun.perfil_piloto.refresh_from_db()
        self.assertEqual(self.user_comun.perfil_piloto.tipo_cuenta, 'PRO')

        # Auditoría registrada
        auditoria = AuditoriaAdmin.objects.filter(
            usuario_afectado=self.user_comun,
            accion='cambiar_plan'
        ).first()
        self.assertIsNotNone(auditoria)
        self.assertEqual(auditoria.admin, self.staff_admin)
        self.assertIn('GRATIS → PRO', auditoria.detalles)


class LandingProTests(TestCase):
    """
    Pruebas para /pro/ con precios centralizados (Criterios 14, 15).
    """
    def setUp(self):
        self.user = User.objects.create_user(
            username='musico@test.cl', email='musico@test.cl', password='password123'
        )
        PerfilPiloto.objects.create(user=self.user, tipo_cuenta='GRATIS')

    def test_pro_landing_muestra_precios_centralizados(self):
        response = self.client.get(reverse('pro'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Fogata Pro')
        self.assertContains(response, '$5.990')
        self.assertContains(response, '$9.990')
        self.assertContains(response, 'Equivale a menos de $1.000 al mes')
        self.assertContains(response, 'Próximamente')


class EventosComercialesTransactionTests(TransactionTestCase):
    """
    Pruebas de emisión de eventos comerciales con debounce y privacidad (Criterios 21, 29).
    Usa TransactionTestCase debido a hooks on_commit en registrar_evento.
    """
    def setUp(self):
        self.user_gratis = User.objects.create_user(
            username='eventos@test.cl', email='eventos@test.cl', password='password123'
        )
        PerfilPiloto.objects.create(user=self.user_gratis, tipo_cuenta='GRATIS')

    def test_visita_pro_genera_evento_comercial(self):
        self.client.login(username='eventos@test.cl', password='password123')
        response = self.client.get(reverse('pro') + '?origen=test_runner')
        self.assertEqual(response.status_code, 200)

        evento = EventoUso.objects.filter(usuario=self.user_gratis, tipo_evento='ver_pro').first()
        self.assertIsNotNone(evento)
        self.assertEqual(evento.metadata.get('origen'), 'test_runner')

        # Comprobación de privacidad: CERO información privada de música
        self.assertNotIn('letra', evento.metadata)
        self.assertNotIn('acordes', evento.metadata)
        self.assertNotIn('titulo', evento.metadata)

    def test_alcanzar_limite_canciones_genera_evento(self):
        self.client.login(username='eventos@test.cl', password='password123')
        for i in range(1, 11):
            Cancion.objects.create(propietario=self.user_gratis, titulo=f'Tema {i}', contenido='Acordes')

        response = self.client.get(reverse('canciones:crear'))
        self.assertEqual(response.status_code, 200)

        evento = EventoUso.objects.filter(usuario=self.user_gratis, tipo_evento='alcanzar_limite_canciones').first()
        self.assertIsNotNone(evento)
        self.assertEqual(evento.objeto_tipo, 'cancion')

    def test_alcanzar_limite_fogatas_genera_evento(self):
        self.client.login(username='eventos@test.cl', password='password123')
        Fogata.objects.create(propietario=self.user_gratis, nombre='Fogata 1')

        response = self.client.get(reverse('fogatas:crear'))
        self.assertEqual(response.status_code, 200)

        evento = EventoUso.objects.filter(usuario=self.user_gratis, tipo_evento='alcanzar_limite_fogatas').first()
        self.assertIsNotNone(evento)
        self.assertEqual(evento.objeto_tipo, 'fogata')


class MetricasComercialesTests(TestCase):
    """
    Pruebas para los cálculos comerciales de Control Center (Criterios 22, 23, 28).
    """
    def setUp(self):
        # Crear usuarios en distintas etapas
        self.u_gratis1 = User.objects.create_user(username='g1@t.cl', email='g1@t.cl', password='pwd')
        PerfilPiloto.objects.create(user=self.u_gratis1, tipo_cuenta='GRATIS')

        self.u_gratis2 = User.objects.create_user(username='g2@t.cl', email='g2@t.cl', password='pwd')
        PerfilPiloto.objects.create(user=self.u_gratis2, tipo_cuenta='GRATIS')

        self.u_pro = User.objects.create_user(username='pro@t.cl', email='pro@t.cl', password='pwd')
        PerfilPiloto.objects.create(user=self.u_pro, tipo_cuenta='PRO')

        # u_gratis1 tiene 10 canciones (señal de conversión)
        for i in range(10):
            Cancion.objects.create(propietario=self.u_gratis1, titulo=f'C {i}', contenido='L')

        # u_gratis2 tiene 8 canciones
        for i in range(8):
            Cancion.objects.create(propietario=self.u_gratis2, titulo=f'C2 {i}', contenido='L')

    def test_obtener_metricas_comerciales_conteos(self):
        metricas = obtener_metricas_comerciales()
        self.assertEqual(metricas['total_gratis'], 2)
        self.assertEqual(metricas['total_pro'], 1)
        self.assertEqual(metricas['gratis_10_canciones'], 1)
        self.assertEqual(metricas['gratis_8_9_canciones'], 1)
        self.assertGreaterEqual(metricas['total_senales_conversion'], 1)

        # Validar etapas del funnel comercial
        etapas = [p['etapa'] for p in metricas['funnel']]
        self.assertIn('Usuario Gratis', etapas)
        self.assertIn('8+ canciones', etapas)
        self.assertIn('Límite alcanzado', etapas)
        self.assertIn('Visitó Pro', etapas)
        self.assertIn('PRO', etapas)


class ConcurrenciaFreemiumSQLiteTests(TransactionTestCase):
    """
    Pruebas específicas de concurrencia bajo SQLite (Criterio 13 y Corrección Final Fase 8).
    Verifica que peticiones concurrentes para sobrepasar los límites de canciones (10 -> 11)
    y Fogatas (1 -> 2) sean contenidas por la validación en servidor dentro de transaction.atomic().
    """
    def setUp(self):
        self.user_concurrente_c = User.objects.create_user(
            username='concurrente_c@test.cl', email='concurrente_c@test.cl', password='password123'
        )
        PerfilPiloto.objects.create(user=self.user_concurrente_c, tipo_cuenta='GRATIS')

        # Cargar 9 canciones para estar en el umbral 9 -> 10 (concurrencia hacia la 11ª)
        for i in range(9):
            Cancion.objects.create(
                propietario=self.user_concurrente_c,
                titulo=f'Canción Base {i}',
                contenido='Contenido'
            )

        self.user_concurrente_f = User.objects.create_user(
            username='concurrente_f@test.cl', email='concurrente_f@test.cl', password='password123'
        )
        PerfilPiloto.objects.create(user=self.user_concurrente_f, tipo_cuenta='GRATIS')

    def test_concurrencia_cancion_10_a_11(self):
        """
        Intenta crear simultáneamente 4 canciones cuando el usuario ya tiene 9.
        Bajo SQLite, las peticiones concurrentes son serializadas o rechazadas por bloqueo
        de BD/transacción atómica. El total de canciones en base de datos nunca debe superar 10.
        """
        import concurrent.futures
        cliente_base = Client()
        cliente_base.login(username='concurrente_c@test.cl', password='password123')
        cookie_val = cliente_base.cookies.get(settings.SESSION_COOKIE_NAME).value

        num_hilos = 4

        def intentar_crear(indice):
            cliente = Client()
            cliente.cookies[settings.SESSION_COOKIE_NAME] = cookie_val
            try:
                return cliente.post(reverse('canciones:crear'), {
                    'titulo': f'Canción Hilo {indice}',
                    'artista': 'Test',
                    'contenido': f'Contenido Hilo {indice}',
                    'tonalidad': 'C',
                    'capo': 0
                })
            except Exception as exc:
                return exc

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_hilos) as executor:
            futuros = [executor.submit(intentar_crear, i) for i in range(num_hilos)]
            resultados = [f.result() for f in concurrent.futures.as_completed(futuros)]

        total_canciones = Cancion.objects.filter(propietario=self.user_concurrente_c).count()
        # Invariante crítico de integridad: nunca superar el límite de 10
        self.assertLessEqual(total_canciones, 10)

    def test_concurrencia_fogata_1_a_2(self):
        """
        Intenta crear simultáneamente 4 Fogatas cuando el usuario tiene 0.
        Bajo SQLite, la validación atómica y el bloqueo de BD impiden sobrepasar el límite de 1.
        El total de Fogatas nunca debe superar 1.
        """
        import concurrent.futures
        cliente_base = Client()
        cliente_base.login(username='concurrente_f@test.cl', password='password123')
        cookie_val = cliente_base.cookies.get(settings.SESSION_COOKIE_NAME).value

        num_hilos = 4

        def intentar_crear_fogata(indice):
            cliente = Client()
            cliente.cookies[settings.SESSION_COOKIE_NAME] = cookie_val
            try:
                return cliente.post(reverse('fogatas:crear'), {
                    'nombre': f'Fogata Hilo {indice}',
                    'descripcion': 'Prueba concurrente'
                })
            except Exception as exc:
                return exc

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_hilos) as executor:
            futuros = [executor.submit(intentar_crear_fogata, i) for i in range(num_hilos)]
            resultados = [f.result() for f in concurrent.futures.as_completed(futuros)]

        total_fogatas = Fogata.objects.filter(propietario=self.user_concurrente_f).count()
        # Invariante crítico de integridad: nunca superar el límite de 1
        self.assertLessEqual(total_fogatas, 1)

