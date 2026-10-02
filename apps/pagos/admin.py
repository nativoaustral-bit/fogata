from django.contrib import admin
from .models import OrdenPago


@admin.register(OrdenPago)
class OrdenPagoAdmin(admin.ModelAdmin):
    list_display = ('commerce_order', 'usuario', 'plan', 'monto', 'moneda', 'ambiente', 'estado', 'pro_aplicado', 'creada_el')
    list_filter = ('estado', 'ambiente', 'plan', 'pro_aplicado', 'creada_el')
    search_fields = ('commerce_order', 'flow_order', 'flow_token', 'usuario__email')
    readonly_fields = ('commerce_order', 'flow_order', 'flow_token', 'checkout_request_id', 'creada_el', 'actualizada_el', 'pagada_el')
    ordering = ('-creada_el',)
