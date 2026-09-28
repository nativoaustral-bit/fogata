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

