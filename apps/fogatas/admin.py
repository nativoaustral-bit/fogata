from django.contrib import admin
from .models import Fogata, FogataCancion, SesionCompartida


class FogataCancionInline(admin.TabularInline):
    model = FogataCancion
    extra = 1
    ordering = ('orden',)


@admin.register(Fogata)
class FogataAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'propietario', 'total_canciones', 'created_at')
    list_filter = ('propietario',)
    search_fields = ('nombre', 'descripcion', 'propietario__email')
    inlines = [FogataCancionInline]

    def total_canciones(self, obj):
        return obj.canciones_asociadas.count()
    total_canciones.short_description = 'Canciones'


@admin.register(SesionCompartida)
class SesionCompartidaAdmin(admin.ModelAdmin):
    list_display = ('token', 'fogata', 'creado_el', 'expira_el', 'activa', 'esta_vigente')
    list_filter = ('activa',)
    search_fields = ('token', 'fogata__nombre')
