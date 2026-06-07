from django.contrib import admin
from django.db.models import F
from django.utils.html import format_html
from .models import Pago


# ==============================================================================
# ACCIONES EN LOTE
# ==============================================================================

@admin.action(description="Cancelar pagos pendientes seleccionados")
def cancelar_pagos(modeladmin, request, queryset):
    """
    Cancela los pagos que esten en estado pendiente.
    Ignora los que ya fueron procesados y notifica al administrador.
    """
    cancelados = 0
    ignorados = 0

    for pago in queryset:
        if pago.esta_pendiente:
            pago.cancelar()
            cancelados += 1
        else:
            ignorados += 1

    if cancelados:
        modeladmin.message_user(
            request,
            f"{cancelados} pago(s) cancelado(s) exitosamente."
        )
    if ignorados:
        modeladmin.message_user(
            request,
            f"{ignorados} pago(s) ignorado(s) por no estar pendientes.",
            level="warning"
        )


# ==============================================================================
# ADMIN DE PAGO
# ==============================================================================

@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    """
    Panel de administracion para Pagos.

    Completamente de solo lectura para preservar la integridad
    financiera y contable de los registros.

    Los pagos se crean exclusivamente desde la API.
    Ningun pago puede crearse, editarse ni eliminarse desde el admin.
    """
    list_display = [
        "id_corto",
        "orden_numero",
        "pasarela_badge",
        "estado_badge",
        "monto_display",
        "fecha_procesado",
        "fecha_creacion",
    ]
    list_filter = ["estado", "pasarela", "fecha_creacion"]
    search_fields = [
        "^orden__usuario__username",
        "^id_transaccion",
    ]
    ordering = ["-fecha_creacion"]
    readonly_fields = [
        "id_corto",
        "orden",
        "pasarela",
        "estado",
        "monto_display",
        "id_transaccion",
        "respuesta_pasarela",
        "fecha_procesado",
        "fecha_creacion",
        "fecha_actualizacion",
    ]
    list_select_related = ["orden__usuario"]
    list_per_page = 25
    date_hierarchy = "fecha_creacion"
    actions = [cancelar_pagos]

    fieldsets = (
        ("Informacion del pago", {
            "fields": (
                "id_corto",
                "orden",
                "pasarela",
                "estado",
                "monto_display",
            )
        }),
        ("Datos de la pasarela", {
            "fields": (
                "id_transaccion",
                "respuesta_pasarela",
                "fecha_procesado",
            )
        }),
        ("Fechas", {
            "fields": (
                "fecha_creacion",
                "fecha_actualizacion",
            ),
            "classes": ("collapse",)
        }),
    )

    # ------------------------------------------------------------------
    # PERMISOS - Todo deshabilitado por integridad financiera
    # ------------------------------------------------------------------

    def has_add_permission(self, request):
        """Los pagos se crean desde la API, no desde el admin."""
        return False

    def has_change_permission(self, request, obj=None):
        """Los pagos no se editan para preservar integridad contable."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Los pagos nunca se eliminan por integridad financiera."""
        return False

    # ------------------------------------------------------------------
    # QUERYSET OPTIMIZADO
    # ------------------------------------------------------------------

    def get_queryset(self, request):
        """
        Optimiza las consultas con select_related.
        Evita N+1 al acceder a datos de la orden y el usuario.
        """
        return super().get_queryset(request).select_related(
            "orden__usuario"
        )

    # ------------------------------------------------------------------
    # COLUMNAS PERSONALIZADAS
    # ------------------------------------------------------------------

    def id_corto(self, obj):
        """Muestra los primeros 8 caracteres del UUID."""
        return f"#{str(obj.id)[:8].upper()}"
    id_corto.short_description = "ID"

    def orden_numero(self, obj):
        """Muestra el numero de orden asociado."""
        return f"#{str(obj.orden.id)[:8].upper()}"
    orden_numero.short_description = "N° Orden"
    orden_numero.admin_order_field = "orden__id"

    def pasarela_badge(self, obj):
        """Muestra la pasarela con badge de color."""
        colores = {
            "stripe":        ("#635bff", "#ffffff"),
            "mercado_pago":  ("#009ee3", "#ffffff"),
            "efectivo":      ("#28a745", "#ffffff"),
            "transferencia": ("#6c757d", "#ffffff"),
        }
        bg, color = colores.get(obj.pasarela, ("#6c757d", "#ffffff"))
        return format_html(
            '<span style="background:{};color:{};padding:3px 8px;'
            'border-radius:4px;font-weight:bold;">{}</span>',
            bg, color, obj.get_pasarela_display()
        )
    pasarela_badge.short_description = "Pasarela"
    pasarela_badge.admin_order_field = "pasarela"

    def estado_badge(self, obj):
        """Muestra el estado con badge de color semantico."""
        colores = {
            "pending":   ("#fff3cd", "#856404"),
            "approved":  ("#d4edda", "#155724"),
            "rejected":  ("#f8d7da", "#721c24"),
            "refunded":  ("#cce5ff", "#004085"),
            "cancelled": ("#e2e3e5", "#383d41"),
        }
        bg, color = colores.get(obj.estado, ("#fff", "#000"))
        return format_html(
            '<span style="background:{};color:{};padding:3px 8px;'
            'border-radius:4px;font-weight:bold;">{}</span>',
            bg, color, obj.get_estado_display()
        )
    estado_badge.short_description = "Estado"
    estado_badge.admin_order_field = "estado"

    def monto_display(self, obj):
        """Muestra el monto en Guaranies formateado."""
        return format_html(
            '<span style="font-weight:bold;color:#155724;">'
            'Gs. {:,.0f}</span>',
            obj.monto
        )
    monto_display.short_description = "Monto (Gs.)"
    monto_display.admin_order_field = "monto"