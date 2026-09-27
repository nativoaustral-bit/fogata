from django.contrib import admin
from .models import Cancion


@admin.register(Cancion)
class CancionAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'artista', 'propietario', 'tonalidad', 'capo', 'created_at')
    search_fields = ('titulo', 'artista', 'contenido', 'propietario__email')
    list_filter = ('propietario', 'tonalidad', 'capo')
