from django.test import TestCase
from django.urls import reverse
from .models import Cancion
from .services import obtener_solo_letra


class CancionModelTest(TestCase):
    def test_creacion_cancion_preserva_contenido_integro(self):
        """
        Verifica que el contenido con espacios, saltos de línea y acordes
        se preserve exactamente tal como fue ingresado (Criterios 2 y 6).
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

        # Comprobar que no hubo mutilación de espacios
        self.assertEqual(cancion.contenido, contenido_prueba)
        self.assertEqual(str(cancion), "Canto Nocturno Ficticio - Grupo Prueba")
        self.assertEqual(cancion.get_tocar_url(), reverse('canciones:tocar', args=[cancion.pk]))

    def test_servicio_obtener_solo_letra_no_destructivo(self):
        """
        Verifica que el helper futuro obtener_solo_letra sea tolerante
        y no destruya el contenido original (Criterio 6).
        """
        contenido = "  C    G    Am    F\nCanta la brisa en el amanecer..."
        resultado = obtener_solo_letra(contenido)
        self.assertIn("Canta la brisa", resultado)
        self.assertEqual(obtener_solo_letra(""), "")


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

        response_vacia = self.client.get(reverse('canciones:lista') + '?q=Inexistente')
        self.assertEqual(response_vacia.status_code, 200)
        self.assertNotContains(response_vacia, "Canción del Amanecer Ficticia")

    def test_detalle_cancion(self):
        response = self.client.get(reverse('canciones:detalle', args=[self.cancion.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Banda de Prueba")

    def test_crear_y_preservar_espacios_y_saltos(self):
        """
        Verifica crear canción con espacios iniciales, tabulaciones simuladas
        y saltos de línea, comprobando que se preserven íntegros.
        """
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

    def test_editar_cancion_preserva_contenido(self):
        """
        Verifica que al editar una canción, los espacios y saltos se conserven exactamente.
        """
        contenido_modificado = (
            "    Am          Dm\n"
            "Línea editada con espacios previos intactos\n"
            "         E7               Am\n"
            "Segunda línea con sangría larga\n"
        )
        data = {
            'titulo': 'Canción Editada Ficticia',
            'artista': 'Banda de Prueba',
            'tonalidad': 'Am',
            'capo': '2',
            'afinacion': 'Estándar',
            'contenido': contenido_modificado,
            'notas_personales': 'Actualizada'
        }
        response = self.client.post(reverse('canciones:editar', args=[self.cancion.pk]), data=data)
        self.assertEqual(response.status_code, 302)
        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.contenido, contenido_modificado)
        self.assertEqual(self.cancion.titulo, 'Canción Editada Ficticia')

    def test_eliminar_cancion(self):
        """
        Verifica el flujo GET de confirmación y POST de eliminación.
        """
        # GET confirmación
        response_get = self.client.get(reverse('canciones:eliminar', args=[self.cancion.pk]))
        self.assertEqual(response_get.status_code, 200)
        self.assertContains(response_get, "¿Eliminar canción?")

        # POST eliminación
        response_post = self.client.post(reverse('canciones:eliminar', args=[self.cancion.pk]))
        self.assertEqual(response_post.status_code, 302)
        self.assertFalse(Cancion.objects.filter(pk=self.cancion.pk).exists())

    def test_lineas_largas_se_almacenan_y_renderizan_sin_alteracion(self):
        """
        Verifica que una línea muy larga (más de 120 caracteres) se guarde y muestre
        exactamente, sin truncar ni romper artificialmente.
        """
        linea_larga = "F" + (" " * 40) + "G" + (" " * 40) + "Am\n"
        verso_largo = "Esta es una línea deliberadamente extensa con más de ciento cuarenta caracteres continuos para validar que el Modo Músico no fuerce saltos automáticos.\n"
        contenido = linea_larga + verso_largo

        self.cancion.contenido = contenido
        self.cancion.save()

        response = self.client.get(reverse('canciones:tocar', args=[self.cancion.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, verso_largo.strip())

    def test_modo_musico_tocar(self):
        """
        Verifica que la vista Tocar use Modo Músico y contenga
        los identificadores para preservación de espaciado y controles de atril.
        """
        response = self.client.get(reverse('canciones:tocar', args=[self.cancion.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="cuerpo-letra"')
        self.assertContains(response, 'letra-acordes-musico')
        self.assertContains(response, 'btn-zoom-menos')
        self.assertContains(response, 'btn-zoom-mas')
        self.assertContains(response, 'btn-wakelock')
