import json
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.gestion.models import EventoUso
from .models import SesionEntrenamiento
from .musical import (
    OPEN_STRINGS_MIDI,
    midi_a_frecuencia,
    calcular_posiciones_exactas,
    generar_svg_mastil_posiciones,
    obtener_catalogo_notas,
    obtener_catalogo_acordes,
    obtener_catalogo_progresiones,
)

User = get_user_model()


class MusicalEngineTests(TestCase):
    """Pruebas del motor musical, afinación física y cálculo del diapasón."""

    def test_afinacion_estandar_eadgbe(self):
        """Verifica que las 6 cuerdas al aire correspondan estrictamente a EADGBE."""
        self.assertEqual(OPEN_STRINGS_MIDI[6], 40)  # E2
        self.assertEqual(OPEN_STRINGS_MIDI[5], 45)  # A2
        self.assertEqual(OPEN_STRINGS_MIDI[4], 50)  # D3
        self.assertEqual(OPEN_STRINGS_MIDI[3], 55)  # G3
        self.assertEqual(OPEN_STRINGS_MIDI[2], 59)  # B3
        self.assertEqual(OPEN_STRINGS_MIDI[1], 64)  # E4

    def test_calculo_frecuencias_hz(self):
        """Verifica el cálculo de frecuencia temperada con A4=440Hz y A3=220Hz."""
        self.assertAlmostEqual(midi_a_frecuencia(69), 440.0, places=1)
        self.assertAlmostEqual(midi_a_frecuencia(57), 220.0, places=1)
        self.assertAlmostEqual(midi_a_frecuencia(45), 110.0, places=1)

    def test_posiciones_exactas_misma_octava(self):
        """
        G3 (MIDI 55) debe encontrarse exactamente en:
        - 3ª cuerda traste 0 (55 - 55 = 0)
        - 4ª cuerda traste 5 (55 - 50 = 5)
        - 5ª cuerda traste 10 (55 - 45 = 10)
        No debe confundir octavas ni incluir posiciones imposibles.
        """
        posiciones = calcular_posiciones_exactas(55)
        self.assertEqual(len(posiciones), 3)

        pos_dict = {p.cuerda: p.traste for p in posiciones}
        self.assertEqual(pos_dict[3], 0)
        self.assertEqual(pos_dict[4], 5)
        self.assertEqual(pos_dict[5], 10)

        # Todas las posiciones deben producir exactamente MIDI 55
        for p in posiciones:
            self.assertEqual(OPEN_STRINGS_MIDI[p.cuerda] + p.traste, 55)

    def test_generador_svg_mastil(self):
        """El generador de SVG para el diapasón debe retornar SVG válido y accesible."""
        posiciones = calcular_posiciones_exactas(55)
        svg = generar_svg_mastil_posiciones(posiciones, "Sol (G3)")
        self.assertIn('<svg', svg)
        self.assertIn('role="img"', svg)
        self.assertIn('mastil-posiciones-svg', svg)
        self.assertIn('</svg>', svg)

    def test_catalogo_notas_completo(self):
        """El catálogo de notas debe proveer notas naturales para Gratis y catálogo completo para Pro."""
        catalogo_gratis = obtener_catalogo_notas(solo_gratis=True)
        self.assertEqual(len(catalogo_gratis), 10)
        # Las 7 notas naturales deben estar presentes en el catálogo gratuito
        nombres_raiz = set(n.nombre_latino.split()[0] for n in catalogo_gratis)
        self.assertEqual(nombres_raiz, {'Do', 'Re', 'Mi', 'Fa', 'Sol', 'La', 'Si'})
        for n in catalogo_gratis:
            self.assertFalse(n.es_pro)
            self.assertTrue(len(n.posiciones) >= 2)
            self.assertTrue(n.frecuencia > 100)
            self.assertIn('<svg', n.fretboard_svg)

        catalogo_pro = obtener_catalogo_notas(solo_gratis=False)
        self.assertEqual(len(catalogo_pro), 21)
        codigos_pro = {n.id for n in catalogo_pro}
        self.assertIn('F#3', codigos_pro)
        self.assertIn('C#4', codigos_pro)
        self.assertIn('A4', codigos_pro)
        self.assertIn('A2', codigos_pro)

    def test_catalogo_acordes_8_esenciales(self):
        """
        Verifica los 8 acordes estándar (C, G, D, A, E, Am, Em, Dm) para Gratis
        y el catálogo completo de 18 acordes (con cejillas y séptimas) para Pro.
        """
        catalogo_gratis = obtener_catalogo_acordes(solo_gratis=True)
        self.assertEqual(len(catalogo_gratis), 8)
        codigos = [a.codigo for a in catalogo_gratis]
        self.assertEqual(codigos, ['C', 'G', 'D', 'A', 'E', 'Am', 'Em', 'Dm'])

        for ac in catalogo_gratis:
            self.assertFalse(ac.es_pro)
            self.assertEqual(len(ac.trastes_referencia), 6)
            self.assertEqual(len(ac.trastes_alternativa), 6)
            self.assertIn('<svg', ac.svg_referencia)
            self.assertIn('<svg', ac.svg_alternativa)
            self.assertTrue(len(ac.notas_componentes) > 0)
            self.assertTrue(len(ac.descripcion_alternativa) > 0)

        catalogo_pro = obtener_catalogo_acordes(solo_gratis=False)
        self.assertEqual(len(catalogo_pro), 18)
        codigos_pro = [a.codigo for a in catalogo_pro]
        for c_esperado in ['F', 'B', 'Bm', 'F#m', 'C7', 'D7', 'G7', 'A7', 'E7', 'B7']:
            self.assertIn(c_esperado, codigos_pro)

    def test_catalogo_progresiones_armonicas(self):
        """Verifica las progresiones de 2 acordes para Gratis y el catálogo completo (2, 3 y 4) para Pro."""
        catalogo_gratis = obtener_catalogo_progresiones(solo_gratis=True)
        self.assertEqual(len(catalogo_gratis), 8)
        for prog in catalogo_gratis:
            self.assertFalse(prog.es_pro)
            self.assertEqual(len(prog.acordes), 2)
            self.assertEqual(len(prog.diagramas_svg), 2)
            self.assertEqual(len(prog.audio_chords), 2)
            self.assertIn('→', prog.acordes_str)
            self.assertTrue(len(prog.explicacion) > 10)

        catalogo_pro = obtener_catalogo_progresiones(solo_gratis=False)
        self.assertEqual(len(catalogo_pro), 25)
        longitudes = set(len(p.acordes) for p in catalogo_pro)
        self.assertEqual(longitudes, {2, 3, 4})


class EntrenamientoViewsTests(TestCase):
    """Pruebas de vistas, autenticación, control de activación y experiencia."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='guitarrista@test.com',
            email='guitarrista@test.com',
            password='password123'
        )
        self.url_portada = reverse('entrenamiento:portada')
        self.url_notas = reverse('entrenamiento:notas')
        self.url_acordes = reverse('entrenamiento:acordes')
        self.url_progresiones = reverse('entrenamiento:progresiones')
        self.url_api = reverse('entrenamiento:api_evento')

    def test_requiere_autenticacion(self):
        """Usuarios no autenticados son redirigidos al login."""
        r1 = self.client.get(self.url_portada)
        self.assertEqual(r1.status_code, 302)
        self.assertIn(reverse('core:login'), r1.url)

        r2 = self.client.get(self.url_notas)
        self.assertEqual(r2.status_code, 302)

        r3 = self.client.get(self.url_acordes)
        self.assertEqual(r3.status_code, 302)

        r4 = self.client.get(self.url_progresiones)
        self.assertEqual(r4.status_code, 302)

    def test_portada_usuario_autenticado(self):
        """Usuario autenticado accede a la portada y se registra métrica de acceso."""
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.get(self.url_portada)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'entrenamiento/portada.html')
        self.assertContains(resp, 'Entrena tu oído')
        self.assertContains(resp, 'Escucha. Encuentra. Toca.')
        self.assertContains(resp, 'Notas')
        self.assertContains(resp, 'Acordes')
        self.assertContains(resp, 'Progresiones')

        # Comprobar evento de uso registrado
        evento = EventoUso.objects.filter(usuario=self.user, tipo_evento='acceder_entrenamiento').first()
        self.assertIsNotNone(evento)

    def test_entrenar_notas_inicia_sesion(self):
        """La vista de notas crea una sesión de 5 ejercicios."""
        self.client.force_login(self.user)
        resp = self.client.get(self.url_notas)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'entrenamiento/ejercicio_notas.html')
        self.assertContains(resp, 'Encuentra la nota')

        sesion = SesionEntrenamiento.objects.filter(usuario=self.user, modalidad='notas').first()
        self.assertIsNotNone(sesion)
        self.assertEqual(sesion.total_ejercicios, 5)
        self.assertFalse(sesion.completada)

    def test_entrenar_acordes_inicia_sesion(self):
        """La vista de acordes crea una sesión de 5 ejercicios."""
        self.client.force_login(self.user)
        resp = self.client.get(self.url_acordes)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'entrenamiento/ejercicio_acordes.html')
        self.assertContains(resp, 'Encuentra el acorde')

        sesion = SesionEntrenamiento.objects.filter(usuario=self.user, modalidad='acordes').first()
        self.assertIsNotNone(sesion)
        self.assertEqual(sesion.total_ejercicios, 5)

    def test_entrenar_progresiones_inicia_sesion(self):
        """La vista de progresiones crea una sesión de 5 ejercicios."""
        self.client.force_login(self.user)
        resp = self.client.get(self.url_progresiones)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'entrenamiento/ejercicio_progresiones.html')
        self.assertContains(resp, 'Sigue la progresión')

        sesion = SesionEntrenamiento.objects.filter(usuario=self.user, modalidad='progresiones').first()
        self.assertIsNotNone(sesion)
        self.assertEqual(sesion.total_ejercicios, 5)

    @override_settings(FOGATA_EAR_TRAINING_ENABLED=False)
    def test_desactivacion_controlada_feature_flag(self):
        """Cuando FOGATA_EAR_TRAINING_ENABLED=False, los endpoints arrojan 404."""
        self.client.force_login(self.user)
        r1 = self.client.get(self.url_portada)
        self.assertEqual(r1.status_code, 404)

        r2 = self.client.get(self.url_notas)
        self.assertEqual(r2.status_code, 404)

        r3 = self.client.get(self.url_acordes)
        self.assertEqual(r3.status_code, 404)

        r4 = self.client.get(self.url_progresiones)
        self.assertEqual(r4.status_code, 404)

        # En la navegación principal no debe aparecer el enlace
        r_home = self.client.get(reverse('core:home'))
        self.assertNotContains(r_home, 'Entrena tu oído')

    def test_enlace_navegacion_visible_cuando_activo(self):
        """Cuando el módulo está activo y el usuario autenticado, el link aparece en nav."""
        self.client.force_login(self.user)
        resp = self.client.get(reverse('canciones:lista'))
        self.assertContains(resp, 'Entrena tu oído')
        # Verificar elementos fijos móviles y botón sandwich
        self.assertContains(resp, 'id="btn-menu-sandwich"')
        self.assertContains(resp, 'class="nav-direct-mobile"')
        self.assertContains(resp, 'id="menu-desplegable-sandwich"')

    def test_api_eventos_telemetria_y_autoevaluacion(self):
        """Prueba del ciclo de vida de eventos vía API JSON."""
        self.client.force_login(self.user)
        sesion = SesionEntrenamiento.objects.create(
            usuario=self.user,
            modalidad='acordes',
            total_ejercicios=5
        )

        # 1. Reproducir audio
        resp1 = self.client.post(
            self.url_api,
            data=json.dumps({
                'tipo': 'reproducir_audio',
                'modalidad': 'acordes',
                'sesion_id': sesion.pk,
                'es_repeticion': False
            }),
            content_type='application/json'
        )
        self.assertEqual(resp1.status_code, 200)

        # 2. Revelar respuesta
        resp2 = self.client.post(
            self.url_api,
            data=json.dumps({
                'tipo': 'revelar_respuesta',
                'modalidad': 'acordes',
                'sesion_id': sesion.pk,
                'ejercicio_num': 1
            }),
            content_type='application/json'
        )
        self.assertEqual(resp2.status_code, 200)

        # 3. Autoevaluación voluntaria: "encontre"
        resp3 = self.client.post(
            self.url_api,
            data=json.dumps({
                'tipo': 'autoevaluacion',
                'modalidad': 'acordes',
                'sesion_id': sesion.pk,
                'resultado': 'encontre'
            }),
            content_type='application/json'
        )
        self.assertEqual(resp3.status_code, 200)

        sesion.refresh_from_db()
        self.assertEqual(sesion.ejercicios_completados, 1)
        self.assertEqual(sesion.aciertos_declarados, 1)

        # 4. Completar sesión
        resp4 = self.client.post(
            self.url_api,
            data=json.dumps({
                'tipo': 'completar_sesion',
                'modalidad': 'acordes',
                'sesion_id': sesion.pk,
                'total_ejercicios': 5,
                'aciertos_declarados': 1
            }),
            content_type='application/json'
        )
        self.assertEqual(resp4.status_code, 200)

        sesion.refresh_from_db()
        self.assertTrue(sesion.completada)
        self.assertIsNotNone(sesion.finalizada_el)

    def test_usuario_plan_pro_y_gratis_acceso_total(self):
        """Criterio 11: Tanto usuarios Gratis como Pro tienen acceso completo sin restricciones."""
        # 1. Usuario Gratis
        self.client.force_login(self.user)
        resp_gratis = self.client.get(self.url_acordes)
        self.assertEqual(resp_gratis.status_code, 200)

        # 2. Usuario Pro
        from apps.core.models import PerfilPiloto
        from django.utils import timezone
        from datetime import timedelta
        user_pro = User.objects.create_user(
            username='pro_musico@test.com',
            email='pro_musico@test.com',
            password='PasswordPro123!'
        )
        PerfilPiloto.objects.create(
            user=user_pro,
            codigo_invitacion='PRO_EAR_TRAIN',
            tipo_cuenta='PRO',
            fecha_fin_plan=timezone.now() + timedelta(days=30)
        )
        self.client.force_login(user_pro)
        resp_pro = self.client.get(self.url_acordes)
        self.assertEqual(resp_pro.status_code, 200)

    def test_api_json_invalido_retorna_400(self):
        """Si el payload no es JSON válido, el endpoint API retorna HTTP 400."""
        self.client.force_login(self.user)
        resp = self.client.post(
            self.url_api,
            data="no es un json",
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertFalse(data['ok'])

    def test_autoevaluacion_seguir_practicando(self):
        """La autoevaluación 'practicar' incrementa ejercicios completados pero no aciertos."""
        self.client.force_login(self.user)
        sesion = SesionEntrenamiento.objects.create(
            usuario=self.user,
            modalidad='notas',
            total_ejercicios=5
        )
        resp = self.client.post(
            self.url_api,
            data=json.dumps({
                'tipo': 'autoevaluacion',
                'modalidad': 'notas',
                'sesion_id': sesion.pk,
                'resultado': 'practicar'
            }),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        sesion.refresh_from_db()
        self.assertEqual(sesion.ejercicios_completados, 1)
        self.assertEqual(sesion.aciertos_declarados, 0)

    def test_diferenciacion_gratis_y_pro_en_vistas(self):
        """
        Verifica que:
        - Usuario Gratis solo recibe ejercicios con es_pro=False (notas naturales, 8 acordes, 2 acordes progresiones).
        - Usuario Pro activo recibe ejercicios del catálogo completo.
        - Usuario Pro vencido regresa automáticamente a las restricciones de Gratis.
        """
        from apps.core.models import PerfilPiloto
        from datetime import timedelta
        from django.utils import timezone

        # 1. Usuario Gratis
        user_gratis = User.objects.create_user(
            username='gratis_musico@test.com',
            email='gratis_musico@test.com',
            password='Password123!'
        )
        PerfilPiloto.objects.create(user=user_gratis, tipo_cuenta='GRATIS')

        self.client.force_login(user_gratis)

        resp_notas = self.client.get(self.url_notas)
        ejercicios_notas = json.loads(resp_notas.context['ejercicios_json'])
        for ej in ejercicios_notas:
            self.assertFalse(ej['es_pro'])

        resp_acordes = self.client.get(self.url_acordes)
        ejercicios_acordes = json.loads(resp_acordes.context['ejercicios_json'])
        for ej in ejercicios_acordes:
            self.assertFalse(ej['es_pro'])
            self.assertIn(ej['codigo'], ['C', 'G', 'D', 'A', 'E', 'Am', 'Em', 'Dm'])

        resp_progs = self.client.get(self.url_progresiones)
        ejercicios_progs = json.loads(resp_progs.context['ejercicios_json'])
        for ej in ejercicios_progs:
            self.assertFalse(ej['es_pro'])
            self.assertEqual(len(ej['acordes']), 2)

        # 2. Usuario Pro Activo
        user_pro = User.objects.create_user(
            username='pro_activo@test.com',
            email='pro_activo@test.com',
            password='Password123!'
        )
        PerfilPiloto.objects.create(
            user=user_pro,
            tipo_cuenta='PRO',
            fecha_fin_plan=timezone.now() + timedelta(days=30)
        )
        self.client.force_login(user_pro)
        resp_pro_notas = self.client.get(self.url_notas)
        self.assertTrue(resp_pro_notas.context['es_pro'])

        # 3. Usuario Pro Vencido (degradado a Gratis en tiempo real)
        user_vencido = User.objects.create_user(
            username='pro_vencido@test.com',
            email='pro_vencido@test.com',
            password='Password123!'
        )
        PerfilPiloto.objects.create(
            user=user_vencido,
            tipo_cuenta='PRO',
            fecha_fin_plan=timezone.now() - timedelta(days=1)
        )
        self.client.force_login(user_vencido)
        resp_vencido_notas = self.client.get(self.url_notas)
        self.assertFalse(resp_vencido_notas.context['es_pro'])
        ejercicios_vencido = json.loads(resp_vencido_notas.context['ejercicios_json'])
        for ej in ejercicios_vencido:
            self.assertFalse(ej['es_pro'])

    def test_seguridad_servidor_evita_bypasses_a_pro(self):
        """Un usuario Gratis no puede obtener contenido Pro manipulando query parameters."""
        from apps.core.models import PerfilPiloto
        user_gratis = User.objects.create_user(
            username='hacker_gratis@test.com',
            email='hacker_gratis@test.com',
            password='Password123!'
        )
        PerfilPiloto.objects.create(user=user_gratis, tipo_cuenta='GRATIS')
        self.client.force_login(user_gratis)

        resp = self.client.get(self.url_acordes + '?nivel=pro&modo=avanzado')
        self.assertFalse(resp.context['es_pro'])
        ejercicios = json.loads(resp.context['ejercicios_json'])
        for ej in ejercicios:
            self.assertFalse(ej['es_pro'])
            self.assertIn(ej['codigo'], ['C', 'G', 'D', 'A', 'E', 'Am', 'Em', 'Dm'])

    def test_pagina_login_como_entrada_comercial_publica(self):
        """La página de login muestra el formulario arriba y la presentación comercial abajo."""
        # 1. Acceso a /login/
        resp = self.client.get(reverse('core:login'))
        self.assertEqual(resp.status_code, 200)
        # Formulario arriba
        self.assertContains(resp, 'name="email"')
        self.assertContains(resp, 'name="password"')
        self.assertContains(resp, 'Olvidé mi contraseña')
        self.assertContains(resp, 'Tus canciones. Tus acordes. Tu sesión.')
        # Secciones comerciales abajo
        self.assertContains(resp, 'Más guitarra. Menos distracciones.')
        self.assertContains(resp, '¿Y si cada vez necesitaras mirar menos la pantalla?')
        self.assertContains(resp, 'Escucha')
        self.assertContains(resp, 'Encuentra')
        self.assertContains(resp, 'Revela')
        self.assertContains(resp, 'Sigue tocando')
        self.assertContains(resp, '¿Para quién es Fogata?')
        self.assertContains(resp, 'Empieza gratis. Avanza cuando quieras.')
        self.assertContains(resp, 'FOGATA GRATIS')
        self.assertContains(resp, 'FOGATA PRO')
        self.assertContains(resp, '5.990')
        self.assertContains(resp, '9.990')
        self.assertContains(resp, 'Toca. Practica. Disfruta.')
        self.assertContains(resp, 'fogata.humm.cl')

        # 2. Acceso anónimo a / (home) muestra la entrada unificada
        resp_home = self.client.get(reverse('core:home'))
        self.assertEqual(resp_home.status_code, 200)
        self.assertContains(resp_home, 'name="email"')
        self.assertContains(resp_home, 'Tus canciones. Tus acordes. Tu sesión.')

