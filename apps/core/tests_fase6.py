from django.test import TestCase, TransactionTestCase, Client, override_settings
from django.urls import reverse
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth.models import User
from django.utils import timezone
from apps.canciones.models import Cancion
from apps.fogatas.models import Fogata, FogataCancion, SesionCompartida
from apps.core.models import Invitacion, PerfilPiloto
from apps.fogatas.forms import AgregarCancionForm


class AislamientoMultiusuarioTest(TestCase):
    """
    Fase 6 — Criterios 1, 8 y 25:
    Aislamiento absoluto de bibliotecas privadas y prevención de IDOR.
    Un usuario nunca debe poder ver, editar o eliminar contenido de otro usuario.
    El ID nunca otorga acceso: el propietario sí. Todas las consultas ajenas deben retornar 404.
    """

    def setUp(self):
        # Usuario A
        self.user_a = User.objects.create_user(
            username='musico_a@correo.cl',
            email='musico_a@correo.cl',
            password='Password123!',
            first_name='Músico A'
        )
        self.cancion_a = Cancion.objects.create(
            propietario=self.user_a,
            titulo="Canción Privada A",
            artista="Banda A",
            contenido="G   D\nLetra confidencial de A"
        )
        self.fogata_a = Fogata.objects.create(
            propietario=self.user_a,
            nombre="Fogata de A",
            descripcion="Repertorio privado de A"
        )
        self.fc_a = FogataCancion.objects.create(
            fogata=self.fogata_a,
            cancion=self.cancion_a,
            orden=1
        )

        # Usuario B
        self.user_b = User.objects.create_user(
            username='musico_b@correo.cl',
            email='musico_b@correo.cl',
            password='Password123!',
            first_name='Músico B'
        )
        self.cancion_b = Cancion.objects.create(
            propietario=self.user_b,
            titulo="Canción Secreta B",
            artista="Banda B",
            contenido="Am  F\nLetra confidencial de B"
        )
        self.fogata_b = Fogata.objects.create(
            propietario=self.user_b,
            nombre="Fogata de B",
            descripcion="Repertorio privado de B"
        )
        self.fc_b = FogataCancion.objects.create(
            fogata=self.fogata_b,
            cancion=self.cancion_b,
            orden=1
        )

        self.client_a = Client()
        self.client_a.force_login(self.user_a)

        self.client_b = Client()
        self.client_b.force_login(self.user_b)

    def test_listados_estrictamente_aislados(self):
        """Usuario A no ve canciones ni fogatas de B en su lista."""
        res_canciones = self.client_a.get(reverse('canciones:lista'))
        self.assertEqual(res_canciones.status_code, 200)
        self.assertContains(res_canciones, "Canción Privada A")
        self.assertNotContains(res_canciones, "Canción Secreta B")

        res_fogatas = self.client_a.get(reverse('fogatas:lista'))
        self.assertEqual(res_fogatas.status_code, 200)
        self.assertContains(res_fogatas, "Fogata de A")
        self.assertNotContains(res_fogatas, "Fogata de B")

    def test_idor_lectura_cancion_ajena_retorna_404(self):
        """Intentar ver detalle, atril o edición de acordes de otro usuario devuelve 404."""
        # Detalle
        r1 = self.client_a.get(reverse('canciones:detalle', args=[self.cancion_b.pk]))
        self.assertEqual(r1.status_code, 404)

        # Modo Tocar (Atril)
        r2 = self.client_a.get(reverse('canciones:tocar', args=[self.cancion_b.pk]))
        self.assertEqual(r2.status_code, 404)

        # Editar Acordes
        r3 = self.client_a.get(reverse('canciones:editar_acordes', args=[self.cancion_b.pk]))
        self.assertEqual(r3.status_code, 404)

    def test_idor_modificacion_cancion_ajena_retorna_404(self):
        """Intentar editar o eliminar una canción ajena vía POST devuelve 404 y no altera datos."""
        # Editar
        post_data = {
            'titulo': 'Título Hackeado',
            'artista': 'Hacker',
            'contenido': 'C   G\nLetra alterada',
            'capo': 0
        }
        r_edit = self.client_a.post(reverse('canciones:editar', args=[self.cancion_b.pk]), post_data)
        self.assertEqual(r_edit.status_code, 404)
        self.cancion_b.refresh_from_db()
        self.assertEqual(self.cancion_b.titulo, "Canción Secreta B")

        # Guardar edición acorde
        r_acorde = self.client_a.post(
            reverse('canciones:guardar_edicion_acorde', args=[self.cancion_b.pk]),
            {'num_linea': 0, 'col_inicio': 0, 'col_fin': 2, 'texto_original': 'Am', 'nuevo_acorde': 'C', 'modo': 'uno'}
        )
        self.assertEqual(r_acorde.status_code, 404)

        # Eliminar
        r_del = self.client_a.post(reverse('canciones:eliminar', args=[self.cancion_b.pk]))
        self.assertEqual(r_del.status_code, 404)
        self.assertTrue(Cancion.objects.filter(pk=self.cancion_b.pk).exists())

    def test_idor_lectura_fogata_ajena_retorna_404(self):
        """Intentar ver detalle o atril de una Fogata ajena devuelve 404."""
        r_det = self.client_a.get(reverse('fogatas:detalle', args=[self.fogata_b.pk]))
        self.assertEqual(r_det.status_code, 404)

        r_tocar = self.client_a.get(reverse('fogatas:tocar_sesion', args=[self.fogata_b.pk]))
        self.assertEqual(r_tocar.status_code, 404)

    def test_idor_modificacion_fogata_ajena_retorna_404(self):
        """Intentar editar o eliminar una Fogata ajena vía POST devuelve 404."""
        r_edit = self.client_a.post(reverse('fogatas:editar', args=[self.fogata_b.pk]), {'nombre': 'Fogata Hackeada'})
        self.assertEqual(r_edit.status_code, 404)
        self.fogata_b.refresh_from_db()
        self.assertEqual(self.fogata_b.nombre, "Fogata de B")

        r_del = self.client_a.post(reverse('fogatas:eliminar', args=[self.fogata_b.pk]))
        self.assertEqual(r_del.status_code, 404)
        self.assertTrue(Fogata.objects.filter(pk=self.fogata_b.pk).exists())

    def test_idor_compartir_sesion_fogata_ajena_retorna_404(self):
        """Usuario A no puede crear ni revocar enlaces compartidos de Fogatas de B."""
        r_comp = self.client_a.post(reverse('fogatas:compartir_crear', args=[self.fogata_b.pk]), {'duracion_horas': 4})
        self.assertEqual(r_comp.status_code, 404)


class RelacionesFogataCancionTripleProteccionTest(TestCase):
    """
    Fase 6 — Criterio 9:
    Triple protección:
    1. Queryset filtrado en formulario.
    2. Validación en servidor en la vista.
    3. Validación a nivel de modelo en FogataCancion.
    Una Fogata de A nunca puede contener una Canción de B aunque el POST sea forzado.
    """

    def setUp(self):
        self.user_a = User.objects.create_user(username='a@test.cl', email='a@test.cl', password='pass')
        self.user_b = User.objects.create_user(username='b@test.cl', email='b@test.cl', password='pass')

        self.cancion_a = Cancion.objects.create(propietario=self.user_a, titulo="Tema A", contenido="C\nLetra A")
        self.fogata_a = Fogata.objects.create(propietario=self.user_a, nombre="Fogata A")

        self.cancion_b = Cancion.objects.create(propietario=self.user_b, titulo="Tema B", contenido="D\nLetra B")

        self.client_a = Client()
        self.client_a.force_login(self.user_a)

    def test_1_formulario_filtra_solo_canciones_propias(self):
        """El formulario AgregarCancionForm solo incluye canciones del propietario de la Fogata."""
        form = AgregarCancionForm(fogata=self.fogata_a)
        qs = form.fields['cancion'].queryset
        self.assertIn(self.cancion_a, qs)
        self.assertNotIn(self.cancion_b, qs)

    def test_2_post_forzado_a_servidor_es_rechazado(self):
        """Un POST manipulado enviando cancion_id ajena es rechazado y no se guarda."""
        url = reverse('fogatas:agregar_cancion', args=[self.fogata_a.pk])
        # Form submission con el id de cancion_b perteneciente al Usuario B
        res = self.client_a.post(url, {
            'cancion': self.cancion_b.pk,
            'nota_sesion': 'Inyección maliciosa'
        })
        # El formulario no valida porque cancion_b no está en el queryset permitido
        self.assertFalse(FogataCancion.objects.filter(fogata=self.fogata_a, cancion=self.cancion_b).exists())

    def test_3_modelo_rechaza_asociacion_cruzada(self):
        """El modelo FogataCancion lanza ValidationError si los propietarios no coinciden."""
        asociacion_invalida = FogataCancion(
            fogata=self.fogata_a,
            cancion=self.cancion_b,
            orden=1
        )
        with self.assertRaises(ValidationError):
            asociacion_invalida.full_clean()

        with self.assertRaises(ValidationError):
            asociacion_invalida.save()


class IdentidadNormalizadaYAutenticacionTest(TestCase):
    """
    Fase 6 — Criterios 2, 3 y 25:
    Normalización de email a minúsculas, login único, rechazo de duplicados sin importar mayúsculas.
    """

    def setUp(self):
        self.invitacion = Invitacion.objects.create(
            codigo='PILOTO2026',
            descripcion='Invitación para pruebas'
        )

    def test_registro_normaliza_email_a_minusculas_y_asigna_username(self):
        """Registro con Rodrigo@Correo.CL se almacena como rodrigo@correo.cl en email y username."""
        res = self.client.post(reverse('registro'), {
            'codigo_invitacion': 'PILOTO2026',
            'nombre': 'Rodrigo',
            'email': 'Rodrigo@Correo.CL',
            'password': 'MiPasswordSegura123!',
            'password_confirm': 'MiPasswordSegura123!'
        })
        self.assertEqual(res.status_code, 302)

        usuario = User.objects.get(email='rodrigo@correo.cl')
        self.assertEqual(usuario.username, 'rodrigo@correo.cl')
        self.assertEqual(usuario.email, 'rodrigo@correo.cl')
        self.assertTrue(usuario.check_password('MiPasswordSegura123!'))

        # Perfil piloto registrado
        self.assertTrue(PerfilPiloto.objects.filter(user=usuario, codigo_invitacion='PILOTO2026').exists())

    def test_no_permite_registro_duplicado_insensible_a_mayusculas(self):
        """Habiendo registrado Rodrigo@Correo.cl, no se permite registrar posteriormente rodrigo@correo.cl."""
        # Primer registro
        self.client.post(reverse('registro'), {
            'codigo_invitacion': 'PILOTO2026',
            'nombre': 'Rodrigo',
            'email': 'Rodrigo@Correo.cl',
            'password': 'Password123!',
            'password_confirm': 'Password123!'
        })

        # Desloguear para simular segundo visitante no autenticado
        self.client.logout()

        # Segundo registro con diferente capitalización y nueva invitación
        inv2 = Invitacion.objects.create(codigo='OTRO2026')
        res_dup = self.client.post(reverse('registro'), {
            'codigo_invitacion': 'OTRO2026',
            'nombre': 'Rodrigo Clon',
            'email': 'RODRIGO@correo.cl',
            'password': 'Password123!',
            'password_confirm': 'Password123!'
        })
        self.assertEqual(res_dup.status_code, 200)
        self.assertContains(res_dup, "Ya existe una cuenta registrada con este correo electrónico.")

    def test_login_insensible_a_mayusculas(self):
        """Login funciona con cualquier combinación de mayúsculas/minúsculas en el email."""
        User.objects.create_user(
            username='usuario@ejemplo.cl',
            email='usuario@ejemplo.cl',
            password='Password123!'
        )

        res_login = self.client.post(reverse('login'), {
            'email': 'USUARIO@EJEMPLO.CL',
            'password': 'Password123!'
        })
        self.assertEqual(res_login.status_code, 302)
        self.assertTrue('_auth_user_id' in self.client.session)


class InvitacionesConcurrenciaYLimitesTest(TransactionTestCase):
    """
    Fase 6 — Criterios 4, 5 y 25:
    Control de invitaciones, atomicidad y prevención de sobrecupo (max_usos).
    """

    def test_consumo_hasta_max_usos(self):
        """Una invitación con max_usos=1 no puede ser usada por un segundo registro."""
        inv = Invitacion.objects.create(
            codigo='SOLO-UNO',
            max_usos=1
        )

        # Primer uso
        inv_consumida = Invitacion.consumir_codigo('solo-uno')
        self.assertEqual(inv_consumida.usos_actuales, 1)
        self.assertFalse(inv_consumida.activa)

        # Segundo intento de consumo
        with self.assertRaises(ValueError) as ctx:
            Invitacion.consumir_codigo('SOLO-UNO')
        self.assertIn("desactivado", str(ctx.exception).lower())

    def test_consumo_concurrente_exacto_un_cupo(self):
        """
        Prueba de concurrencia multihilo: dos hilos intentan consumir simultáneamente
        una invitación con max_usos=1. Exactamente uno debe tener éxito y el otro debe fallar.
        """
        import threading
        from django.db import connection

        Invitacion.objects.create(
            codigo='CUPORACE',
            max_usos=1
        )
        resultados = []
        errores = []

        def intentar_consumir():
            connection.close()
            import time
            for _ in range(10):
                try:
                    res = Invitacion.consumir_codigo('CUPORACE')
                    resultados.append(res)
                    break
                except ValueError as e:
                    errores.append(e)
                    break
                except Exception as e:
                    # SQLite contención a nivel de archivo/tabla
                    time.sleep(0.02)

        t1 = threading.Thread(target=intentar_consumir)
        t2 = threading.Thread(target=intentar_consumir)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(resultados), 1, f"Exactamente 1 debe triunfar, hubo {len(resultados)}. Errores: {errores}")
        self.assertEqual(len(errores), 1, f"Exactamente 1 debe fallar, hubo {len(errores)}")
        inv_final = Invitacion.objects.get(codigo='CUPORACE')
        self.assertEqual(inv_final.usos_actuales, 1)
        self.assertFalse(inv_final.activa)

    def test_invitacion_expirada_es_rechazada(self):
        """Una invitación con expira_el en el pasado no se puede consumir."""
        Invitacion.objects.create(
            codigo='EXPIRADA',
            expira_el=timezone.now() - timezone.timedelta(hours=1)
        )
        with self.assertRaises(ValueError) as ctx:
            Invitacion.consumir_codigo('EXPIRADA')
        self.assertIn("expirado", str(ctx.exception).lower())

    def test_invitacion_desactivada_es_rechazada(self):
        """Una invitación con activa=False no se puede consumir."""
        Invitacion.objects.create(
            codigo='INACTIVA',
            activa=False
        )
        with self.assertRaises(ValueError) as ctx:
            Invitacion.consumir_codigo('INACTIVA')
        self.assertIn("desactivado", str(ctx.exception).lower())

    def test_registro_no_confia_en_query_string(self):
        """GET con ?codigo=ABC123 precarga el campo, pero un POST con código falso es rechazado en servidor."""
        res_get = self.client.get(reverse('registro') + '?codigo=FALSO123')
        self.assertEqual(res_get.status_code, 200)
        self.assertContains(res_get, 'value="FALSO123"')

        # POST con ese código inexistente
        res_post = self.client.post(reverse('registro'), {
            'codigo_invitacion': 'FALSO123',
            'nombre': 'Tester',
            'email': 'test@fake.cl',
            'password': 'Password123!',
            'password_confirm': 'Password123!'
        })
        self.assertEqual(res_post.status_code, 200)
        self.assertContains(res_post, "El código de invitación no existe.")


class SesionLogoutYCachePrivadaTest(TestCase):
    """
    Fase 6 — Criterios 13, 14 y 25:
    - Logout por POST exclusivamente.
    - Redirección tras expiración de sesión.
    - Cabeceras Cache-Control: no-store, private en respuestas de usuarios autenticados.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='musico_seguro@fogata.app',
            email='musico_seguro@fogata.app',
            password='Password123!'
        )
        self.cancion = Cancion.objects.create(
            propietario=self.user,
            titulo="Mi Canción",
            contenido="C\nLetra"
        )
        self.client.force_login(self.user)

    def test_logout_por_get_no_cierra_sesion(self):
        """GET a /logout/ no cierra la sesión accidentalmente."""
        res_get = self.client.get(reverse('logout'))
        # Debe redirigir o no mutar la sesión
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_logout_por_post_cierra_sesion_y_redirige(self):
        """POST a /logout/ invalida la sesión de Django."""
        res_post = self.client.post(reverse('logout'))
        self.assertEqual(res_post.status_code, 302)
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_sesion_expirada_redirige_a_login(self):
        """Si la sesión expira o es anónima, el acceso a vista privada redirige a login."""
        self.client.logout()
        res = self.client.get(reverse('canciones:detalle', args=[self.cancion.pk]))
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login/', res['Location'])

    def test_cabeceras_no_store_private_en_vistas_autenticadas(self):
        """Respuestas privadas incluyen Cache-Control: no-store, private."""
        urls_privadas = [
            reverse('core:home'),
            reverse('canciones:lista'),
            reverse('canciones:detalle', args=[self.cancion.pk]),
            reverse('canciones:tocar', args=[self.cancion.pk]),
            reverse('fogatas:lista'),
        ]
        for url in urls_privadas:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Error en URL privada: {url}")
            cc = res.get('Cache-Control', '')
            self.assertIn('no-store', cc, f"Falta no-store en {url}")
            self.assertIn('private', cc, f"Falta private en {url}")


class PasswordResetBlindResponseTest(TestCase):
    """
    Fase 6 — Criterios 17 y 25:
    Respuesta ciega idéntica tanto si el correo existe como si no existe.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='existente@fogata.app',
            email='existente@fogata.app',
            password='Password123!'
        )

    def test_password_reset_respuesta_visual_identica(self):
        """Muestra exactamente la misma respuesta sin revelar si el correo está registrado."""
        # 1. Correo que existe
        res_existente = self.client.post(reverse('password_reset'), {'email': 'existente@fogata.app'})
        self.assertEqual(res_existente.status_code, 302)
        res_done1 = self.client.get(reverse('password_reset_done'))
        self.assertEqual(res_done1.status_code, 200)

        # 2. Correo que NO existe
        res_inexistente = self.client.post(reverse('password_reset'), {'email': 'fantasma@noexiste.cl'})
        self.assertEqual(res_inexistente.status_code, 302)
        res_done2 = self.client.get(reverse('password_reset_done'))
        self.assertEqual(res_done2.status_code, 200)

        # Ambos muestran el mensaje ciego
        mensaje_esperado = "Si existe una cuenta asociada a ese correo, recibirás instrucciones para restablecer tu contraseña."
        self.assertContains(res_done1, mensaje_esperado)
        self.assertContains(res_done2, mensaje_esperado)


class HomeDiferenciadaPrimerUsuarioTest(TestCase):
    """
    Fase 6 — Criterios 20 y 21:
    - Landing pública para anónimos.
    - Pantalla de bienvenida ('Agrega tu primera canción') cuando canciones.count() == 0.
    - Home de repertorio cuando ya hay canciones.
    """

    def test_landing_publica_anonima(self):
        res = self.client.get(reverse('core:home'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Tus canciones. Tus acordes. Tu sesión.")
        self.assertContains(res, "Crear cuenta")
        self.assertContains(res, "Iniciar sesión")

    def test_bienvenida_primer_usuario_sin_canciones(self):
        user = User.objects.create_user(username='nuevo@fogata.app', email='nuevo@fogata.app', password='pass')
        self.client.force_login(user)

        res = self.client.get(reverse('core:home'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Bienvenido a Fogata")
        self.assertContains(res, "Agrega tu primera canción")
        self.assertContains(res, "+ Agregar primera canción")

    def test_home_con_repertorio(self):
        user = User.objects.create_user(username='activo@fogata.app', email='activo@fogata.app', password='pass')
        Cancion.objects.create(propietario=user, titulo="Canción 1", contenido="G\nLetra")
        self.client.force_login(user)

        res = self.client.get(reverse('core:home'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Mis canciones")
        self.assertContains(res, "Mis Fogatas")
        self.assertContains(res, "Nueva canción")
        self.assertContains(res, "Nueva Fogata")
