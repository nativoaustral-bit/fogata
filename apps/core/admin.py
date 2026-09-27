from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from .models import Invitacion, PerfilPiloto


@admin.register(Invitacion)
class InvitacionAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descripcion', 'usos_actuales', 'max_usos', 'activa', 'expira_el', 'esta_vigente', 'creada_el')
    list_filter = ('activa',)
    search_fields = ('codigo', 'descripcion')
    readonly_fields = ('creada_el', 'usos_actuales')

    def esta_vigente(self, obj):
        return obj.esta_vigente()
    esta_vigente.boolean = True
    esta_vigente.short_description = 'Vigente'


@admin.register(PerfilPiloto)
class PerfilPilotoAdmin(admin.ModelAdmin):
    list_display = ('user', 'codigo_invitacion', 'registrado_el')
    search_fields = ('user__email', 'user__username', 'codigo_invitacion')
    readonly_fields = ('registrado_el',)


class PerfilPilotoInline(admin.StackedInline):
    model = PerfilPiloto
    can_delete = False
    verbose_name_plural = 'Perfil de Piloto'
    readonly_fields = ('codigo_invitacion', 'registrado_el')


# Re-registrar UserAdmin para incorporar métricas del piloto
admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(DefaultUserAdmin):
    list_display = (
        'email',
        'first_name',
        'is_active',
        'date_joined',
        'last_login',
        'numero_canciones',
        'numero_fogatas',
        'codigo_invitacion_usado',
    )
    list_filter = ('is_active', 'is_staff', 'date_joined')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    inlines = [PerfilPilotoInline]

    def numero_canciones(self, obj):
        return obj.canciones.count()
    numero_canciones.short_description = 'Canciones'

    def numero_fogatas(self, obj):
        return obj.fogatas.count()
    numero_fogatas.short_description = 'Fogatas'

    def codigo_invitacion_usado(self, obj):
        if hasattr(obj, 'perfil_piloto'):
            return obj.perfil_piloto.codigo_invitacion or '—'
        return '—'
    codigo_invitacion_usado.short_description = 'Código Invitación'
