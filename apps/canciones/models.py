from django.conf import settings
from django.db import models
from django.urls import reverse


class Cancion(models.Model):
    """
    Representa una canción en el repertorio del usuario.
    Almacena el contenido íntegro y sin alteraciones ingresado por el usuario
    (letra con acordes espaciados), garantizando fidelidad espacial absoluta.
    """
    propietario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='canciones',
        verbose_name='Propietario',
        db_index=True
    )
    titulo = models.CharField(
        max_length=200,
        verbose_name='Título',
        help_text='Nombre de la canción'
    )
    artista = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Artista / Banda',
        help_text='Nombre del intérprete o compositor'
    )
    contenido = models.TextField(
        verbose_name='Contenido (Letra + Acordes)',
        help_text='Texto íntegro tal como fue copiado/escrito. Se preservan espacios y saltos de línea.'
    )
    tonalidad = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='Tono',
        help_text='Tono base (ej: G, Am, C#m)'
    )
    capo = models.PositiveSmallIntegerField(
        default=0,
        blank=True,
        verbose_name='Capo / Cejillo',
        help_text='Traste del cejillo (0 = sin capo)'
    )
    afinacion = models.CharField(
        max_length=50,
        default='Estándar (E A D G B E)',
        blank=True,
        verbose_name='Afinación'
    )
    notas_personales = models.TextField(
        blank=True,
        verbose_name='Notas de interpretación',
        help_text='Rasgueo, ritmo, intro, anotaciones personales'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado el')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizado el')

    class Meta:
        verbose_name = 'Canción'
        verbose_name_plural = 'Canciones'
        ordering = ['titulo', 'artista']

    def __str__(self):
        if self.artista:
            return f"{self.titulo} - {self.artista}"
        return self.titulo

    def get_absolute_url(self):
        return reverse('canciones:detalle', args=[self.pk])

    def get_tocar_url(self):
        return reverse('canciones:tocar', args=[self.pk])
