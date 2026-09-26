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
