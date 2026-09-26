from django.test import TestCase
from django.urls import reverse
from .models import Cancion
from .services import obtener_solo_letra
from .parser import (
    parse_cancion,
    render_cancion_html,
    extraer_solo_letra,
    extraer_acordes_unicos,
    validar_token_acorde,
    LineaMusical,
    AcordeToken
)


class CancionModelTest(TestCase):
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
        self.cancion = Cancion.objects.create(
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
        self.assertContains(response, '<span class="acorde">F</span>')
        self.assertContains(response, '<span class="acorde">Bb</span>')

    def test_tocar_cancion_renderiza_acordes_en_atril(self):
        response = self.client.get(reverse('canciones:tocar', args=[self.cancion.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<span class="acorde">F</span>')
        self.assertContains(response, '<span class="acorde">Bb</span>')
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
            titulo="Canción No-JS",
            artista="Autor No-JS",
            contenido="   A      E\nCaminando sin prisa..."
        )
        res_tocar = self.client.get(reverse('canciones:tocar', args=[cancion.pk]))
        self.assertEqual(res_tocar.status_code, 200)
        # Acordes ya vienen con clase .acorde desde el servidor
        self.assertContains(res_tocar, '<span class="acorde">A</span>')
        self.assertContains(res_tocar, '<span class="acorde">E</span>')

    def test_14_visualizacion_movil_clases_y_estilos(self):
        """14. Modo tocar incluye contenedor de atril monoespaciado y con scroll horizontal seguro."""
        cancion = Cancion.objects.create(
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
        self.cancion = Cancion.objects.create(
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
        self.assertContains(res, '<span class="acorde">G</span>')
        self.assertContains(res, '<span class="acorde">Em</span>')


