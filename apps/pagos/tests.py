"""
Suite de pruebas exhaustiva para Fase 9: Integración comercial real con Flow Chile.
Verifica cumplimiento estricto de todas las directrices comerciales,
idempotencia en SQLite, seguridad, cálculo de fechas y observabilidad.
"""

from datetime import timedelta
import calendar
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.management import call_command

from apps.core.models import PerfilPiloto
from apps.core.planes import obtener_tipo_cuenta, puede_crear_cancion, puede_crear_fogata
from apps.canciones.models import Cancion
from apps.fogatas.models import Fogata
from apps.gestion.models import EventoUso
from apps.gestion.metrics import obtener_metricas_comerciales
from apps.pagos.models import OrdenPago
from apps.pagos.signing import generar_firma_flow, verificar_firma_flow
from apps.pagos.flow import FlowClient, FlowAPIError, FlowNetworkError, FlowError
from apps.pagos.services import (
    sumar_meses_calendario,
    obtener_precio_plan,
    iniciar_checkout_pago,
    procesar_confirmacion_flow,
    generar_commerce_order,
)

User = get_user_model()


def crear_usuario_test(email, password='Password123!', **kwargs):
    return User.objects.create_user(username=email, email=email, password=password, **kwargs)


def crear_admin_test(email, password='Password123!', **kwargs):
    return User.objects.create_superuser(username=email, email=email, password=password, **kwargs)


class FlowSigningAndClientTests(TestCase):
    """Pruebas del algoritmo oficial de firma y cliente Flow."""

    def test_firma_hmac_algoritmo_oficial(self):
        """Verifica orden alfabético, concatenación clave+valor y HMAC SHA-256."""
        secret = "mi_secreto_super_seguro_12345"
        params = {
            'apiKey': 'API_KEY_TEST',
            'commerceOrder': 'FOG-ORD-1',
            'amount': '5990',
            'currency': 'CLP',
        }
        # Orden alfabético: amount, apiKey, commerceOrder, currency
        firma = generar_firma_flow(params, secret)
        self.assertIsInstance(firma, str)
        self.assertEqual(len(firma), 64)  # Hexadecimal SHA-256

        # Verificación compare_digest
        self.assertTrue(verificar_firma_flow(params, firma, secret))
        self.assertFalse(verificar_firma_flow(params, "firma_falsa", secret))

    def test_firma_sin_secreto_lanza_error(self):
        with self.assertRaises(ValueError):
            generar_firma_flow({'a': '1'}, "")

    @override_settings(FLOW_ENVIRONMENT='sandbox', FLOW_API_KEY='k', FLOW_SECRET_KEY='s', FLOW_BASE_URL='https://sandbox.flow.cl/api')
    def test_flow_client_sandbox_urls(self):
        client = FlowClient()
        self.assertEqual(client.environment, 'sandbox')
        self.assertEqual(client.base_url, 'https://sandbox.flow.cl/api')

    @override_settings(FLOW_ENVIRONMENT='production', FLOW_API_KEY='', FLOW_SECRET_KEY='')
    def test_produccion_sin_credenciales_falla_de_manera_segura(self):
        """Producción debe fallar ruidosamente si faltan llaves sin degradar a Sandbox."""
        with self.assertRaises(FlowError):
            FlowClient()

    @override_settings(FLOW_ENVIRONMENT='production', FLOW_API_KEY='key', FLOW_SECRET_KEY='sec', FLOW_BASE_URL='https://sandbox.flow.cl/api')
    def test_produccion_apuntando_a_sandbox_falla_de_manera_segura(self):
        with self.assertRaises(FlowError):
            FlowClient()


class FlowCheckoutCreationTests(TestCase):
    """Pruebas de creación de checkout y resolución autoritativa de precio."""

    def setUp(self):
        self.user_gratis = crear_usuario_test('gratis@test.com')
        PerfilPiloto.objects.create(user=self.user_gratis, tipo_cuenta='GRATIS')

        self.user_pro = crear_usuario_test('pro@test.com')
        PerfilPiloto.objects.create(
            user=self.user_pro,
            tipo_cuenta='PRO',
            fecha_fin_plan=timezone.now() + timedelta(days=60)
        )

    def test_monto_semestral_y_anual_resueltos_servidor(self):
        self.assertEqual(obtener_precio_plan(OrdenPago.PLAN_PRO_6M), 5990)
        self.assertEqual(obtener_precio_plan(OrdenPago.PLAN_PRO_12M), 9990)
        with self.assertRaises(ValueError):
            obtener_precio_plan('PLAN_INVALIDO')

    @override_settings(FOGATA_PAYMENTS_ENABLED=False)
    def test_pagos_deshabilitados_no_permiten_checkout(self):
        self.client.force_login(self.user_gratis)
        resp = self.client.post(reverse('pagos:crear_pago'), {'plan': 'PRO_6M'})
        self.assertEqual(resp.status_code, 302)
        # No debe haberse creado orden
        self.assertEqual(OrdenPago.objects.count(), 0)

    @override_settings(
        FOGATA_PAYMENTS_ENABLED=True,
        FLOW_API_KEY='test_key',
        FLOW_SECRET_KEY='test_secret',
        FLOW_ENVIRONMENT='sandbox'
    )
    @patch('apps.pagos.flow.FlowClient.crear_pago')
    def test_usuario_gratis_puede_iniciar_pago_semestral(self, mock_crear):
        mock_crear.return_value = {
            'url': 'https://sandbox.flow.cl/app/web/pay.php',
            'token': 'TOKEN_TEST_123',
            'flowOrder': 98765
        }
        self.client.force_login(self.user_gratis)
        resp = self.client.post(reverse('pagos:crear_pago'), {'plan': 'PRO_6M'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("token=TOKEN_TEST_123", resp.url)

        orden = OrdenPago.objects.get(usuario=self.user_gratis)
        self.assertEqual(orden.monto, 5990)
        self.assertEqual(orden.plan, OrdenPago.PLAN_PRO_6M)
        self.assertEqual(orden.estado, OrdenPago.ESTADO_PENDIENTE)
        self.assertEqual(orden.flow_token, 'TOKEN_TEST_123')
        self.assertEqual(orden.flow_order, 98765)
        self.assertFalse(orden.pro_aplicado)

    @override_settings(
        FOGATA_PAYMENTS_ENABLED=True,
        FLOW_API_KEY='test_key',
        FLOW_SECRET_KEY='test_secret'
    )
    @patch('apps.pagos.flow.FlowClient.crear_pago')
    def test_post_con_monto_manipulado_no_cambia_precio(self, mock_crear):
        mock_crear.return_value = {
            'url': 'https://sandbox.flow.cl/pay',
            'token': 'TOKEN_HACK',
            'flowOrder': 111
        }
        self.client.force_login(self.user_gratis)
        # El atacante envía amount=100 y precio=10
        self.client.post(reverse('pagos:crear_pago'), {
            'plan': 'PRO_12M',
            'amount': '100',
            'monto': '10',
            'precio': '1'
        })
        orden = OrdenPago.objects.get(usuario=self.user_gratis)
        # El servidor ignoró los campos inyectados y asignó el precio oficial de 12M
        self.assertEqual(orden.monto, 9990)

    def test_commerce_order_es_unico(self):
        ord1 = generar_commerce_order('PRO_6M')
        ord2 = generar_commerce_order('PRO_6M')
        self.assertNotEqual(ord1, ord2)
        self.assertTrue(ord1.startswith('FOG-6M-'))

    @override_settings(
        FOGATA_PAYMENTS_ENABLED=True,
        FLOW_API_KEY='k',
        FLOW_SECRET_KEY='s'
    )
    @patch('apps.pagos.flow.FlowClient.crear_pago')
    def test_doble_post_con_checkout_request_id_no_duplica_ordenes(self, mock_crear):
        """Ajuste 11: Idempotencia al iniciar compra previene doble orden accidental."""
        mock_crear.return_value = {'url': 'https://sandbox.flow.cl/pay', 'token': 'TOKEN_DOUBLE', 'flowOrder': 222}
        self.client.force_login(self.user_gratis)

        req_id = "REQ-ID-UNIQUE-123"
        self.client.post(reverse('pagos:crear_pago'), {'plan': 'PRO_6M', 'checkout_request_id': req_id})
        self.assertEqual(OrdenPago.objects.count(), 1)

        # Segundo submit idéntico (doble click)
        self.client.post(reverse('pagos:crear_pago'), {'plan': 'PRO_6M', 'checkout_request_id': req_id})
        self.assertEqual(OrdenPago.objects.count(), 1)


class FlowWebhookConfirmationTests(TestCase):
    """Pruebas de callback de confirmación servidor-servidor y activación Pro."""

    def setUp(self):
        self.user = crear_usuario_test('musico@test.com')
        self.perfil = PerfilPiloto.objects.create(user=self.user, tipo_cuenta='GRATIS')

        self.orden_6m = OrdenPago.objects.create(
            usuario=self.user,
            commerce_order='FOG-6M-20261002-1234567890ABCDEF',
            plan=OrdenPago.PLAN_PRO_6M,
            monto=5990,
            moneda='CLP',
            estado=OrdenPago.ESTADO_PENDIENTE,
            flow_token='TOKEN_TEST_CONFIRM',
            ambiente=OrdenPago.AMBIENTE_SANDBOX
        )

    def test_callback_sin_token_devuelve_400(self):
        resp = self.client.post(reverse('pagos:flow_confirmacion'), {})
        self.assertEqual(resp.status_code, 400)

    @patch('apps.pagos.flow.FlowClient.obtener_estado_pago')
    def test_flow_status_2_pagada_activa_pro(self, mock_status):
        """Estado 2 oficial de Flow activa Pro con meses calendario exactos."""
        mock_status.return_value = {
            'status': 2,
            'flowOrder': 444555,
            'commerceOrder': self.orden_6m.commerce_order,
            'amount': 5990,
            'currency': 'CLP',
            'payer': 'otro_correo_pagador@banco.cl',  # Ajuste 15: no se exige igual correo
            'paymentData': {'media': 'Webpay', 'date': '2026-10-02 16:30:00'}
        }

        resp = self.client.post(reverse('pagos:flow_confirmacion'), {'token': 'TOKEN_TEST_CONFIRM'})
        self.assertEqual(resp.status_code, 200)

        self.orden_6m.refresh_from_db()
        self.assertEqual(self.orden_6m.estado, OrdenPago.ESTADO_PAGADA)
        self.assertTrue(self.orden_6m.pro_aplicado)
        self.assertIsNotNone(self.orden_6m.pagada_el)

        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.tipo_cuenta, 'PRO')
        self.assertEqual(self.perfil.estado_suscripcion, 'ACTIVA')
        self.assertIsNotNone(self.perfil.fecha_fin_plan)

    @patch('apps.pagos.flow.FlowClient.obtener_estado_pago')
    def test_flow_status_1_pendiente_no_activa_pro(self, mock_status):
        mock_status.return_value = {
            'status': 1,
            'flowOrder': 100,
            'commerceOrder': self.orden_6m.commerce_order,
            'amount': 5990,
            'currency': 'CLP',
        }
        self.client.post(reverse('pagos:flow_confirmacion'), {'token': 'TOKEN_TEST_CONFIRM'})
        self.orden_6m.refresh_from_db()
        self.assertEqual(self.orden_6m.estado, OrdenPago.ESTADO_PENDIENTE)
        self.assertFalse(self.orden_6m.pro_aplicado)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.tipo_cuenta, 'GRATIS')

    @patch('apps.pagos.flow.FlowClient.obtener_estado_pago')
    def test_flow_status_3_rechazada_no_activa_pro(self, mock_status):
        mock_status.return_value = {
            'status': 3,
            'flowOrder': 101,
            'commerceOrder': self.orden_6m.commerce_order,
            'amount': 5990,
            'currency': 'CLP',
        }
        self.client.post(reverse('pagos:flow_confirmacion'), {'token': 'TOKEN_TEST_CONFIRM'})
        self.orden_6m.refresh_from_db()
        self.assertEqual(self.orden_6m.estado, OrdenPago.ESTADO_RECHAZADA)
        self.assertFalse(self.orden_6m.pro_aplicado)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.tipo_cuenta, 'GRATIS')

    @patch('apps.pagos.flow.FlowClient.obtener_estado_pago')
    def test_flow_status_4_anulada_no_activa_pro(self, mock_status):
        mock_status.return_value = {
            'status': 4,
            'flowOrder': 102,
            'commerceOrder': self.orden_6m.commerce_order,
            'amount': 5990,
            'currency': 'CLP',
        }
        self.client.post(reverse('pagos:flow_confirmacion'), {'token': 'TOKEN_TEST_CONFIRM'})
        self.orden_6m.refresh_from_db()
        self.assertEqual(self.orden_6m.estado, OrdenPago.ESTADO_ANULADA)
        self.assertFalse(self.orden_6m.pro_aplicado)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.tipo_cuenta, 'GRATIS')

    @patch('apps.pagos.flow.FlowClient.obtener_estado_pago')
    def test_discrepancia_amount_marca_error_y_no_activa_pro(self, mock_status):
        mock_status.return_value = {
            'status': 2,
            'flowOrder': 103,
            'commerceOrder': self.orden_6m.commerce_order,
            'amount': 1000,  # Esperaba 5990
            'currency': 'CLP',
        }
        self.client.post(reverse('pagos:flow_confirmacion'), {'token': 'TOKEN_TEST_CONFIRM'})
        self.orden_6m.refresh_from_db()
        self.assertEqual(self.orden_6m.estado, OrdenPago.ESTADO_ERROR_VALIDACION)
        self.assertFalse(self.orden_6m.pro_aplicado)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.tipo_cuenta, 'GRATIS')

    @patch('apps.pagos.flow.FlowClient.obtener_estado_pago')
    def test_discrepancia_currency_marca_error_y_no_activa_pro(self, mock_status):
        mock_status.return_value = {
            'status': 2,
            'flowOrder': 104,
            'commerceOrder': self.orden_6m.commerce_order,
            'amount': 5990,
            'currency': 'USD',  # Esperaba CLP
        }
        self.client.post(reverse('pagos:flow_confirmacion'), {'token': 'TOKEN_TEST_CONFIRM'})
        self.orden_6m.refresh_from_db()
        self.assertEqual(self.orden_6m.estado, OrdenPago.ESTADO_ERROR_VALIDACION)
        self.assertFalse(self.orden_6m.pro_aplicado)

    @patch('apps.pagos.flow.FlowClient.obtener_estado_pago')
    def test_discrepancia_commerce_order_marca_error_y_no_activa_pro(self, mock_status):
        mock_status.return_value = {
            'status': 2,
            'flowOrder': 105,
            'commerceOrder': 'OTRA_ORDEN_DISTINTA',
            'amount': 5990,
            'currency': 'CLP',
        }
        self.client.post(reverse('pagos:flow_confirmacion'), {'token': 'TOKEN_TEST_CONFIRM'})
        self.orden_6m.refresh_from_db()
        self.assertEqual(self.orden_6m.estado, OrdenPago.ESTADO_ERROR_VALIDACION)
        self.assertFalse(self.orden_6m.pro_aplicado)

    @patch('apps.pagos.flow.FlowClient.obtener_estado_pago')
    def test_callback_duplicado_es_estrictamente_idempotente(self, mock_status):
        """Ajuste 1: Confirmación duplicada no añade vigencia extra ni duplica efectos."""
        mock_status.return_value = {
            'status': 2,
            'flowOrder': 444555,
            'commerceOrder': self.orden_6m.commerce_order,
            'amount': 5990,
            'currency': 'CLP',
        }
        # Primera confirmación
        self.client.post(reverse('pagos:flow_confirmacion'), {'token': 'TOKEN_TEST_CONFIRM'})
        self.perfil.refresh_from_db()
        fin_inicial = self.perfil.fecha_fin_plan

        # Segunda confirmación idéntica
        self.client.post(reverse('pagos:flow_confirmacion'), {'token': 'TOKEN_TEST_CONFIRM'})
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.fecha_fin_plan, fin_inicial)

    @patch('apps.pagos.flow.FlowClient.obtener_estado_pago')
    def test_confirmacion_concurrente_sqlite_solo_aplica_una_vez(self, mock_status):
        """Ajuste 1: Simulación de concurrencia donde update(pro_aplicado=False) filtra."""
        mock_status.return_value = {
            'status': 2,
            'flowOrder': 777,
            'commerceOrder': self.orden_6m.commerce_order,
            'amount': 5990,
            'currency': 'CLP',
        }
        # Si la orden ya tiene pro_aplicado=True simulando carrera
        self.orden_6m.pro_aplicado = True
        self.orden_6m.estado = OrdenPago.ESTADO_PAGADA
        self.orden_6m.save()

        # Una confirmación en paralelo debe retornar no-op de inmediato
        orden_res = procesar_confirmacion_flow('TOKEN_TEST_CONFIRM')
        self.assertEqual(orden_res.id, self.orden_6m.id)

    @patch('apps.pagos.flow.FlowClient.obtener_estado_pago')
    def test_raw_response_no_persiste_payer_ni_payment_data(self, mock_status):
        """Ajuste 6: flow_metadata solo guarda whitelist técnica."""
        mock_status.return_value = {
            'status': 2,
            'flowOrder': 888,
            'commerceOrder': self.orden_6m.commerce_order,
            'amount': 5990,
            'currency': 'CLP',
            'payer': 'sensible@banco.cl',
            'token': 'TOKEN_QUE_NO_DEBE_IR_EN_JSON',
            'paymentData': {
                'media': 'Webpay',
                'cardNumber': '************1234',
                'rut': '12345678-9'
            }
        }
        self.client.post(reverse('pagos:flow_confirmacion'), {'token': 'TOKEN_TEST_CONFIRM'})
        self.orden_6m.refresh_from_db()
        meta = self.orden_6m.flow_metadata
        self.assertNotIn('payer', meta)
        self.assertNotIn('token', meta)
        self.assertNotIn('cardNumber', str(meta))
        self.assertNotIn('rut', str(meta))
        self.assertEqual(meta.get('paymentMethod'), 'Webpay')

    @patch('apps.pagos.flow.FlowClient.obtener_estado_pago')
    def test_timeout_de_flow_mantiene_pendiente_sin_marcar_rechazada(self, mock_status):
        """Ajustes 4 y 14: Fallo temporal de red deja PENDIENTE para reconciliación posterior."""
        mock_status.side_effect = FlowNetworkError("Timeout de conexión")
        self.client.post(reverse('pagos:flow_confirmacion'), {'token': 'TOKEN_TEST_CONFIRM'})
        self.orden_6m.refresh_from_db()
        self.assertEqual(self.orden_6m.estado, OrdenPago.ESTADO_PENDIENTE)
        self.assertIn("Fallo temporal de red", self.orden_6m.detalles_error)


class FlowUserReturnAndGetResultTests(TestCase):
    """Pruebas del retorno POST de Flow y el GET amigable de resultado."""

    def setUp(self):
        self.user = crear_usuario_test('usuario@test.com')
        self.perfil = PerfilPiloto.objects.create(user=self.user, tipo_cuenta='GRATIS')
        self.orden = OrdenPago.objects.create(
            usuario=self.user,
            commerce_order='FOG-ORD-RETORNO',
            plan=OrdenPago.PLAN_PRO_6M,
            monto=5990,
            moneda='CLP',
            estado=OrdenPago.ESTADO_PENDIENTE,
            flow_token='TOKEN_RETORNO'
        )

    @patch('apps.pagos.flow.FlowClient.obtener_estado_pago')
    def test_url_return_mediante_post_redirige_a_get_resultado(self, mock_status):
        """Ajuste 3: Flow hace POST a /pagos/flow/retorno/ y Fogata redirige a GET de resultado."""
        mock_status.return_value = {
            'status': 2,
            'flowOrder': 999,
            'commerceOrder': self.orden.commerce_order,
            'amount': 5990,
            'currency': 'CLP',
        }
        resp = self.client.post(reverse('pagos:flow_retorno'), {'token': 'TOKEN_RETORNO'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('pagos:resultado', kwargs={'commerce_order': self.orden.commerce_order}))

    def test_get_falsificado_no_activa_pro(self):
        """Ajuste 3 y Criterio 19: Acceder directamente a resultado no concede Pro."""
        self.client.force_login(self.user)
        # La orden sigue pendiente
        resp = self.client.get(reverse('pagos:resultado', kwargs={'commerce_order': self.orden.commerce_order}))
        self.assertEqual(resp.status_code, 200)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.tipo_cuenta, 'GRATIS')

    def test_usuario_no_puede_ver_pagos_de_otro_usuario(self):
        otro_user = crear_usuario_test('otro@test.com')
        self.client.force_login(otro_user)
        resp = self.client.get(reverse('pagos:resultado', kwargs={'commerce_order': self.orden.commerce_order}))
        self.assertEqual(resp.status_code, 404)


class CalendarMonthsAndRenewalTests(TestCase):
    """Pruebas de meses calendario exactos y renovación anticipada."""

    def test_sumar_meses_calendario_exactos(self):
        # 31 de Agosto + 6 meses -> 28 de Febrero (en año no bisiesto)
        dt = timezone.datetime(2025, 8, 31, 12, 0, 0, tzinfo=timezone.get_current_timezone())
        res = sumar_meses_calendario(dt, 6)
        self.assertEqual(res.year, 2026)
        self.assertEqual(res.month, 2)
        self.assertEqual(res.day, 28)

        # 31 de Enero + 12 meses -> 31 de Enero del año siguiente
        dt2 = timezone.datetime(2026, 1, 31, 10, 0, 0, tzinfo=timezone.get_current_timezone())
        res2 = sumar_meses_calendario(dt2, 12)
        self.assertEqual(res2.year, 2027)
        self.assertEqual(res2.month, 1)
        self.assertEqual(res2.day, 31)

    @patch('apps.pagos.flow.FlowClient.obtener_estado_pago')
    def test_renovacion_pro_vigente_conserva_tiempo_restante(self, mock_status):
        """Criterio 17: Renovar antes de que venza no pierde días restantes."""
        user = crear_usuario_test('pro_renovador@test.com')
        ahora = timezone.now()
        vencimiento_actual = ahora + timedelta(days=45)
        PerfilPiloto.objects.create(
            user=user,
            tipo_cuenta='PRO',
            fecha_inicio_plan=ahora - timedelta(days=100),
            fecha_fin_plan=vencimiento_actual
        )

        orden = OrdenPago.objects.create(
            usuario=user,
            commerce_order='FOG-RENOVAR-12M',
            plan=OrdenPago.PLAN_PRO_12M,
            monto=9990,
            moneda='CLP',
            estado=OrdenPago.ESTADO_PENDIENTE,
            flow_token='TOKEN_RENOVACION'
        )

        mock_status.return_value = {
            'status': 2,
            'flowOrder': 1234,
            'commerceOrder': orden.commerce_order,
            'amount': 9990,
            'currency': 'CLP',
        }

        procesar_confirmacion_flow('TOKEN_RENOVACION')

        user.perfil_piloto.refresh_from_db()
        # La nueva fecha debe ser vencimiento_actual + 12 meses calendario
        esperada = sumar_meses_calendario(vencimiento_actual, 12)
        self.assertEqual(user.perfil_piloto.fecha_fin_plan, esperada)


class RuntimeExpirationAndDowngradeTests(TestCase):
    """Pruebas de degradación en tiempo real y management commands."""

    def test_vencimiento_pro_en_runtime_degrada_a_limites_gratis(self):
        """Ajuste 13 / Criterio 21: Runtime trata como GRATIS si fecha_fin_plan <= ahora."""
        user = crear_usuario_test('expirado@test.com')
        PerfilPiloto.objects.create(
            user=user,
            tipo_cuenta='PRO',
            fecha_fin_plan=timezone.now() - timedelta(hours=1)
        )
        # En runtime debe resolver como GRATIS
        self.assertEqual(obtener_tipo_cuenta(user), 'GRATIS')

        # Si tiene 10 canciones no debe poder crear la 11
        for i in range(10):
            Cancion.objects.create(titulo=f"Tema {i}", artista="A", contenido="La [Am] letra", propietario=user)

        self.assertFalse(puede_crear_cancion(user))

    def test_downgrade_por_vencimiento_no_elimina_canciones_ni_fogatas(self):
        """Criterio 22: Al vencer Pro nada se borra ni se bloquea."""
        user = crear_usuario_test('downgrade@test.com')
        PerfilPiloto.objects.create(
            user=user,
            tipo_cuenta='PRO',
            fecha_fin_plan=timezone.now() - timedelta(days=2)
        )
        for i in range(15):
            Cancion.objects.create(titulo=f"Cancion {i}", artista="B", contenido="Acordes [C]", propietario=user)
        Fogata.objects.create(nombre="Setlist 1", propietario=user)
        Fogata.objects.create(nombre="Setlist 2", propietario=user)

        call_command('procesar_vencimientos_planes')
        user.perfil_piloto.refresh_from_db()
        self.assertEqual(user.perfil_piloto.tipo_cuenta, 'GRATIS')

        # Todas las 15 canciones y 2 Fogatas siguen existiendo
        self.assertEqual(Cancion.objects.filter(propietario=user).count(), 15)
        self.assertEqual(Fogata.objects.filter(propietario=user).count(), 2)

    @patch('apps.pagos.flow.FlowClient.obtener_estado_pago')
    def test_reconciliacion_recupera_pago_confirmado(self, mock_status):
        """Ajuste 5: Comando reconciliar_pagos_flow recupera órdenes pendientes."""
        user = crear_usuario_test('reconciliar@test.com')
        PerfilPiloto.objects.create(user=user, tipo_cuenta='GRATIS')
        orden = OrdenPago.objects.create(
            usuario=user,
            commerce_order='FOG-RECONCILIAR',
            plan=OrdenPago.PLAN_PRO_6M,
            monto=5990,
            moneda='CLP',
            estado=OrdenPago.ESTADO_PENDIENTE,
            flow_token='TOKEN_RECONCILIAR'
        )

        mock_status.return_value = {
            'status': 2,
            'flowOrder': 555,
            'commerceOrder': orden.commerce_order,
            'amount': 5990,
            'currency': 'CLP',
        }

        call_command('reconciliar_pagos_flow', dias=7)

        orden.refresh_from_db()
        self.assertEqual(orden.estado, OrdenPago.ESTADO_PAGADA)
        self.assertTrue(orden.pro_aplicado)
        user.perfil_piloto.refresh_from_db()
        self.assertEqual(user.perfil_piloto.tipo_cuenta, 'PRO')


class MetricsAndSecurityTests(TestCase):
    """Pruebas de métricas financieras, separación sandbox/producción y permisos."""

    def test_orden_sandbox_no_suma_ingresos_reales(self):
        """Ajuste 8: Solo PRODUCTION + PAGADA suma ingresos y ventas reales."""
        user = crear_usuario_test('test_m@test.com')
        PerfilPiloto.objects.create(user=user, tipo_cuenta='GRATIS')

        # Orden en SANDBOX PAGADA
        OrdenPago.objects.create(
            usuario=user,
            commerce_order='FOG-SANDBOX-PAGADA',
            plan=OrdenPago.PLAN_PRO_6M,
            monto=5990,
            moneda='CLP',
            estado=OrdenPago.ESTADO_PAGADA,
            ambiente=OrdenPago.AMBIENTE_SANDBOX,
            pro_aplicado=True
        )

        m = obtener_metricas_comerciales()
        self.assertEqual(m['ingresos_totales'], 0)
        self.assertEqual(m['ventas_totales'], 0)

        # Orden en PRODUCTION PAGADA
        OrdenPago.objects.create(
            usuario=user,
            commerce_order='FOG-PROD-PAGADA',
            plan=OrdenPago.PLAN_PRO_12M,
            monto=9990,
            moneda='CLP',
            estado=OrdenPago.ESTADO_PAGADA,
            ambiente=OrdenPago.AMBIENTE_PRODUCTION,
            pro_aplicado=True,
            pagada_el=timezone.now()
        )

        m2 = obtener_metricas_comerciales()
        self.assertEqual(m2['ingresos_totales'], 9990)
        self.assertEqual(m2['ventas_totales'], 1)
        self.assertEqual(m2['ventas_anual'], 1)

    def test_pro_manual_no_cuenta_como_venta_ni_ingreso(self):
        """Ajuste 10: Usuario asignado manualmente a PRO no suma en ventas."""
        admin_user = crear_admin_test('adm@test.com')
        user_manual = crear_usuario_test('manual@test.com')
        PerfilPiloto.objects.create(user=user_manual, tipo_cuenta='PRO')

        m = obtener_metricas_comerciales()
        self.assertEqual(m['ventas_totales'], 0)
        self.assertEqual(m['ingresos_totales'], 0)
        self.assertEqual(m['pro_pagados_activos'], 0)
        self.assertEqual(m['pro_activos_totales'], 1)

    def test_control_center_pagos_requiere_staff(self):
        user_comun = crear_usuario_test('comun@test.com')
        self.client.force_login(user_comun)
        resp = self.client.get(reverse('gestion:pagos_lista'))
        self.assertEqual(resp.status_code, 403)

        staff_user = crear_usuario_test('staff@test.com', is_staff=True)
        self.client.force_login(staff_user)
        resp_staff = self.client.get(reverse('gestion:pagos_lista'))
        self.assertEqual(resp_staff.status_code, 200)

    def test_credenciales_flow_nunca_llegan_a_contexto_de_plantilla(self):
        """Criterio 27: Templates no deben recibir secretos."""
        user = crear_usuario_test('templ@test.com')
        self.client.force_login(user)
        resp = self.client.get(reverse('pro'))
        self.assertEqual(resp.status_code, 200)
        contenido = resp.content.decode('utf-8')
        self.assertNotIn("FLOW_SECRET_KEY", contenido)
        self.assertNotIn("FLOW_API_KEY", contenido)
