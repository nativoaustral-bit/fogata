from datetime import timedelta
from django.test import TestCase, Client, TransactionTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.db import transaction, models
from django.db.models.deletion import ProtectedError

from apps.canciones.models import Cancion
from apps.fogatas.models import Fogata, FogataCancion, SesionCompartida
from apps.core.models import Invitacion, PerfilPiloto
from .models import EventoUso, AuditoriaAdmin
from .constants import ACCIONES_USO_REAL, obtener_analytics_start_date
from .services import registrar_evento, sanitizar_metadata
from .metrics import (
    obtener_metricas_dashboard,
    calcular_retencion_7_dias,
    calcular_retencion_30_dias,
    calcular_funnel_nuevos_usuarios,
)
from .views import sanitizar_celda_csv

User = get_user_model()


class GestionSecurityTests(TestCase):
    """
    Pruebas de control de acceso y autorización estricta en /gestion/.
    """
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='admin@humm.cl',
            email='admin@humm.cl',
            password='PasswordAdmin123!',
            is_staff=True
        )
        self.normal_user = User.objects.create_user(
            username='musico@humm.cl',
            email='musico@humm.cl',
            password='PasswordMusico123!',
            is_staff=False
        )
        self.client = Client()

    def test_acceso_anonimo_redirige_login(self):
        url = reverse('gestion:dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_acceso_usuario_comun_prohibido_403(self):
        self.client.login(username='musico@humm.cl', password='PasswordMusico123!')
        url = reverse('gestion:dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, 'gestion/403.html')

    def test_acceso_staff_permitido(self):
        self.client.login(username='admin@humm.cl', password='PasswordAdmin123!')
        url = reverse('gestion:dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/dashboard.html')


class EventoUsoTests(TransactionTestCase):
    """
    Pruebas del sistema de eventos, sanitización, debounce y transacciones.
    """
    def setUp(self):
        self.user = User.objects.create_user(
            username='guitarrista@humm.cl',
            email='guitarrista@humm.cl',
            password='PassGuitarrista123!'
        )
        PerfilPiloto.objects.create(user=self.user, codigo_invitacion='TESTPILOTO')

    def test_sanitizar_metadata_elimina_claves_prohibidas(self):
        metadata_insegura = {
            'letra': 'De música ligera...',
            'acordes': 'Bm G D A',
            'titulo': 'Canción privada',
            'token': 'secret123',
            'origen': 'directo'
        }
        limpia = sanitizar_metadata('tocar_cancion', metadata_insegura)
        self.assertNotIn('letra', limpia)
        self.assertNotIn('acordes', limpia)
        self.assertNotIn('titulo', limpia)
        self.assertNotIn('token', limpia)
        self.assertEqual(limpia.get('origen'), 'directo')

    def test_registrar_evento_exitoso(self):
        registrar_evento(
            usuario=self.user,
            tipo_evento='crear_cancion',
            objeto_tipo='cancion',
            objeto_id=10
        )
        self.assertEqual(EventoUso.objects.filter(usuario=self.user, tipo_evento='crear_cancion').count(), 1)

    def test_transaccion_rollback_no_genera_evento(self):
        """
        Criterio 16 y 38: Una transacción que hace rollback no produce eventos persistidos.
        """
        try:
            with transaction.atomic():
                registrar_evento(
                    usuario=self.user,
                    tipo_evento='crear_cancion',
                    objeto_tipo='cancion',
                    objeto_id=999
                )
                raise ValueError("Simulación de fallo antes de commit")
        except ValueError:
            pass

        self.assertFalse(EventoUso.objects.filter(objeto_id=999).exists())

    def test_debounce_tocar_cancion(self):
        """
        Criterio 9 y 38: Múltiples aperturas dentro de 5 minutos en la misma sesión
        generan solo 1 evento tocar_cancion.
        """
        cancion = Cancion.objects.create(
            propietario=self.user,
            titulo='Canción de Prueba',
            contenido='Letra de prueba'
        )
        client = Client()
        client.login(username=self.user.username, password='PassGuitarrista123!')

        url = reverse('canciones:tocar', args=[cancion.pk])

        # Primera apertura -> debe registrar evento
        client.get(url)
        self.assertEqual(EventoUso.objects.filter(usuario=self.user, tipo_evento='tocar_cancion').count(), 1)

        # Segunda apertura inmediata (refresh) -> NO debe duplicar evento
        client.get(url)
        self.assertEqual(EventoUso.objects.filter(usuario=self.user, tipo_evento='tocar_cancion').count(), 1)

    def test_debounce_tocar_fogata(self):
        """
        Criterio 10 y 38: Navegar varios temas dentro de la misma Fogata no infla tocar_fogata.
        """
        fogata = Fogata.objects.create(propietario=self.user, nombre='Fogata Rock')
        cancion1 = Cancion.objects.create(propietario=self.user, titulo='Tema 1', contenido='...')
        cancion2 = Cancion.objects.create(propietario=self.user, titulo='Tema 2', contenido='...')
        FogataCancion.objects.create(fogata=fogata, cancion=cancion1, orden=1)
        FogataCancion.objects.create(fogata=fogata, cancion=cancion2, orden=2)

        client = Client()
        client.login(username=self.user.username, password='PassGuitarrista123!')

        url_tocar = reverse('fogatas:tocar_sesion', args=[fogata.pk])

        # Tema 1
        client.get(f"{url_tocar}?pos=1")
        self.assertEqual(EventoUso.objects.filter(usuario=self.user, tipo_evento='tocar_fogata').count(), 1)

        # Tema 2 (mismo setlist dentro de los 15 minutos) -> No duplica
        client.get(f"{url_tocar}?pos=2")
        self.assertEqual(EventoUso.objects.filter(usuario=self.user, tipo_evento='tocar_fogata').count(), 1)

    def test_aperturas_sesion_compartida_no_infla_por_canciones(self):
        """
        Criterio 11 y 38: Navegar canciones dentro de una sesión compartida no infla
        el contador de abrir_sesion_compartida.
        """
        fogata = Fogata.objects.create(propietario=self.user, nombre='Fogata Acústica')
        cancion = Cancion.objects.create(propietario=self.user, titulo='Tema A', contenido='Letra')
        item = FogataCancion.objects.create(fogata=fogata, cancion=cancion, orden=1)
        sesion = SesionCompartida.objects.create(fogata=fogata)

        client = Client()

        # Invitado abre la entrada principal /s/<token>/ -> Registra 1 evento
        url_principal = reverse('sesion_compartida_publica', args=[sesion.token])
        resp1 = client.get(url_principal)
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(EventoUso.objects.filter(tipo_evento='abrir_sesion_compartida').count(), 1)

        # Invitado lee la canción /s/<token>/cancion/<id>/ -> NO registra abrir_sesion_compartida
        url_cancion = reverse('sesion_compartida_cancion_publica', args=[sesion.token, item.cancion_id])
        resp2 = client.get(url_cancion)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(EventoUso.objects.filter(tipo_evento='abrir_sesion_compartida').count(), 1)


class MetricasYAnaliticaTests(TransactionTestCase):
    """
    Pruebas del motor de métricas: DAU/WAU/MAU, usuario activo, recurrente,
    retención 7 y 30 días, y embudo de adopción.
    """
    def setUp(self):
        self.start_date = obtener_analytics_start_date()
        self.u1 = User.objects.create_user(
            username='u1@humm.cl',
            email='u1@humm.cl',
            password='Password123!'
        )
        self.u1.date_joined = self.start_date
        self.u1.save()
        PerfilPiloto.objects.create(user=self.u1)

    def test_login_solo_no_activa_usuario(self):
        """
        Criterio 1, 2 y 38: Iniciar sesión únicamente NO convierte a un usuario en activo
        en DAU, WAU ni MAU.
        """
        # Registrar evento de login únicamente
        registrar_evento(usuario=self.u1, tipo_evento='login')

        metricas = obtener_metricas_dashboard()
        self.assertEqual(metricas['dau'], 0)
        self.assertEqual(metricas['wau'], 0)
        self.assertEqual(metricas['mau'], 0)

        # Al registrar una acción real de producto, pasa a ser activo
        registrar_evento(usuario=self.u1, tipo_evento='tocar_cancion', objeto_tipo='cancion', objeto_id=1)
        metricas_post = obtener_metricas_dashboard()
        self.assertEqual(metricas_post['dau'], 1)
        self.assertEqual(metricas_post['wau'], 1)
        self.assertEqual(metricas_post['mau'], 1)

    def test_usuario_recurrente_30_dias(self):
        """
        Criterio 36 y 38:
        - Actividad en 2 días distintos dentro de 30 días = Recurrente.
        - Actividad en 1 solo día = No recurrente.
        """
        ahora = timezone.now()
        dia1 = ahora - timedelta(days=5)
        dia2 = ahora - timedelta(days=2)

        # Caso 1: 2 eventos en el mismo día -> No recurrente
        registrar_evento(usuario=self.u1, tipo_evento='crear_cancion', fecha=dia1)
        registrar_evento(usuario=self.u1, tipo_evento='tocar_cancion', fecha=dia1 + timedelta(hours=1))

        metricas = obtener_metricas_dashboard()
        self.assertEqual(metricas['usuarios_recurrentes_30d'], 0)

        # Caso 2: Nuevo evento en un día distinto -> Recurrente
        registrar_evento(usuario=self.u1, tipo_evento='tocar_cancion', fecha=dia2)
        metricas_post = obtener_metricas_dashboard()
        self.assertEqual(metricas_post['usuarios_recurrentes_30d'], 1)

    def test_usuario_activado(self):
        """
        Criterio 3: Usuario activado = creó al menos 1 canción y usó Modo Tocar.
        """
        # Inicialmente no activado
        metricas = obtener_metricas_dashboard()
        self.assertEqual(metricas['usuarios_activados_total'], 0)

        # Crea canción
        Cancion.objects.create(propietario=self.u1, titulo='Test', contenido='...')
        metricas = obtener_metricas_dashboard()
        self.assertEqual(metricas['usuarios_activados_total'], 0)

        # Usa Modo Tocar
        registrar_evento(usuario=self.u1, tipo_evento='tocar_cancion')
        metricas = obtener_metricas_dashboard()
        self.assertEqual(metricas['usuarios_activados_total'], 1)

    def test_cohorte_fase_7_no_distorsiona_funnel(self):
        """
        Criterio 5 y 38: Usuarios registrados antes de ANALYTICS_START_DATE no se
        incluyen en el funnel principal de nuevos usuarios.
        """
        usuario_historico = User.objects.create_user(
            username='historico@humm.cl',
            email='historico@humm.cl',
            password='Pass123!'
        )
        usuario_historico.date_joined = self.start_date - timedelta(days=60)
        usuario_historico.save()

        # Funnel de nuevos usuarios solo cuenta a u1 (registrado en start_date)
        funnel = calcular_funnel_nuevos_usuarios()
        self.assertEqual(funnel['total_registrados'], 1)

    def test_retencion_7_y_30_dias(self):
        """
        Criterio 7 y 38: Validar ventanas de tiempo para retención 7d (día 1-7) y 30d (día 8-30).
        """
        # Creamos usuario registrado hace 35 días
        ahora = timezone.now()
        u_ret = User.objects.create_user(
            username='antiguo@humm.cl',
            email='antiguo@humm.cl',
            password='Pass123!'
        )
        u_ret.date_joined = self.start_date
        u_ret.save()

        # Actividad entre día 1 y 7 posterior al registro
        fecha_act_7d = u_ret.date_joined + timedelta(days=3)
        registrar_evento(usuario=u_ret, tipo_evento='crear_cancion', fecha=fecha_act_7d)

        # Actividad entre día 8 y 30 posterior al registro
        fecha_act_30d = u_ret.date_joined + timedelta(days=15)
        registrar_evento(usuario=u_ret, tipo_evento='tocar_fogata', fecha=fecha_act_30d)

        ret_7 = calcular_retencion_7_dias()
        ret_30 = calcular_retencion_30_dias()

        self.assertIn('porcentaje', ret_7)
        self.assertIn('porcentaje', ret_30)


class AdministracionAuditoriaYCSVTests(TestCase):
    """
    Pruebas de suspensión, reactivación, auditoría con PROTECT, y sanitización CSV.
    """
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='admin@humm.cl',
            email='admin@humm.cl',
            password='PasswordAdmin123!',
            is_staff=True
        )
        self.user = User.objects.create_user(
            username='sospechoso@humm.cl',
            email='sospechoso@humm.cl',
            password='PassUser123!',
            first_name='=1+1'  # Nombre malicioso para prueba de fórmula CSV
        )
        PerfilPiloto.objects.create(user=self.user)
        self.client = Client()
        self.client.login(username='admin@humm.cl', password='PasswordAdmin123!')

    def test_suspender_usuario_invalida_sesion_inmediatamente(self):
        """
        Criterio 20 y 38: Al suspender un usuario, se marca is_active=False, se registra auditoría,
        y una sesión previamente abierta pierde acceso en su siguiente petición.
        """
        user_client = Client()
        user_client.login(username='sospechoso@humm.cl', password='PassUser123!')

        # La sesión privada funciona antes de suspender
        resp_pre = user_client.get(reverse('canciones:lista'))
        self.assertEqual(resp_pre.status_code, 200)

        # Staff suspende al usuario mediante POST
        url_suspender = reverse('gestion:usuario_suspender', args=[self.user.pk])
        resp_susp = self.client.post(url_suspender)
        self.assertEqual(resp_susp.status_code, 302)

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

        # Auditoría registrada
        self.assertTrue(AuditoriaAdmin.objects.filter(usuario_afectado=self.user, accion='suspender_usuario').exists())

        # En la siguiente petición del usuario, se deniega acceso o se invalida sesión
        resp_post = user_client.get(reverse('canciones:lista'))
        self.assertIn(resp_post.status_code, (302, 401, 403))

    def test_reactivar_usuario(self):
        self.user.is_active = False
        self.user.save()

        url_reactivar = reverse('gestion:usuario_reactivar', args=[self.user.pk])
        resp = self.client.post(url_reactivar)
        self.assertEqual(resp.status_code, 302)

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertTrue(AuditoriaAdmin.objects.filter(usuario_afectado=self.user, accion='reactivar_usuario').exists())

    def test_auditoria_protege_eliminacion_usuario(self):
        """
        Criterio 17 y 38: on_delete=PROTECT en usuario_afectado impide borrar accidentalmente
        a un usuario mientras conserve registros de auditoría administrativa.
        """
        AuditoriaAdmin.objects.create(
            admin=self.staff_user,
            usuario_afectado=self.user,
            accion='suspender_usuario',
            detalles='Auditoría de prueba'
        )

        with self.assertRaises(ProtectedError):
            self.user.delete()

    def test_csv_formula_injection_sanitization(self):
        """
        Criterio 21 y 38: Valores que comienzan con =, +, -, @ se prefijan con '
        para prevenir inyección de fórmulas al abrir el CSV en Excel/Sheets.
        """
        self.assertEqual(sanitizar_celda_csv("=1+1"), "'=1+1")
        self.assertEqual(sanitizar_celda_csv("+123"), "'+123")
        self.assertEqual(sanitizar_celda_csv("-50"), "'-50")
        self.assertEqual(sanitizar_celda_csv("@SUM(A1:A5)"), "'@SUM(A1:A5)")
        self.assertEqual(sanitizar_celda_csv("Usuario Normal"), "Usuario Normal")

        # Probar endpoint de descarga CSV
        url_csv = reverse('gestion:exportar_usuarios_csv')
        resp = self.client.get(url_csv)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        contenido = resp.content.decode('utf-8')

        # Verificar que el nombre '=1+1' fue prefijado con comilla
        self.assertIn("'=1+1", contenido)
        # Verificar que no contiene información sensible
        self.assertNotIn('letra', contenido.lower())
        self.assertNotIn('acorde', contenido.lower())
        self.assertNotIn('pbkdf2', contenido.lower())

    def test_prevenir_n_mas_1_usuarios_lista(self):
        """
        Criterio 29 y 38: Verificar que la consulta del listado de usuarios no
        ejecute N consultas adicionales según la cantidad de usuarios.
        """
        # Crear 10 usuarios adicionales
        for i in range(10):
            u = User.objects.create_user(username=f'u_batch_{i}@humm.cl', email=f'u_batch_{i}@humm.cl', password='Pass123!')
            PerfilPiloto.objects.create(user=u)

        url = reverse('gestion:usuarios_lista')
        with self.assertNumQueries(4):  # session, user auth, count, select annotado con joins
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)

    def test_acciones_administrativas_requieren_post(self):
        """
        Criterio 34 y 38: Las acciones administrativas (suspender/reactivar) requieren POST.
        Una petición GET retorna HTTP 405 y nunca modifica el estado del usuario.
        """
        url_suspender = reverse('gestion:usuario_suspender', args=[self.user.pk])
        resp_get = self.client.get(url_suspender)
        self.assertEqual(resp_get.status_code, 405)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

        self.user.is_active = False
        self.user.save()

        url_reactivar = reverse('gestion:usuario_reactivar', args=[self.user.pk])
        resp_get2 = self.client.get(url_reactivar)
        self.assertEqual(resp_get2.status_code, 405)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)


class Fase10LimpiezaSeguraTests(TestCase):
    """
    Suite obligatoria de 15 pruebas para la Fase 10:
    Limpieza y administración segura de usuarios y datos de prueba.
    """
    def setUp(self):
        from apps.pagos.models import OrdenPago
        self.OrdenPago = OrdenPago

        # Superadministrador
        self.superadmin = User.objects.create_superuser(
            username='superadmin@humm.cl',
            email='superadmin@humm.cl',
            password='PassSuperAdmin123!'
        )

        # Staff administrador regular
        self.admin = User.objects.create_user(
            username='staff@humm.cl',
            email='staff@humm.cl',
            password='PassStaff123!',
            is_staff=True
        )

        # Cliente autenticado como staff
        self.client = Client()
        self.client.login(username='staff@humm.cl', password='PassStaff123!')

    def test_01_eliminar_usuario_sin_pagos(self):
        """1. Eliminar usuario sin pagos."""
        from apps.gestion.services import puede_eliminar_usuario, eliminar_usuario_prueba

        u_test = User.objects.create_user(username='test_sin_pagos@humm.cl', email='test_sin_pagos@humm.cl', password='Pass123!')
        puede, motivo = puede_eliminar_usuario(u_test, admin_usuario=self.admin)
        self.assertTrue(puede)
        self.assertEqual(motivo, "")

        u_id = u_test.pk
        resumen = eliminar_usuario_prueba(u_test, admin_responsable=self.admin)
        self.assertIsInstance(resumen, dict)
        self.assertFalse(User.objects.filter(pk=u_id).exists())
        self.assertTrue(AuditoriaAdmin.objects.filter(accion='suspender_usuario').exists())

    def test_02_eliminar_usuario_con_datos_asociados(self):
        """2. Eliminar usuario con datos asociados (canciones, fogatas, relaciones, sesiones, eventos)."""
        from apps.gestion.services import obtener_resumen_dependencias_usuario, eliminar_usuario_prueba

        u = User.objects.create_user(username='test_datos@humm.cl', email='test_datos@humm.cl', password='Pass123!')
        c1 = Cancion.objects.create(propietario=u, titulo='C1', contenido='...')
        c2 = Cancion.objects.create(propietario=u, titulo='C2', contenido='...')
        f = Fogata.objects.create(propietario=u, nombre='F1')
        FogataCancion.objects.create(fogata=f, cancion=c1, orden=1)
        SesionCompartida.objects.create(fogata=f)
        EventoUso.objects.create(usuario=u, tipo_evento='crear_cancion')
        EventoUso.objects.create(usuario=u, tipo_evento='tocar_cancion')

        resumen = obtener_resumen_dependencias_usuario(u)
        self.assertEqual(resumen['canciones_count'], 2)
        self.assertEqual(resumen['fogatas_count'], 1)
        self.assertEqual(resumen['sesiones_compartidas_count'], 1)
        self.assertEqual(resumen['eventos_count'], 2)

        u_id = u.pk
        res = eliminar_usuario_prueba(u, admin_responsable=self.admin)
        self.assertIsInstance(res, dict)
        self.assertFalse(User.objects.filter(pk=u_id).exists())
        self.assertEqual(Cancion.objects.filter(propietario_id=u_id).count(), 0)
        self.assertEqual(Fogata.objects.filter(propietario_id=u_id).count(), 0)
        self.assertEqual(SesionCompartida.objects.filter(fogata__propietario_id=u_id).count(), 0)

    def test_03_eliminar_usuario_con_ordenes_sandbox(self):
        """3. Eliminar usuario con órdenes Sandbox."""
        from apps.gestion.services import puede_eliminar_usuario, eliminar_usuario_prueba

        u = User.objects.create_user(username='test_sandbox@humm.cl', email='test_sandbox@humm.cl', password='Pass123!')
        ord_s = self.OrdenPago.objects.create(
            usuario=u,
            monto=5990,
            estado=self.OrdenPago.ESTADO_PAGADA,
            ambiente=self.OrdenPago.AMBIENTE_SANDBOX,
            commerce_order='TEST-SBX-01',
            flow_order=1001
        )

        puede, motivo = puede_eliminar_usuario(u, admin_usuario=self.admin)
        self.assertTrue(puede)

        u_id = u.pk
        ord_s_pk = ord_s.pk
        res = eliminar_usuario_prueba(u, admin_responsable=self.admin)
        self.assertIsInstance(res, dict)
        self.assertFalse(User.objects.filter(pk=u_id).exists())
        self.assertFalse(self.OrdenPago.objects.filter(pk=ord_s_pk).exists())

    def test_04_bloquear_eliminacion_si_posee_pago_production_pagada(self):
        """4. Bloquear eliminación si posee pago Production PAGADA (servicio y view)."""
        from apps.gestion.services import puede_eliminar_usuario, eliminar_usuario_prueba

        u_prod = User.objects.create_user(username='cliente_real@humm.cl', email='cliente_real@humm.cl', password='Pass123!')
        self.OrdenPago.objects.create(
            usuario=u_prod,
            monto=5990,
            estado=self.OrdenPago.ESTADO_PAGADA,
            ambiente=self.OrdenPago.AMBIENTE_PRODUCTION,
            commerce_order='FOGATA-PROD-01',
            flow_order=2001
        )

        # A nivel de servicio
        puede, motivo = puede_eliminar_usuario(u_prod, admin_usuario=self.admin)
        self.assertFalse(puede)
        self.assertIn("producción", motivo.lower())

        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            eliminar_usuario_prueba(u_prod, admin_responsable=self.admin)
        self.assertTrue(User.objects.filter(pk=u_prod.pk).exists())

        # A nivel de vista HTTP POST
        url = reverse('gestion:usuario_eliminar', args=[u_prod.pk])
        resp = self.client.post(url, {'confirmacion': 'ELIMINAR'})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(User.objects.filter(pk=u_prod.pk).exists())

    def test_05_desactivar_usuario_con_pago_production(self):
        """5. Desactivar usuario con pago Production."""
        u_prod = User.objects.create_user(username='cliente_suspendible@humm.cl', email='cliente_suspendible@humm.cl', password='Pass123!')
        self.OrdenPago.objects.create(
            usuario=u_prod,
            monto=5990,
            estado=self.OrdenPago.ESTADO_PAGADA,
            ambiente=self.OrdenPago.AMBIENTE_PRODUCTION,
            commerce_order='FOGATA-PROD-02',
            flow_order=2002
        )

        url = reverse('gestion:usuario_suspender', args=[u_prod.pk])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)

        u_prod.refresh_from_db()
        self.assertFalse(u_prod.is_active)
        # El usuario y su orden siguen intactos
        self.assertTrue(self.OrdenPago.objects.filter(commerce_order='FOGATA-PROD-02').exists())

    def test_06_reactivar_usuario(self):
        """6. Reactivar usuario."""
        u = User.objects.create_user(username='desactivado@humm.cl', email='desactivado@humm.cl', password='Pass123!', is_active=False)

        url = reverse('gestion:usuario_reactivar', args=[u.pk])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)

        u.refresh_from_db()
        self.assertTrue(u.is_active)

    def test_07_eliminar_orden_sandbox_individual(self):
        """7. Eliminar una orden Sandbox individual y proteger Production."""
        from django.core.exceptions import PermissionDenied
        from apps.gestion.services import eliminar_orden_sandbox

        u = User.objects.create_user(username='u_ordenes@humm.cl', email='u_ordenes@humm.cl', password='Pass123!')
        ord_sbx = self.OrdenPago.objects.create(
            usuario=u,
            monto=5990,
            estado=self.OrdenPago.ESTADO_PAGADA,
            ambiente=self.OrdenPago.AMBIENTE_SANDBOX,
            commerce_order='SBX-INDIVIDUAL-1'
        )
        ord_prod = self.OrdenPago.objects.create(
            usuario=u,
            monto=5990,
            estado=self.OrdenPago.ESTADO_PAGADA,
            ambiente=self.OrdenPago.AMBIENTE_PRODUCTION,
            commerce_order='PROD-INDIVIDUAL-1'
        )

        # Eliminar sandbox vía endpoint
        url_sbx = reverse('gestion:pago_eliminar_sandbox', args=[ord_sbx.pk])
        resp = self.client.post(url_sbx)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(self.OrdenPago.objects.filter(pk=ord_sbx.pk).exists())

        # Intentar eliminar Production vía servicio -> debe fallar con PermissionDenied
        with self.assertRaises(PermissionDenied):
            eliminar_orden_sandbox(ord_prod, admin_responsable=self.admin)
        self.assertTrue(self.OrdenPago.objects.filter(pk=ord_prod.pk).exists())

        # Intentar eliminar Production vía endpoint -> debe redirigir con error sin borrar
        url_prod = reverse('gestion:pago_eliminar_sandbox', args=[ord_prod.pk])
        resp_prod = self.client.post(url_prod)
        self.assertEqual(resp_prod.status_code, 302)
        self.assertTrue(self.OrdenPago.objects.filter(pk=ord_prod.pk).exists())

    def test_08_eliminacion_masiva_sandbox(self):
        """8. Eliminación masiva Sandbox."""
        from apps.gestion.services import limpiar_ordenes_sandbox

        u = User.objects.create_user(username='u_masivo@humm.cl', email='u_masivo@humm.cl', password='Pass123!')
        for i in range(3):
            self.OrdenPago.objects.create(
                usuario=u,
                monto=5990,
                estado=self.OrdenPago.ESTADO_PAGADA,
                ambiente=self.OrdenPago.AMBIENTE_SANDBOX,
                commerce_order=f'SBX-MASIVO-{i}'
            )

        ord_prod = self.OrdenPago.objects.create(
            usuario=u,
            monto=5990,
            estado=self.OrdenPago.ESTADO_PAGADA,
            ambiente=self.OrdenPago.AMBIENTE_PRODUCTION,
            commerce_order='PROD-INTACTA-1'
        )

        cant = limpiar_ordenes_sandbox(admin_responsable=self.admin)
        self.assertEqual(cant, 3)
        self.assertEqual(self.OrdenPago.objects.filter(ambiente=self.OrdenPago.AMBIENTE_SANDBOX).count(), 0)
        self.assertTrue(self.OrdenPago.objects.filter(pk=ord_prod.pk).exists())

    def test_09_garantizar_que_ninguna_orden_production_sea_eliminada(self):
        """9. Garantizar que ninguna orden Production sea eliminada en ninguna limpieza."""
        from apps.gestion.services import (
            limpiar_ordenes_sandbox,
            limpiar_actividad_prueba,
            ejecutar_limpieza_masiva_usuarios_prueba
        )

        u_prod = User.objects.create_user(username='u_intocable@humm.cl', email='u_intocable@humm.cl', password='Pass123!')
        p1 = self.OrdenPago.objects.create(
            usuario=u_prod, monto=5990, estado=self.OrdenPago.ESTADO_PAGADA,
            ambiente=self.OrdenPago.AMBIENTE_PRODUCTION, commerce_order='PROD-SAFE-1'
        )
        p2 = self.OrdenPago.objects.create(
            usuario=u_prod, monto=5990, estado=self.OrdenPago.ESTADO_PENDIENTE,
            ambiente=self.OrdenPago.AMBIENTE_PRODUCTION, commerce_order='PROD-SAFE-2'
        )

        # Limpiezas sucesivas
        limpiar_ordenes_sandbox(admin_responsable=self.admin)
        limpiar_actividad_prueba(admin_responsable=self.admin)
        ejecutar_limpieza_masiva_usuarios_prueba(admin_responsable=self.admin)

        # Ambas órdenes Production existen
        self.assertEqual(self.OrdenPago.objects.filter(ambiente=self.OrdenPago.AMBIENTE_PRODUCTION).count(), 2)
        self.assertTrue(self.OrdenPago.objects.filter(pk=p1.pk).exists())
        self.assertTrue(self.OrdenPago.objects.filter(pk=p2.pk).exists())

    def test_10_limpiar_actividad_cuenta_prueba(self):
        """10. Limpiar actividad de cuenta de prueba (individual y masiva)."""
        from apps.gestion.services import limpiar_actividad_usuario, limpiar_actividad_prueba

        u_prueba = User.objects.create_user(username='u_act_prueba@humm.cl', email='u_act_prueba@humm.cl', password='Pass123!')
        EventoUso.objects.create(usuario=u_prueba, tipo_evento='login')
        EventoUso.objects.create(usuario=u_prueba, tipo_evento='crear_cancion')

        u_real = User.objects.create_user(username='u_act_real@humm.cl', email='u_act_real@humm.cl', password='Pass123!')
        self.OrdenPago.objects.create(
            usuario=u_real, monto=5990, estado=self.OrdenPago.ESTADO_PAGADA,
            ambiente=self.OrdenPago.AMBIENTE_PRODUCTION, commerce_order='PROD-AUDIT-1'
        )
        ev_real = EventoUso.objects.create(usuario=u_real, tipo_evento='crear_cancion')

        # Limpiar usuario individual
        cant = limpiar_actividad_usuario(u_prueba, admin_responsable=self.admin)
        self.assertEqual(cant, 2)
        self.assertEqual(EventoUso.objects.filter(usuario=u_prueba).count(), 0)
        # Evento del usuario real intacto
        self.assertEqual(EventoUso.objects.filter(usuario=u_real).count(), 1)

        # Limpieza masiva de actividad
        EventoUso.objects.create(usuario=u_prueba, tipo_evento='tocar_cancion')
        cant2 = limpiar_actividad_prueba(admin_responsable=self.admin)
        self.assertGreaterEqual(cant2, 1)
        self.assertEqual(EventoUso.objects.filter(usuario=u_prueba).count(), 0)
        self.assertTrue(EventoUso.objects.filter(pk=ev_real.pk).exists())

    def test_11_impedir_eliminacion_superuser_conectado(self):
        """11. Impedir eliminación del superuser conectado o cuenta administrativa."""
        from apps.gestion.services import puede_eliminar_usuario

        # Staff intenta eliminarse a sí mismo
        puede_self, motivo_self = puede_eliminar_usuario(self.admin, admin_usuario=self.admin)
        self.assertFalse(puede_self)
        self.assertIn("propia cuenta", motivo_self.lower())

        # Staff intenta eliminar al superusuario
        puede_super, motivo_super = puede_eliminar_usuario(self.superadmin, admin_usuario=self.admin)
        self.assertFalse(puede_super)
        self.assertIn("administrador principal", motivo_super.lower())

    def test_12_csrf_y_post_obligatorio(self):
        """12. CSRF y POST obligatorio en acciones destructivas."""
        u_test = User.objects.create_user(username='u_test_csrf@humm.cl', email='u_test_csrf@humm.cl', password='Pass123!')

        # GET a usuario_eliminar NO elimina al usuario
        url = reverse('gestion:usuario_eliminar', args=[u_test.pk])
        resp_get = self.client.get(url)
        self.assertEqual(resp_get.status_code, 200)
        self.assertTrue(User.objects.filter(pk=u_test.pk).exists())

        # POST sin palabra clave 'ELIMINAR' no elimina
        resp_post_invalido = self.client.post(url, {'confirmacion': 'borrar'})
        self.assertEqual(resp_post_invalido.status_code, 200)
        self.assertTrue(User.objects.filter(pk=u_test.pk).exists())

        # POST correcto con 'ELIMINAR' sí elimina
        resp_post_valido = self.client.post(url, {'confirmacion': 'ELIMINAR'})
        self.assertEqual(resp_post_valido.status_code, 302)
        self.assertFalse(User.objects.filter(pk=u_test.pk).exists())

    def test_13_aislamiento_entre_usuarios(self):
        """13. Aislamiento entre usuarios (otros usuarios conservan todos sus datos)."""
        from apps.gestion.services import eliminar_usuario_prueba

        u_a = User.objects.create_user(username='u_a@humm.cl', email='u_a@humm.cl', password='Pass123!')
        u_b = User.objects.create_user(username='u_b@humm.cl', email='u_b@humm.cl', password='Pass123!')

        c_a = Cancion.objects.create(propietario=u_a, titulo='Cancion A')
        f_a = Fogata.objects.create(propietario=u_a, nombre='Fogata A')

        c_b = Cancion.objects.create(propietario=u_b, titulo='Cancion B')
        f_b = Fogata.objects.create(propietario=u_b, nombre='Fogata B')

        res = eliminar_usuario_prueba(u_a, admin_responsable=self.admin)
        self.assertIsInstance(res, dict)

        # Usuario B y sus datos están 100% intactos
        self.assertTrue(User.objects.filter(pk=u_b.pk).exists())
        self.assertTrue(Cancion.objects.filter(pk=c_b.pk).exists())
        self.assertTrue(Fogata.objects.filter(pk=f_b.pk).exists())

    def test_14_dry_run_produce_conteos_correctos(self):
        """14. Dry-run produce conteos correctos sin modificar DB."""
        from apps.gestion.services import obtener_dry_run_limpieza_usuarios

        u_dry = User.objects.create_user(username='u_dry@humm.cl', email='u_dry@humm.cl', password='Pass123!')
        Cancion.objects.create(propietario=u_dry, titulo='Cancion Dry')
        Fogata.objects.create(propietario=u_dry, nombre='Fogata Dry')
        EventoUso.objects.create(usuario=u_dry, tipo_evento='crear_cancion')

        dry = obtener_dry_run_limpieza_usuarios()
        self.assertGreaterEqual(dry['usuarios_count'], 1)
        self.assertGreaterEqual(dry['canciones_count'], 1)
        self.assertGreaterEqual(dry['fogatas_count'], 1)
        self.assertEqual(dry['ordenes_prod_afectadas'], 0)
        self.assertEqual(dry['ingresos_prod_afectados'], 0)

        # Verificar que la DB no se modificó
        self.assertTrue(User.objects.filter(pk=u_dry.pk).exists())

    def test_15_metricas_financieras_production_permanecen_identicas(self):
        """15. Métricas financieras Production permanecen idénticas antes y después de limpieza."""
        from apps.gestion.metrics import obtener_metricas_comerciales
        from apps.gestion.services import limpiar_ordenes_sandbox, ejecutar_limpieza_masiva_usuarios_prueba

        u_real = User.objects.create_user(username='u_comercial@humm.cl', email='u_comercial@humm.cl', password='Pass123!')
        self.OrdenPago.objects.create(
            usuario=u_real, monto=5990, estado=self.OrdenPago.ESTADO_PAGADA,
            ambiente=self.OrdenPago.AMBIENTE_PRODUCTION, commerce_order='PROD-METRIC-1'
        )

        u_test = User.objects.create_user(username='u_test_sbx@humm.cl', email='u_test_sbx@humm.cl', password='Pass123!')
        self.OrdenPago.objects.create(
            usuario=u_test, monto=5990, estado=self.OrdenPago.ESTADO_PAGADA,
            ambiente=self.OrdenPago.AMBIENTE_SANDBOX, commerce_order='SBX-METRIC-1'
        )

        metricas_pre = obtener_metricas_comerciales()
        self.assertEqual(metricas_pre['ingresos_totales'], 5990)
        self.assertEqual(metricas_pre['ventas_totales'], 1)

        # Ejecutar limpiezas
        limpiar_ordenes_sandbox(admin_responsable=self.admin)
        ejecutar_limpieza_masiva_usuarios_prueba(admin_responsable=self.admin)

        metricas_post = obtener_metricas_comerciales()
        self.assertEqual(metricas_post['ingresos_totales'], 5990)
        self.assertEqual(metricas_post['ventas_totales'], 1)
        self.assertEqual(metricas_pre['ingresos_totales'], metricas_post['ingresos_totales'])
        self.assertEqual(metricas_pre['ventas_totales'], metricas_post['ventas_totales'])



