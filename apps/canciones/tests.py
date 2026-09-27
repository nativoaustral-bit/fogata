from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Cancion
from .services import obtener_solo_letra
from .parser import (
    parse_cancion,
    render_cancion_html,
    extraer_solo_letra,
    extraer_acordes_unicos,
    validar_token_acorde,
    LineaMusical,
    AcordeToken,
    compensar_espacios_en_linea,
    reemplazar_acorde_en_contenido,
    transponer_y_formatear_token,
    transponer_acorde_str,
    transponer_tonalidad,
    determinar_preferencia_alteraciones
)



class CancionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='musico_model@fogata.app',
            email='musico_model@fogata.app',
            password='password123'
        )

    def test_creacion_cancion_preserva_contenido_integro(self):
        """
        Verifica que el contenido con espacios, saltos de línea y acordes
        se preserve exactamente tal como fue ingresado (Criterio 1).
        """
        contenido_prueba = (
            "       Bm           G          D           A\n"
            "Viento nocturno sobre las colinas del sur\n"
            "   Bm            G           D        A\n"
            "Y una fogata encendida mirando la luz\n"
        )
        cancion = Cancion.objects.create(
            propietario=self.user,
            titulo="Canto Nocturno Ficticio",
            artista="Grupo Prueba",
            tonalidad="Bm",
            capo=0,
            afinacion="Estándar (E A D G B E)",
            contenido=contenido_prueba,
            notas_personales="Rasgueo en corcheas acentuando el 2 y 4"
        )

        # Comprobar que no hubo mutilación de espacios en base de datos
        self.assertEqual(cancion.contenido, contenido_prueba)
        self.assertEqual(str(cancion), "Canto Nocturno Ficticio - Grupo Prueba")
        self.assertEqual(cancion.get_tocar_url(), reverse('canciones:tocar', args=[cancion.pk]))


class ParserMusicalTest(TestCase):
    def test_reconocimiento_acordes_americanos(self):
        """
        Prueba acordes en notación americana: mayores, menores, séptimas,
        alteraciones (#, b), suspendidos, agregados y slash chords.
        """
        linea = "C  G  Am7  Fmaj7  Dsus4  Badd9  C#m7  Eb  A7#5  E5  G/B"
        lineas_parsed = parse_cancion(linea)
        self.assertEqual(len(lineas_parsed), 1)
        lm = lineas_parsed[0]
        self.assertEqual(lm.tipo, 'acordes')
        self.assertEqual(len(lm.tokens_acorde), 11)

        tokens = [t.texto_original for t in lm.tokens_acorde]
        self.assertIn("Am7", tokens)
        self.assertIn("Fmaj7", tokens)
        self.assertIn("C#m7", tokens)
        self.assertIn("G/B", tokens)

    def test_reconocimiento_acordes_latinos(self):
        """
        Prueba acordes en notación latina: Do, Re, Mi, Fa, Sol, La, Si.
        """
        linea = "Do  Sol  Lam  Rem7  Fa#m  Sib  Sol7  Re/Fa#  Sim7b5"
        lineas_parsed = parse_cancion(linea)
        self.assertEqual(len(lineas_parsed), 1)
        lm = lineas_parsed[0]
        self.assertEqual(lm.tipo, 'acordes')
        self.assertEqual(len(lm.tokens_acorde), 9)

        tokens = [t.texto_original for t in lm.tokens_acorde]
        self.assertIn("Do", tokens)
        self.assertIn("Lam", tokens)
        self.assertIn("Rem7", tokens)
        self.assertIn("Sib", tokens)
        self.assertIn("Re/Fa#", tokens)

    def test_mayusculas_y_semantica_cm7_vs_cm7(self):
        """
        Ajuste 3: Diferenciar correctamente Cm7 (menor séptima) de CM7 (mayor séptima).
        Preservar la distinción en el modificador y texto original.
        """
        val_menor = validar_token_acorde("Cm7")
        self.assertIsNotNone(val_menor)
        raiz_m, acc_m, mod_m, bajo_m = val_menor
        self.assertEqual(raiz_m, "C")
        self.assertEqual(mod_m, "m7")

        val_mayor = validar_token_acorde("CM7")
        self.assertIsNotNone(val_mayor)
        raiz_M, acc_M, mod_M, bajo_M = val_mayor
        self.assertEqual(raiz_M, "C")
        self.assertEqual(mod_M, "M7")

        self.assertNotEqual(mod_m, mod_M)

    def test_puntuacion_y_separadores_musicales(self):
        """
        Ajuste 2: Reconocer como líneas de acordes válidas aquellas que usan
        comas, guiones o barras de compás.
        """
        # Formato con comas
        l1 = parse_cancion("G, D, Em, C")[0]
        self.assertEqual(l1.tipo, 'acordes')
        self.assertEqual(len(l1.tokens_acorde), 4)

        # Formato con guiones
        l2 = parse_cancion("G - D - Em - C")[0]
        self.assertEqual(l2.tipo, 'acordes')
        self.assertEqual(len(l2.tokens_acorde), 4)

        # Formato con compases
        l3 = parse_cancion("| G | D | Em | C |")[0]
        self.assertEqual(l3.tipo, 'acordes')
        self.assertEqual(len(l3.tokens_acorde), 4)

    def test_acordes_embebidos(self):
        """
        Ajuste 4: Detección básica del formato [G]Cuando salga el [D]sol.
        Identifica únicamente el acorde dentro de corchetes preservando texto y espacios.
        """
        linea = "[G]Cuando salga el [D]sol de la mañana"
        parsed = parse_cancion(linea)[0]
        self.assertEqual(parsed.tipo, 'embebida')
        self.assertEqual(len(parsed.tokens_acorde), 2)
        self.assertEqual(parsed.tokens_acorde[0].texto_original, "G")
        self.assertEqual(parsed.tokens_acorde[1].texto_original, "D")

        # Renderizado HTML preserva corchetes y resalta solo el acorde
        html = render_cancion_html(linea)
        self.assertIn('[<span class="acorde">G</span>]Cuando salga el [<span class="acorde">D</span>]sol', html)

    def test_clasificacion_independiente_del_idioma_sin_falsos_positivos(self):
        """
        Ajuste 1: No clasificar como acordes versos con palabras ambiguas
        (A, La, Si, Sol, Do) en español, inglés, portugués u otros idiomas.
        """
        # Español con 'A', 'la', 'sol', 'si'
        l_es = parse_cancion("A la sombra de mi casa, si tú quieres mirar el sol")[0]
        self.assertEqual(l_es.tipo, 'letra')
        self.assertEqual(len(l_es.tokens_acorde), 0)

        # Inglés con 'A', 'in', 'the', 'sun'
        l_en = parse_cancion("A friend of mine was walking in the summer night")[0]
        self.assertEqual(l_en.tipo, 'letra')
        self.assertEqual(len(l_en.tokens_acorde), 0)

        # Portugués con 'A', 'do', 'mar'
        l_pt = parse_cancion("A canção do vento sopra forte na beira do mar")[0]
        self.assertEqual(l_pt.tipo, 'letra')
        self.assertEqual(len(l_pt.tokens_acorde), 0)

    def test_secciones_y_tablaturas(self):
        """
        Reconocer encabezados [Intro], [Coro], Intro: y tablaturas sin romper espaciado.
        """
        texto = (
            "[Intro]\n"
            "G  D  Em  C\n\n"
            "e|---0---2---0---|\n"
            "B|---1---3---1---|\n"
            "Coro:\n"
            "[G]Canta con el [C]viento\n"
        )
        parsed = parse_cancion(texto)
        self.assertEqual(parsed[0].tipo, 'seccion')
        self.assertEqual(parsed[1].tipo, 'acordes')
        self.assertEqual(parsed[2].tipo, 'vacia')
        self.assertEqual(parsed[3].tipo, 'tablatura')
        self.assertEqual(parsed[4].tipo, 'tablatura')
        self.assertEqual(parsed[5].tipo, 'seccion')
        self.assertEqual(parsed[6].tipo, 'embebida')

    def test_preservacion_espacial_exacta_en_html(self):
        """
        Criterio 4: Verificar que los espacios intermedios e iniciales se preserven
        idénticos tras el renderizado con etiquetas <span>.
        """
        linea_original = "       Bm           G          D           A"
        html = render_cancion_html(linea_original)

        # Al quitar las etiquetas HTML, el texto resultante debe ser exactamente igual
        import re
        texto_sin_tags = re.sub(r'<[^>]+>', '', html)
        self.assertEqual(texto_sin_tags, linea_original)

    def test_seguridad_escape_xss(self):
        """
        Ajuste 6: Todo contenido procedente del usuario debe ser escapado.
        Inyección maliciosa no debe generar tags ejecutables.
        """
        peligro = "[G]<script>alert('xss')</script>[D]"
        html = render_cancion_html(peligro)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn('<span class="acorde">G</span>', html)
        self.assertIn('<span class="acorde">D</span>', html)

    def test_extraer_acordes_unicos(self):
        """
        Ajuste 5: Preparación para futuras funciones de diagramas.
        """
        texto = "G  D  G  Em  C  D  G"
        parsed = parse_cancion(texto)
        unicos = extraer_acordes_unicos(parsed)
        self.assertEqual(unicos, ['G', 'D', 'Em', 'C'])

    def test_extraer_solo_letra(self):
        """
        Verifica que el servicio de solo letra omita líneas de acordes y tablatura,
        y limpie acordes embebidos.
        """
        texto = (
            "[Intro]\n"
            "G  D  Em  C\n"
            "e|---0---|\n"
            "[G]Baja la tarde sobre el [C]sauzal\n"
            "Y una fogata comienza a brillar\n"
        )
        letra = extraer_solo_letra(texto)
        self.assertNotIn("G  D  Em  C", letra)
        self.assertNotIn("e|---0---|", letra)
        self.assertIn("Baja la tarde sobre el sauzal", letra)
        self.assertIn("Y una fogata comienza a brillar", letra)


class CancionViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='musico_views@fogata.app',
            email='musico_views@fogata.app',
            password='password123'
        )
        self.client.force_login(self.user)
        self.cancion = Cancion.objects.create(
            propietario=self.user,
            titulo="Canción del Amanecer Ficticia",
            artista="Banda de Prueba",
            tonalidad="F",
            capo=0,
            contenido="    F        Bb\nLuz de la mañana sobre el cristal..."
        )

    def test_lista_canciones(self):
        response = self.client.get(reverse('canciones:lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Canción del Amanecer Ficticia")

    def test_busqueda_canciones(self):
        response = self.client.get(reverse('canciones:lista') + '?q=Amanecer')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Banda de Prueba")

    def test_detalle_cancion_renderiza_acordes_en_preview(self):
        response = self.client.get(reverse('canciones:detalle', args=[self.cancion.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="acorde"')
        self.assertContains(response, '>F</span>')
        self.assertContains(response, '>Bb</span>')

    def test_tocar_cancion_renderiza_acordes_en_atril(self):
        response = self.client.get(reverse('canciones:tocar', args=[self.cancion.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="acorde"')
        self.assertContains(response, '>F</span>')
        self.assertContains(response, '>Bb</span>')
        self.assertContains(response, 'letra-acordes-musico')

    def test_crear_y_preservar_espacios(self):
        contenido_exacto = (
            "   G       Em\n"
            "Sol en la ventana...\n\n"
            "   C          D7       G\n"
            "Brilla la mañana en paz\n"
        )
        data = {
            'titulo': 'Sol de la Ventana Ficticia',
            'artista': 'Autor Prueba',
            'tonalidad': 'G',
            'capo': '0',
            'afinacion': 'Estándar',
            'contenido': contenido_exacto,
            'notas_personales': 'Intro acústica suave'
        }
        response = self.client.post(reverse('canciones:crear'), data=data)
        self.assertEqual(response.status_code, 302)
        nueva = Cancion.objects.get(titulo='Sol de la Ventana Ficticia')
        self.assertEqual(nueva.contenido, contenido_exacto)

    def test_eliminar_cancion(self):
        response_post = self.client.post(reverse('canciones:eliminar', args=[self.cancion.pk]))
        self.assertEqual(response_post.status_code, 302)
        self.assertFalse(Cancion.objects.filter(pk=self.cancion.pk).exists())


class Fase1ValidacionRealTest(TestCase):
    """
    Suite de Validación Real para Fase 1.1 (Criterios 1 al 15 de Aceptación).
    Verifica que el flujo 'copiar -> pegar -> guardar -> tocar' sea robusto.
    """
    def setUp(self):
        self.user = User.objects.create_user(
            username='musico_fase1@fogata.app',
            email='musico_fase1@fogata.app',
            password='password123'
        )
        self.client.force_login(self.user)

    def test_01_preservacion_de_espacios(self):
        """1. Preservación estricta de espacios antes, entre y después de acordes."""
        linea = "       G              D"
        html = render_cancion_html(linea)
        import re
        texto_limpio = re.sub(r'<[^>]+>', '', html)
        self.assertEqual(texto_limpio, linea)
        self.assertTrue(html.startswith("       <span class=\"acorde\">G</span>              <span class=\"acorde\">D</span>"))

    def test_02_acordes_en_lineas_independientes(self):
        """2. Formato A: Acordes sobre letra en líneas separadas."""
        formato_a = (
            "       G              D\n"
            "Cuando llegue la mañana\n"
            "\n"
            "       Em             C\n"
            "seguiremos el camino"
        )
        cancion = Cancion.objects.create(
            propietario=self.user,
            titulo="Formato A Test",
            artista="Banda A",
            contenido=formato_a
        )
        self.assertEqual(cancion.contenido, formato_a)

        html = render_cancion_html(formato_a)
        self.assertIn('<span class="acorde">G</span>', html)
        self.assertIn('<span class="acorde">D</span>', html)
        self.assertIn('<span class="acorde">Em</span>', html)
        self.assertIn('<span class="acorde">C</span>', html)
        self.assertIn("Cuando llegue la mañana", html)
        self.assertIn("seguiremos el camino", html)

    def test_03_acordes_embebidos(self):
        """3. Formato B: Acordes entre corchetes sin alterar letra ni perder corchetes."""
        formato_b = (
            "[G]Cuando llegue la [D]mañana\n"
            "[Em]seguiremos el [C]camino"
        )
        html = render_cancion_html(formato_b)
        self.assertIn('[<span class="acorde">G</span>]Cuando llegue la [<span class="acorde">D</span>]mañana', html)
        self.assertIn('[<span class="acorde">Em</span>]seguiremos el [<span class="acorde">C</span>]camino', html)

    def test_04_progresiones(self):
        """4. Formato C: Progresiones con barras, guiones o comas."""
        formato_c = "| G | D | Em | C |"
        lineas = parse_cancion(formato_c)
        self.assertEqual(lineas[0].tipo, 'acordes')
        self.assertEqual(len(lineas[0].tokens_acorde), 4)

        html = render_cancion_html(formato_c)
        self.assertEqual(
            html,
            '| <span class="acorde">G</span> | <span class="acorde">D</span> | <span class="acorde">Em</span> | <span class="acorde">C</span> |'
        )

    def test_05_notacion_latina(self):
        """5. Formato E: Notación latina (Sol, Re, Mim, Do, Fa#, Lam)."""
        formato_e = (
            "Sol             Re\n"
            "Texto ficticio\n\n"
            "Mim             Do\n"
            "Texto ficticio"
        )
        html = render_cancion_html(formato_e)
        self.assertIn('<span class="acorde">Sol</span>             <span class="acorde">Re</span>', html)
        self.assertIn('<span class="acorde">Mim</span>             <span class="acorde">Do</span>', html)

    def test_06_notacion_americana(self):
        """6. Notación americana completa con alteraciones, números y slash."""
        linea = "C  G/B  Am7  F#m7b5  Dsus4  Ebadd9"
        html = render_cancion_html(linea)
        self.assertIn('<span class="acorde">G/B</span>', html)
        self.assertIn('<span class="acorde">F#m7b5</span>', html)
        self.assertIn('<span class="acorde">Dsus4</span>', html)
        self.assertIn('<span class="acorde">Ebadd9</span>', html)

    def test_07_secciones(self):
        """7. Formato D: Secciones diferenciadas visualmente sin alterar estructura."""
        formato_d = (
            "[Intro]\n"
            "G D Em C\n\n"
            "[Verso]\n"
            "G              D\n"
            "Texto ficticio de prueba\n\n"
            "[Coro]\n"
            "Em             C\n"
            "Texto ficticio de prueba"
        )
        html = render_cancion_html(formato_d)
        self.assertIn('<span class="seccion-musical">[Intro]</span>', html)
        self.assertIn('<span class="seccion-musical">[Verso]</span>', html)
        self.assertIn('<span class="seccion-musical">[Coro]</span>', html)

    def test_08_tablaturas(self):
        """8. Formato F: Tablaturas legibles e intactas sin acordes erróneos."""
        tabs = (
            "e|-------------------\n"
            "B|-----3-------------\n"
            "G|---2---------------"
        )
        lineas = parse_cancion(tabs)
        for l in lineas:
            self.assertEqual(l.tipo, 'tablatura')
            self.assertEqual(len(l.tokens_acorde), 0)

        html = render_cancion_html(tabs)
        # No debe haber spans de acordes en las cuerdas de tablatura
        self.assertNotIn('<span class="acorde">', html)
        self.assertEqual(html, tabs)

    def test_09_contenido_desconocido_no_desaparece_ni_falla(self):
        """9. Ninguna línea dudosa desaparece ni genera excepción."""
        mixto = (
            "Intro: G - D - Em - C\n\n"
            "G                  D\n"
            "Texto ficticio de prueba\n\n"
            "Nota: tocar suave con púa fina\n"
            "Observación: Capo en traste 2 para la segunda guitarra\n"
            "e|---0-2-3---"
        )
        # Parse y render sin error
        html = render_cancion_html(mixto)
        self.assertIn("Nota: tocar suave con púa fina", html)
        self.assertIn("Observación: Capo en traste 2 para la segunda guitarra", html)
        self.assertIn("e|---0-2-3---", html)
        self.assertIn('<span class="acorde">G</span>', html)

    def test_10_pegado_desde_navegador_configuracion_textarea(self):
        """10. Textarea configurado para recibir texto plano sin auto-correcciones móviles ni wrap."""
        from .forms import CancionForm
        form = CancionForm()
        widget = form.fields['contenido'].widget
        attrs = widget.attrs
        self.assertEqual(attrs.get('wrap'), 'off')
        self.assertEqual(attrs.get('autocapitalize'), 'off')
        self.assertEqual(attrs.get('autocorrect'), 'off')
        self.assertEqual(attrs.get('spellcheck'), 'false')
        self.assertFalse(form.fields['contenido'].strip)

    def test_11_flujo_pegar_y_tocar_inmediato_y_edicion(self):
        """11. Flujo 'Pegar y Tocar' con Guardar y Tocar, y posterior edición."""
        data_crear = {
            'titulo': 'Canción Inmediata',
            'artista': 'Banda Inmediata',
            'contenido': '   G       D\nCantar en paz...',
            'accion_guardar': 'tocar'
        }
        res_crear = self.client.post(reverse('canciones:crear'), data=data_crear)
        cancion = Cancion.objects.get(titulo='Canción Inmediata')
        # Redirección inmediata a Tocar (Modo Músico)
        self.assertRedirects(res_crear, reverse('canciones:tocar', args=[cancion.pk]))

        # Edición posterior
        data_editar = {
            'titulo': 'Canción Inmediata (Corregida)',
            'artista': 'Banda Inmediata',
            'contenido': '   G       D        Em\nCantar en paz y libertad...',
            'accion_guardar': 'tocar'
        }
        res_editar = self.client.post(reverse('canciones:editar', args=[cancion.pk]), data=data_editar)
        self.assertRedirects(res_editar, reverse('canciones:tocar', args=[cancion.pk]))
        cancion.refresh_from_db()
        self.assertEqual(cancion.titulo, 'Canción Inmediata (Corregida)')
        self.assertIn('Em', cancion.contenido)

    def test_12_seguridad_xss(self):
        """12. Contenido malicioso escapado rigurosamente; no se inyecta HTML ejecutable."""
        xss_payload = '<img src=x onerror=alert(1)> [G] <script>alert("hack")</script>'
        html = render_cancion_html(xss_payload)
        self.assertNotIn('<img src=x', html)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', html)
        self.assertIn('&lt;script&gt;alert(&quot;hack&quot;)&lt;/script&gt;', html)
        self.assertIn('<span class="acorde">G</span>', html)

    def test_13_funcionamiento_sin_javascript(self):
        """13. Modo Tocar y Detalle son 100% renderizados en servidor con HTML puro."""
        cancion = Cancion.objects.create(
            propietario=self.user,
            titulo="Canción No-JS",
            artista="Autor No-JS",
            contenido="   A      E\nCaminando sin prisa..."
        )
        res_tocar = self.client.get(reverse('canciones:tocar', args=[cancion.pk]))
        self.assertEqual(res_tocar.status_code, 200)
        # Acordes ya vienen con clase .acorde desde el servidor
        self.assertContains(res_tocar, 'class="acorde"')
        self.assertContains(res_tocar, '>A</span>')
        self.assertContains(res_tocar, '>E</span>')

    def test_14_visualizacion_movil_clases_y_estilos(self):
        """14. Modo tocar incluye contenedor de atril monoespaciado y con scroll horizontal seguro."""
        cancion = Cancion.objects.create(
            propietario=self.user,
            titulo="Test Móvil",
            artista="Autor Móvil",
            contenido="G       C\nUna sola columna..."
        )
        res = self.client.get(reverse('canciones:tocar', args=[cancion.pk]))
        self.assertContains(res, 'class="letra-acordes-wrapper"')
        self.assertContains(res, 'class="letra-acordes-musico"')

    def test_15_visualizacion_tablet_y_datos_opcionales(self):
        """15. La vista de crear/editar contiene el bloque details con los datos opcionales."""
        res_form = self.client.get(reverse('canciones:crear'))
        self.assertEqual(res_form.status_code, 200)
        self.assertContains(res_form, '<details')
        self.assertContains(res_form, 'Datos adicionales opcionales')
        self.assertContains(res_form, 'Guardar y Tocar')


class Fase2ModoTocarTest(TestCase):
    """
    Pruebas automatizadas para Fase 2:
    Modo Tocar, Auto-Scroll, Velocidad Ajustable y Navegación por Bloques.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='musico_fase2@fogata.app',
            email='musico_fase2@fogata.app',
            password='password123'
        )
        self.client.force_login(self.user)
        self.cancion = Cancion.objects.create(
            propietario=self.user,
            titulo="Canción Test Fase 2",
            artista="Banda de Atril",
            tonalidad="G",
            capo=2,
            afinacion="Estándar",
            contenido=(
                "[Intro]\n"
                "G  D  Em  C\n\n"
                "[Verso 1]\n"
                "G              D\n"
                "Luz de la mañana sobre la colina\n\n"
                "[Coro]\n"
                "Em             C\n"
                "Canta fuerte junto al río\n"
            )
        )

    def test_renderizado_barra_inferior_y_controles(self):
        """Verifica la presencia de la barra fija inferior y todos los controles mínimos."""
        res = self.client.get(reverse('canciones:tocar', args=[self.cancion.pk]))
        self.assertEqual(res.status_code, 200)
        # Barra fija inferior
        self.assertContains(res, 'id="atril-bottom-bar"')
        self.assertContains(res, 'class="atril-bottom-bar"')
        # Play / Pausa
        self.assertContains(res, 'id="btn-scroll-toggle"')
        self.assertContains(res, 'id="icono-scroll-play"')
        self.assertContains(res, 'id="texto-scroll-play"')
        # Velocidad
        self.assertContains(res, 'id="btn-vel-menos"')
        self.assertContains(res, 'id="btn-vel-mas"')
        self.assertContains(res, 'id="indicador-velocidad"')
        # Navegación por bloques
        self.assertContains(res, 'id="btn-bloque-ant"')
        self.assertContains(res, 'id="btn-bloque-sig"')
        # Espaciador inferior para que los últimos versos nunca queden tapados
        self.assertContains(res, 'class="atril-bottom-spacer"')

    def test_dimensiones_tactiles_minimas_48px(self):
        """Verifica que el CSS declare min-height y min-width de al menos 48px para los controles de atril."""
        with open('static/css/fogata.css', 'r', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('.atril-bar-btn', css)
        self.assertIn('min-width: 48px;', css)
        self.assertIn('min-height: 48px;', css)
        self.assertIn('.atril-play-btn', css)
        self.assertIn('min-height: 48px;', css)

    def test_compatibilidad_js_sintaxis_es5(self):
        """Verifica que fogata.js contiene la lógica requerida en ES5 estricto sin dependencias."""
        with open('static/js/fogata.js', 'r', encoding='utf-8') as f:
            js = f.read()
        self.assertIn("'use strict';", js)
        self.assertIn('initAutoScrollAndBloques', js)
        self.assertIn('fogata_scroll_speed', js)
        self.assertIn('recalcularBloques', js)
        self.assertIn('onManualUserScroll', js)
        self.assertIn('visibilitychange', js)
        # No debe usar const ni arrow functions
        self.assertNotIn('const ', js)
        self.assertNotIn('let ', js)
        self.assertNotIn('=>', js)

    def test_servidor_legacy_first_sin_javascript(self):
        """Verifica que sin JavaScript el usuario puede leer completamente la canción y acordes."""
        res = self.client.get(reverse('canciones:tocar', args=[self.cancion.pk]))
        self.assertEqual(res.status_code, 200)
        # Contenido 100% visible desde el HTML generado por el servidor
        self.assertContains(res, 'Luz de la mañana sobre la colina')
        self.assertContains(res, '<span class="seccion-musical">[Intro]</span>')
        self.assertContains(res, '<span class="seccion-musical">[Coro]</span>')
        self.assertContains(res, 'class="acorde"')
        self.assertContains(res, '>G</span>')
        self.assertContains(res, '>Em</span>')


# =============================================================================
# Pruebas Automatizadas Fase 3: Gestión, Edición Rápida, Notación y Transposición
# =============================================================================

class Fase3GestionAcordesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='musico_fase3@fogata.app',
            email='musico_fase3@fogata.app',
            password='password123'
        )
        self.client.force_login(self.user)
        self.cancion = Cancion.objects.create(
            propietario=self.user,
            titulo="Canción Test Fase 3",
            artista="Guitarrista Ficticio",
            tonalidad="G",
            capo=0,
            contenido=(
                "[Intro]\n"
                "G              D\n\n"
                "[Verso 1]\n"
                "[G]Luz de la mañana sobre la [C]colina\n"
                "G              D              Em             C\n"
                "Río cristalino que corre hacia el mar\n\n"
                "[Coro]\n"
                "G/B            C              D              G\n"
                "Canta fuerte junto al fogón\n"
            )
        )

    def test_edicion_acorde_embebido(self):
        """18.1. Edición de acorde embebido ([G] -> [G7]) sin compensación espacial."""
        contenido = "[G]Palabra [D]otra"
        exito, nuevo_contenido, err = reemplazar_acorde_en_contenido(
            contenido=contenido,
            num_linea=0,
            col_inicio=1,
            col_fin=2,
            texto_original='G',
            nuevo_acorde='G7',
            modo='uno'
        )
        self.assertTrue(exito)
        self.assertEqual(nuevo_contenido, "[G7]Palabra [D]otra")

    def test_edicion_G_a_Gmaj7_conservando_columna_posterior(self):
        """18.2. Edición G -> Gmaj7 conservando la columna de inicio del acorde posterior D."""
        linea_original = "G              D"
        # G está en 0..1, D empieza en índice 15
        col_D_original = linea_original.index("D")
        self.assertEqual(col_D_original, 15)

        exito, nueva_linea, err = reemplazar_acorde_en_contenido(
            contenido=linea_original,
            num_linea=0,
            col_inicio=0,
            col_fin=1,
            texto_original='G',
            nuevo_acorde='Gmaj7',
            modo='uno'
        )
        self.assertTrue(exito)
        self.assertEqual(nueva_linea, "Gmaj7          D")
        self.assertEqual(nueva_linea.index("D"), col_D_original)

    def test_reduccion_Gmaj7_a_G_conservando_columna_posterior(self):
        """18.3. Reducción Gmaj7 -> G insertando espacios para conservar la columna de D."""
        linea_original = "Gmaj7          D"
        col_D_original = linea_original.index("D")
        self.assertEqual(col_D_original, 15)

        exito, nueva_linea, err = reemplazar_acorde_en_contenido(
            contenido=linea_original,
            num_linea=0,
            col_inicio=0,
            col_fin=5,
            texto_original='Gmaj7',
            nuevo_acorde='G',
            modo='uno'
        )
        self.assertTrue(exito)
        self.assertEqual(nueva_linea, "G              D")
        self.assertEqual(nueva_linea.index("D"), col_D_original)

    def test_reemplazo_global_multiples_acordes_misma_linea(self):
        """18.4. Reemplazo global (modo='todos') con múltiples acordes en la misma línea sin tocar letra ni tabs."""
        contenido = (
            "G              G\n"
            "Palabras con G y letra de canción\n"
            "e|---G---|\n"
        )
        exito, nuevo_contenido, err = reemplazar_acorde_en_contenido(
            contenido=contenido,
            num_linea=0,
            col_inicio=0,
            col_fin=1,
            texto_original='G',
            nuevo_acorde='Gmaj7',
            modo='todos'
        )
        self.assertTrue(exito)
        lineas = nuevo_contenido.splitlines()
        self.assertEqual(lineas[0], "Gmaj7          Gmaj7")
        self.assertEqual(lineas[1], "Palabras con G y letra de canción")
        self.assertEqual(lineas[2], "e|---G---|")

    def test_transposicion_acorde_con_bajo_slash(self):
        """18.5. Transposición de acorde con bajo slash (raíz y bajo se transponen consistentemente)."""
        # G/B + 2 semitonos -> A/C#
        resultado = transponer_acorde_str("G/B", semitonos=2, notacion='american')
        self.assertEqual(resultado, "A/C#")

        # C/E + 1 semitono con bemoles -> Db/F
        resultado_b = transponer_acorde_str("C/E", semitonos=1, usar_bemoles=True, notacion='american')
        self.assertEqual(resultado_b, "Db/F")

    def test_transposicion_combinada_con_notacion_latina(self):
        """18.6. Transposición combinada con notación latina (C#m7 -> Rem7, Bb -> Si, G/B -> La/Do#)."""
        res1 = transponer_acorde_str("C#m7", semitonos=1, notacion='latin')
        self.assertEqual(res1, "Rem7")

        res2 = transponer_acorde_str("Bb", semitonos=1, notacion='latin')
        self.assertEqual(res2, "Si")

        res3 = transponer_acorde_str("G/B", semitonos=2, notacion='latin')
        self.assertEqual(res3, "La/Do#")

    def test_consistencia_sostenidos_bemoles_cancion_completa(self):
        """18.7. Consistencia determinista de sostenidos y bemoles en una canción completa (Criterio 6)."""
        # Prioridad 1: tonalidad explícita
        self.assertTrue(determinar_preferencia_alteraciones("", tonalidad="F", semitonos=0))
        self.assertTrue(determinar_preferencia_alteraciones("", tonalidad="Bb", semitonos=0))
        self.assertFalse(determinar_preferencia_alteraciones("", tonalidad="A", semitonos=0))
        self.assertFalse(determinar_preferencia_alteraciones("", tonalidad="G", semitonos=0))

        # Prioridad 2: predominio de alteraciones en acordes
        contenido_bemoles = "Eb        Bb\nAb       Fm"
        self.assertTrue(determinar_preferencia_alteraciones(contenido_bemoles, tonalidad="", semitonos=0))

        contenido_sostenidos = "F#m       C#m\nG#m      D#"
        self.assertFalse(determinar_preferencia_alteraciones(contenido_sostenidos, tonalidad="", semitonos=0))

        # Prioridad 3: acordes naturales neutros según dirección de transposición
        contenido_natural = "C   G   Am   F"
        self.assertTrue(determinar_preferencia_alteraciones(contenido_natural, tonalidad="", semitonos=-2))
        self.assertFalse(determinar_preferencia_alteraciones(contenido_natural, tonalidad="", semitonos=2))

    def test_parametro_semitonos_fuera_de_rango(self):
        """18.8. Parámetro semitonos fuera de rango (-6 a +6) o inválido vuelve a 0 de forma segura."""
        res_alto = self.client.get(reverse('canciones:tocar', args=[self.cancion.pk]) + '?semitonos=12')
        self.assertEqual(res_alto.status_code, 200)
        self.assertEqual(res_alto.context['semitonos'], 0)

        res_bajo = self.client.get(reverse('canciones:tocar', args=[self.cancion.pk]) + '?semitonos=-10')
        self.assertEqual(res_bajo.status_code, 200)
        self.assertEqual(res_bajo.context['semitonos'], 0)

        res_texto = self.client.get(reverse('canciones:tocar', args=[self.cancion.pk]) + '?semitonos=invalido')
        self.assertEqual(res_texto.status_code, 200)
        self.assertEqual(res_texto.context['semitonos'], 0)

    def test_fallback_servidor_sin_javascript(self):
        """18.9. Fallback servidor sin JavaScript: el servidor renderiza acordes transpuestos y notación por GET."""
        url = reverse('canciones:tocar', args=[self.cancion.pk]) + '?semitonos=2&notacion=latin'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        # G (+2 semitonos en notación latina) -> La
        self.assertContains(res, '>La</span>')
        # D (+2 semitonos en notación latina) -> Mi
        self.assertContains(res, '>Mi</span>')
        # Enlaces para cambiar medio tono y reset están presentes
        self.assertContains(res, 'id="btn-tono-bajar"')
        self.assertContains(res, 'id="btn-tono-subir"')
        self.assertContains(res, 'id="btn-tono-reset"')
        self.assertContains(res, 'id="btn-toggle-notacion"')

    def test_contenido_con_html_malicioso_durante_edicion(self):
        """18.10. Validación y rechazo de HTML malicioso durante la edición rápida de acordes."""
        url_guardar = reverse('canciones:guardar_edicion_acorde', args=[self.cancion.pk])
        payload = {
            'num_linea': 1,
            'col_inicio': 0,
            'col_fin': 1,
            'texto_original': 'G',
            'nuevo_acorde': '<script>alert("xss")</script>',
            'modo': 'uno'
        }
        res = self.client.post(url_guardar, payload, follow=True)
        self.cancion.refresh_from_db()
        # No debe haber modificado el contenido con HTML malicioso
        self.assertNotIn('<script>', self.cancion.contenido)
        # Mensaje de validación amigable al usuario
        self.assertContains(res, "No reconocemos este acorde")

    def test_retorno_a_tono_original_manteniendo_notacion_seleccionada(self):
        """18.11. Retorno a tono original (semitonos=0) manteniendo la preferencia visual latina."""
        url = reverse('canciones:tocar', args=[self.cancion.pk]) + '?semitonos=0&notacion=latin'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        # G en notación latina sin transposición es Sol
        self.assertContains(res, '>Sol</span>')
        # D en notación latina sin transposición es Re
        self.assertContains(res, '>Re</span>')

    def test_concurrencia_e_integridad_cancion_modificada(self):
        """5. Validación de concurrencia e integridad ante cambios en el contenido guardado."""
        url_guardar = reverse('canciones:guardar_edicion_acorde', args=[self.cancion.pk])
        payload = {
            'num_linea': 1,
            'col_inicio': 99,  # Posición inexistente o desfasada
            'col_fin': 105,
            'texto_original': 'G',
            'nuevo_acorde': 'G7',
            'modo': 'uno'
        }
        res = self.client.post(url_guardar, payload, follow=True)
        self.assertContains(res, "La canción cambió desde que abriste el editor. Recarga antes de modificar este acorde.")

    def test_vista_editar_acordes_renderiza_correctamente(self):
        """Verifica que la vista editar_acordes renderice con clase .acorde-editable y formulario."""
        url = reverse('canciones:editar_acordes', args=[self.cancion.pk])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'acorde-editable')
        self.assertContains(res, 'data-linea=')
        self.assertContains(res, 'data-inicio=')
        self.assertContains(res, 'id="form-edicion-acorde"')

    def test_acordes_unicos_de_cancion_reflejan_transposicion_y_notacion(self):
        """16. Acordes únicos reflejan transposición y notación activa."""
        lineas = parse_cancion(self.cancion.contenido)
        acordes_orig = extraer_acordes_unicos(lineas, semitonos=0, notacion='original')
        self.assertIn("G", acordes_orig)
        self.assertIn("D", acordes_orig)

        acordes_transp_latin = extraer_acordes_unicos(lineas, semitonos=2, notacion='latin')
        self.assertIn("La", acordes_transp_latin)
        self.assertIn("Mi", acordes_transp_latin)

    def test_javascript_es5_fase3_sintaxis_y_funciones(self):
        """Verifica que fogata.js incorpora la lógica de Fase 3 en ES5 sin dependencias."""
        with open('static/js/fogata.js', 'r', encoding='utf-8') as f:
            js = f.read()
        self.assertIn('initTransposicionYNotacion', js)
        self.assertIn('initEdicionAcordesRapida', js)
        self.assertIn('fogata_chord_notation', js)
        self.assertIn('transformarAcordeSpan', js)
        # Garantizar que no se colaron sintaxis ES6
        self.assertNotIn('const ', js)
        self.assertNotIn('let ', js)
        self.assertNotIn('=>', js)


class Fase4DiagramasAcordesTest(TestCase):
    """
    Pruebas completas de la Fase 4: Diagramas de Acordes para Guitarra.
    Cubre validación armónica de biblioteca, detección de digitaciones inválidas,
    comportamiento de capo y afinación alternativa, endpoint canónico /canciones/diagrama/,
    seguridad XSS, accesibilidad SVG, fallback sin JavaScript con retorno seguro,
    flujo en Fogatas/setlists y preservación métrica.
    """

    def setUp(self):
        from apps.canciones.diagramas import (
            BIBLIOTECA_ACORDES,
            validar_digitacion_musical,
            calcular_clases_altura,
            obtener_info_diagrama,
            generar_svg_acorde,
            DigitacionAcorde
        )
        self.BIBLIOTECA_ACORDES = BIBLIOTECA_ACORDES
        self.validar_digitacion_musical = validar_digitacion_musical
        self.calcular_clases_altura = calcular_clases_altura
        self.obtener_info_diagrama = obtener_info_diagrama
        self.generar_svg_acorde = generar_svg_acorde
        self.DigitacionAcorde = DigitacionAcorde

        self.user = User.objects.create_user(
            username='musico_fase4@fogata.app',
            email='musico_fase4@fogata.app',
            password='password123'
        )
        self.client.force_login(self.user)

        self.cancion_std = Cancion.objects.create(
            propietario=self.user,
            titulo="Cancion EADGBE",
            artista="Banda Acustica",
            tonalidad="G",
            capo=0,
            afinacion="Estándar (E A D G B E)",
            contenido="G     C     D\nLetra de prueba en afinacion estandar"
        )
        self.cancion_capo = Cancion.objects.create(
            propietario=self.user,
            titulo="Cancion con Capo",
            artista="Trovador",
            tonalidad="G",
            capo=2,
            afinacion="Estándar",
            contenido="G     Em    C     D\nCantando con capo en segundo traste"
        )
        self.cancion_drop_d = Cancion.objects.create(
            propietario=self.user,
            titulo="Cancion Alternativa",
            artista="Rockero",
            tonalidad="D",
            capo=0,
            afinacion="Drop D",
            contenido="D     G     A\nSonido pesado en Drop D"
        )

    def test_validacion_armonica_biblioteca_completa(self):
        """
        Criterios 1, 2 y 18:
        Comprueba que TODAS las 64 posiciones en la biblioteca inicial sean
        musicalmente válidas contra la afinación estándar.
        """
        self.assertGreaterEqual(len(self.BIBLIOTECA_ACORDES), 60)
        for (root_pitch, mod, bass_pitch), digitacion in self.BIBLIOTECA_ACORDES.items():
            valida, razon = self.validar_digitacion_musical(root_pitch, mod, digitacion, bass_pitch)
            self.assertTrue(
                valida,
                f"Fallo en acorde root={root_pitch}, mod='{mod}', bass={bass_pitch}: {razon} (trastes={digitacion.trastes})"
            )

    def test_sus4_sin_tercera(self):
        """
        Criterios 1 y 2:
        Comprueba que Csus4 y todos los sus4 contengan raíz, 4ta y 5ta,
        y NO contengan tercera mayor ni menor.
        """
        # Csus4 = x33011 -> notas C, F, G, C, F (pitches 0, 5, 7)
        c_sus4 = self.BIBLIOTECA_ACORDES.get((0, 'sus4', None))
        self.assertIsNotNone(c_sus4)
        notas, _ = self.calcular_clases_altura(c_sus4.trastes)
        self.assertIn(0, notas)  # Raíz C
        self.assertIn(5, notas)  # 4ta F
        self.assertIn(7, notas)  # 5ta G
        self.assertNotIn(4, notas)  # NO tercera mayor (E)
        self.assertNotIn(3, notas)  # NO tercera menor (Eb)

    def test_sus2_sin_tercera(self):
        """
        Criterio 2:
        Comprueba que Dsus2 y acordes sus2 contengan raíz, 2da y 5ta,
        y NO contengan tercera mayor ni menor.
        """
        d_sus2 = self.BIBLIOTECA_ACORDES.get((2, 'sus2', None))
        self.assertIsNotNone(d_sus2)
        notas, _ = self.calcular_clases_altura(d_sus2.trastes)
        self.assertIn(2, notas)  # Raíz D
        self.assertIn(4, notas)  # 2da E
        self.assertIn(9, notas)  # 5ta A
        self.assertNotIn(6, notas)  # NO F# (3ra mayor)
        self.assertNotIn(5, notas)  # NO F (3ra menor)

    def test_slash_chord_con_bajo_correcto(self):
        """
        Criterio 3:
        Para G/B, la nota más grave que efectivamente suena DEBE ser B.
        Para D/F#, la nota más grave que efectivamente suena DEBE ser F#.
        """
        g_on_b = self.BIBLIOTECA_ACORDES.get((7, '', 11))
        self.assertIsNotNone(g_on_b)
        valido, razon = self.validar_digitacion_musical(7, '', g_on_b, 11)
        self.assertTrue(valido, razon)

        # Trastes G/B: [-1, 2, 0, 0, 3, 3] -> cuerda 5 en traste 2 es B (pitch 11)
        cuerda_bajo_idx = next(i for i, t in enumerate(g_on_b.trastes) if t != -1)
        self.assertEqual(cuerda_bajo_idx, 1)  # Cuerda 5 (índice 1 en array 0..5 de 6ª a 1ª)

        d_on_fsharp = self.BIBLIOTECA_ACORDES.get((2, '', 6))
        self.assertIsNotNone(d_on_fsharp)
        valido, razon = self.validar_digitacion_musical(2, '', d_on_fsharp, 6)
        self.assertTrue(valido, razon)
        self.assertEqual(d_on_fsharp.trastes[0], 2)  # Cuerda 6 en traste 2 = F# (pitch 6)

    def test_detector_digitacion_invalida(self):
        """
        Criterio 2 y 20:
        Comprueba que validar_digitacion_musical detecte y rechace errores:
        - Csus4 con primera cuerda al aire (contiene tercera mayor E).
        - G/B donde suena la sexta cuerda al aire (bajo es E en vez de B).
        - Mayor sin tercera.
        """
        # Digitacion con error: Csus4 con traste 0 en 1ra cuerda (E)
        pos_erronea_csus4 = self.DigitacionAcorde(trastes=[-1, 3, 3, 0, 1, 0])
        valido, razon = self.validar_digitacion_musical(0, 'sus4', pos_erronea_csus4)
        self.assertFalse(valido)
        self.assertIn("tercera", razon.lower())

        # Digitacion con error: G/B pero con 6ta cuerda al aire (0 en 6ta da bajo E, no B)
        pos_erronea_gb = self.DigitacionAcorde(trastes=[0, 2, 0, 0, 3, 3])
        valido, razon = self.validar_digitacion_musical(7, '', pos_erronea_gb, bajo_pitch=11)
        self.assertFalse(valido)
        self.assertIn("bajo", razon.lower())

    def test_acorde_no_disponible_mensaje_exacto(self):
        """
        Criterio 19:
        Acordes no incluidos no deben aproximarse ni simplificarse.
        Deben mostrar exactamente: 'Diagrama aún no disponible para este acorde.'
        """
        # Solicitamos un acorde inexistente en la biblioteca (ej: Cdim7)
        res = self.client.get(
            reverse('canciones:ver_diagrama'),
            {'root': '0', 'mod': 'dim7', 'format': 'json'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data['disponible'])
        self.assertEqual(data['mensaje'], "Diagrama aún no disponible para este acorde.")

        # Slash chord no incluido (ej: F/A)
        res_slash = self.client.get(
            reverse('canciones:ver_diagrama'),
            {'root': '5', 'mod': '', 'bass': '9', 'format': 'json'}
        )
        data_slash = res_slash.json()
        self.assertFalse(data_slash['disponible'])
        self.assertEqual(data_slash['mensaje'], "Diagrama aún no disponible para este acorde.")

    def test_capo_no_altera_diagrama(self):
        """
        Criterio 4:
        Si una canción tiene Capo 2 y un acorde 'G', el diagrama generado debe
        ser 'G' (root=7), no 'A' (root=9). El diagrama representa la forma que
        ejecuta la mano del guitarrista respecto del capo.
        """
        res = self.client.get(reverse('canciones:tocar', args=[self.cancion_capo.pk]))
        self.assertEqual(res.status_code, 200)
        # El enlace del acorde debe apuntar a root=7 (G)
        self.assertContains(res, 'root=7')
        self.assertNotContains(res, 'root=9&mod=')

    def test_afinacion_alternativa_muestra_advertencia(self):
        """
        Criterio 5:
        Si la afinación es distinta de estándar, el endpoint debe devolver
        advertencia_afinacion=True con el texto 'Diagrama basado en afinación estándar EADGBE.'
        """
        # Afinacion estandar -> sin advertencia
        res_std = self.client.get(
            reverse('canciones:ver_diagrama'),
            {'root': '7', 'mod': '', 'cancion_id': self.cancion_std.pk, 'format': 'json'}
        )
        data_std = res_std.json()
        self.assertFalse(data_std['advertencia_afinacion'])

        # Afinacion alternativa Drop D -> con advertencia discreta
        res_drop_d = self.client.get(
            reverse('canciones:ver_diagrama'),
            {'root': '2', 'mod': '', 'cancion_id': self.cancion_drop_d.pk, 'format': 'json'}
        )
        data_drop_d = res_drop_d.json()
        self.assertTrue(bool(data_drop_d['advertencia_afinacion']))
        self.assertIn("Diagrama basado en afinación estándar EADGBE.", data_drop_d['advertencia_afinacion'])

    def test_endpoint_diagrama_rechaza_root_fuera_de_rango(self):
        """
        Criterio 6:
        El servidor debe validar root entre 0 y 11. Rechaza valores fuera de rango con 400.
        """
        res_neg = self.client.get(reverse('canciones:ver_diagrama'), {'root': '-1', 'mod': ''})
        self.assertEqual(res_neg.status_code, 400)

        res_12 = self.client.get(reverse('canciones:ver_diagrama'), {'root': '12', 'mod': ''})
        self.assertEqual(res_12.status_code, 400)

        res_str = self.client.get(reverse('canciones:ver_diagrama'), {'root': 'C#', 'mod': ''})
        self.assertEqual(res_str.status_code, 400)

    def test_endpoint_diagrama_rechaza_modificador_invalido(self):
        """
        Criterio 6 y 7:
        El servidor debe validar el modificador contra el vocabulario conocido.
        Rechaza modificadores arbitrarios o scripts maliciosos con 400.
        """
        res_xss = self.client.get(
            reverse('canciones:ver_diagrama'),
            {'root': '0', 'mod': '<script>alert(1)</script>'}
        )
        self.assertEqual(res_xss.status_code, 400)

        res_inv = self.client.get(reverse('canciones:ver_diagrama'), {'root': '0', 'mod': 'inventado'})
        self.assertEqual(res_inv.status_code, 400)

    def test_svg_seguridad_xss_accesibilidad_y_primitivas(self):
        """
        Criterios 12 y 13:
        El SVG debe usar <circle> sin relleno para cuerda abierta,
        dos <line> cruzadas para cuerda anulada, role='img', y <title>.
        """
        res = self.client.get(
            reverse('canciones:ver_diagrama'),
            {'root': '7', 'mod': '', 'format': 'json'}
        )
        data = res.json()
        svg = data['svg']
        self.assertIn('role="img"', svg)
        self.assertIn('<title>', svg)
        self.assertIn('Diagrama de acorde G', svg)
        # G = 320003 -> Cuerdas abiertas (traste 0) usan circle
        self.assertIn('<circle', svg)
        self.assertIn('fill="none"', svg)

        # C = x32010 -> Cuerda 6 anulada (-1) usa lineas cruzadas (X)
        res_c = self.client.get(
            reverse('canciones:ver_diagrama'),
            {'root': '0', 'mod': '', 'format': 'json'}
        )
        svg_c = res_c.json()['svg']
        self.assertIn('<line', svg_c)

    def test_endpoint_diagrama_soporte_notacion_latina(self):
        """
        Criterio 11:
        Misma digitación física, solo cambia el nombre mostrado.
        """
        res_am = self.client.get(
            reverse('canciones:ver_diagrama'),
            {'root': '0', 'mod': '', 'notacion': 'american', 'format': 'json'}
        )
        self.assertEqual(res_am.json()['nombre'], 'C')

        res_lat = self.client.get(
            reverse('canciones:ver_diagrama'),
            {'root': '0', 'mod': '', 'notacion': 'latin', 'format': 'json'}
        )
        self.assertEqual(res_lat.json()['nombre'], 'Do')

    def test_retorno_no_js_con_ancla(self):
        """
        Criterios 15 y 16:
        En modo sin JavaScript, la vista HTML del diagrama genera un enlace
        de retorno seguro a la canción con su ancla exacta (#acorde-l...-c...).
        """
        res = self.client.get(
            reverse('canciones:ver_diagrama'),
            {
                'root': '7',
                'mod': '',
                'cancion_id': self.cancion_std.pk,
                'semitonos': '0',
                'notacion': 'american',
                'anchor': 'acorde-l1-c0'
            }
        )
        self.assertEqual(res.status_code, 200)
        # Debe contener enlace de retorno a /canciones/<id>/tocar/?...#acorde-l1-c0
        expected_url = f"/canciones/{self.cancion_std.pk}/tocar/?semitonos=0&amp;notacion=american#acorde-l1-c0"
        self.assertContains(res, expected_url)

    def test_retorno_no_js_dentro_de_fogata_setlist(self):
        """
        Criterio 17:
        Si se consulta desde Tocar Fogata, el enlace de retorno regresa
        a la misma posición del setlist, conservando contexto.
        """
        from apps.fogatas.models import Fogata, FogataCancion
        fogata = Fogata.objects.create(nombre="Fogata Nocturna", propietario=self.user)
        FogataCancion.objects.create(fogata=fogata, cancion=self.cancion_std, orden=1)

        res = self.client.get(
            reverse('canciones:ver_diagrama'),
            {
                'root': '7',
                'mod': '',
                'cancion_id': self.cancion_std.pk,
                'fogata_id': fogata.pk,
                'pos': '1',
                'semitonos': '1',
                'notacion': 'latin',
                'anchor': 'acorde-l1-c6'
            }
        )
        self.assertEqual(res.status_code, 200)
        expected_url = f"/fogatas/{fogata.pk}/tocar/?pos=1&amp;semitonos=1&amp;notacion=latin#acorde-l1-c6"
        self.assertContains(res, expected_url)

    def test_seguridad_retorno_sin_open_redirect(self):
        """
        Criterio 16:
        Parámetros maliciosos no pueden forzar una redirección abierta.
        """
        res = self.client.get(
            reverse('canciones:ver_diagrama'),
            {
                'root': '7',
                'mod': '',
                'cancion_id': 'malicioso',
                'anchor': 'http://evil.com'  # Caracteres no permitidos en anchor
            }
        )
        self.assertEqual(res.status_code, 200)
        # Debe caer al fallback seguro del repertorio general
        self.assertContains(res, reverse('canciones:lista'))
        self.assertNotContains(res, 'evil.com')

    def test_acorde_interactivo_no_rompe_alineacion_monospace(self):
        """
        Criterio 14:
        Comprueba que los acordes interactivos usen .acorde-link inline
        y que no agreguen espaciado o caracteres adicionales que rompan columnas.
        """
        contenido = "G    D    Em   C\nLetra debajo alineada"
        html = render_cancion_html(contenido, cancion_id=self.cancion_std.pk)
        self.assertIn('class="acorde-link"', html)
        self.assertIn('class="acorde"', html)
        self.assertIn('id="acorde-l0-c0"', html)

        with open('static/css/fogata.css', 'r', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('.acorde-link {', css)
        self.assertIn('display: inline;', css)
        self.assertIn('padding: 0;', css)
        self.assertIn('margin: 0;', css)

    def test_diagramas_javascript_es5_y_cache(self):
        """
        Criterios 8, 9 y 20:
        Comprueba que fogata.js tenga la implementación de diagramas:
        - initDiagramasAtril
        - diagramCache
        - XHR XMLHttpRequest (no fetch obligatorio)
        - Pausar auto-scroll al hacer click
        - No reanudar auto-scroll al cerrar
        - Cero sintaxis ES6
        """
        with open('static/js/fogata.js', 'r', encoding='utf-8') as f:
            js = f.read()

        self.assertIn('initDiagramasAtril', js)
        self.assertIn('diagramCache', js)
        self.assertIn('XMLHttpRequest', js)
        self.assertIn('pausarAutoScroll', js)
        self.assertIn('__FOGATA_DIAGRAM_CACHE__', js)

        # Verificar ES5 estricto
        self.assertNotIn('const ', js)
        self.assertNotIn('let ', js)
        self.assertNotIn('=>', js)


# =============================================================================
# Pruebas Automatizadas Fase 5: Precarga Batch de Diagramas Offline
# =============================================================================

class DiagramasBatchTest(TestCase):
    def test_diagramas_batch_endpoint_status_y_contenido(self):
        """
        Criterios 6 y 7 (Fase 5):
        El endpoint /canciones/diagramas/batch/ debe devolver la biblioteca completa
        de 64 digitaciones con nombres y SVGs para ambas notaciones (American y Latin).
        """
        import json
        response = self.client.get('/canciones/diagramas/batch/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/json', response['Content-Type'])

        data = json.loads(response.content.decode('utf-8'))
        self.assertTrue(data.get('ok'))
        self.assertEqual(data.get('total'), 64)
        diagramas = data.get('diagramas', {})
        self.assertEqual(len(diagramas), 64)

        # Probar acorde C (0, '', None)
        c_item = diagramas.get('0||')
        self.assertIsNotNone(c_item)
        self.assertEqual(c_item['root'], 0)
        self.assertEqual(c_item['mod'], '')
        self.assertIsNone(c_item['bass'])
        self.assertEqual(c_item['nombre_american'], 'C')
        self.assertEqual(c_item['nombre_latin'], 'Do')
        self.assertIn('<svg', c_item['svg_american'])
        self.assertIn('<svg', c_item['svg_latin'])

        # Probar acorde slash C/G (0, '', 7)
        cg_item = diagramas.get('0||7')
        self.assertIsNotNone(cg_item)
        self.assertEqual(cg_item['root'], 0)
        self.assertEqual(cg_item['bass'], 7)
        self.assertEqual(cg_item['nombre_american'], 'C/G')
        self.assertEqual(cg_item['nombre_latin'], 'Do/Sol')

    def test_fogata_js_incluye_precarga_batch_es5(self):
        """
        Criterio 6:
        Verifica que fogata.js invoque la precarga del batch de diagramas
        manteniendo compatibilidad ES5 estricta.
        """
        with open('static/js/fogata.js', 'r', encoding='utf-8') as f:
            js = f.read()

        self.assertIn('precargarBatchDiagramas', js)
        self.assertIn('/canciones/diagramas/batch/', js)
        # Verificar ES5 estricto
        self.assertNotIn('const ', js)
        self.assertNotIn('let ', js)
        self.assertNotIn('=>', js)




