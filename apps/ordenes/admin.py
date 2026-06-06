from django.contrib import admin
from django.utils.html import format_html
from django.db import transaction
from django.db.models import Count
from .models import Orden, ItemOrden, HistorialEstadoOrden


# ==============================================================================
# ACCIONES EN LOTE
# ==============================================================================

@admin.action(description="Cancelar órdenes seleccionadas")
def cancelar_ordenes(modeladmin, request, queryset):
    """
    Cancela las órdenes seleccionadas asegurando atomicidad por instancia.
    
    """
    canceladas = 0
    errores = 0

    for orden in queryset:
        try:
            with transaction.atomic():
                orden.cancelar(usuario_accion=request.user)
                canceladas += 1
        except Exception:
            errores += 1

    if canceladas:
        modeladmin.message_user(
            request,
            f"{canceladas} orden(es) cancelada(s) exitosamente."
        )
    if errores:
        modeladmin.message_user(
            request,
            f"{errores} orden(es) no pudieron cancelarse por su estado actual.",
            level="warning"
        )


# ==============================================================================
# INLINES
# ==============================================================================

class ItemOrdenInline(admin.TabularInline):
    """
    Muestra los items dentro del formulario de la orden.
    Solo lectura porque los precios estan congelados historicamente.
    """
    model = ItemOrden
    extra = 0
    fields = [
        "nombre_producto",
        "nombre_variante",
        "cantidad",
        "precio_unitario",
        "subtotal_display",
    ]
    readonly_fields = [
        "nombre_producto",
        "nombre_variante",
        "cantidad",
        "precio_unitario",
        "subtotal_display",
    ]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def subtotal_display(self, obj):
        return format_html(
            '<span style="font-weight:bold;">Gs. {:,.0f}</span>',
            obj.subtotal
        )
    subtotal_display.short_description = "Subtotal (Gs.)"


class HistorialEstadoInline(admin.TabularInline):
    """
    Muestra el historial de cambios de estado (Auditoria).
    Solo lectura para preservar la integridad del historico.
    """
    model = HistorialEstadoOrden
    extra = 0
    fields = [
        "estado_anterior",
        "estado_nuevo",
        "cambiado_por",
        "fecha",
        "comentario"
    ]
    readonly_fields = [
        "estado_anterior",
        "estado_nuevo",
        "cambiado_por",
        "fecha",
        "comentario"
    ]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ==============================================================================
# ADMINS
# ==============================================================================

@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    """
    Panel de administracion optimizado para Ordenes.
    """
    list_display = [
        "numero_orden",
        "usuario",
        "estado_badge",
        "total_display",
        "cantidad_items_display",
        "fecha_creacion",
    ]
    list_filter = ["estado", "fecha_creacion"]
    search_fields = [
        "^usuario__username",
        "^usuario__email",
        "codigo_cupon"
    ]
    ordering = ["-fecha_creacion"]
    readonly_fields = [
        "numero_orden",
        "usuario",
        "subtotal_display",
        "monto_descuento_display",
        "costo_envio_display",
        "total_display",
        "fecha_creacion",
        "fecha_actualizacion",
    ]
    list_select_related = ["usuario"]
    list_per_page = 25
    date_hierarchy = "fecha_creacion"
    inlines = [ItemOrdenInline, HistorialEstadoInline]
    actions = [cancelar_ordenes]

    fieldsets = (
        ("Informacion de la orden", {
            "fields": (
                "numero_orden",
                "usuario",
                "estado",
                "notas",
            )
        }),
        ("Montos en Guaranies", {
            "fields": (
                "subtotal_display",
                "monto_descuento_display",
                "costo_envio_display",
                "total_display",
                "codigo_cupon",
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

    def get_queryset(self, request):
        """Optimizacion O(1) con annotate para evitar N+1 al contar items."""
        return super().get_queryset(request).annotate(
            _cantidad_items=Count("items")
        ).select_related("usuario")

    def numero_orden(self, obj):
        return f"#{str(obj.id)[:8].upper()}"
    numero_orden.short_description = "N° Orden"

    def estado_badge(self, obj):
        """Muestra el estado con colores semanicos."""
        colores = {
            "pending":    ("#fff3cd", "#856404"),
            "confirmed":  ("#d4edda", "#155724"),
            "processing": ("#cce5ff", "#004085"),
            "shipped":    ("#d1ecf1", "#0c5460"),
            "delivered":  ("#d4edda", "#155724"),
            "cancelled":  ("#f8d7da", "#721c24"),
            "refunded":   ("#e2e3e5", "#383d41"),
        }
        bg, color = colores.get(obj.estado, ("#fff", "#000"))
        return format_html(
            '<span style="background:{};color:{};padding:3px 8px;'
            'border-radius:4px;font-weight:bold;">{}</span>',
            bg, color, obj.get_estado_display()
        )
    estado_badge.short_description = "Estado"
    estado_badge.admin_order_field = "estado"

    def total_display(self, obj):
        return format_html(
            '<span style="font-weight:bold;color:#155724;">Gs. {:,.0f}</span>',
            obj.total
        )
    total_display.short_description = "Total (Gs.)"
    total_display.admin_order_field = "total"

    def subtotal_display(self, obj):
        return f"Gs. {obj.subtotal:,.0f}"
    subtotal_display.short_description = "Subtotal (Gs.)"

    def monto_descuento_display(self, obj):
        return f"Gs. {obj.monto_descuento:,.0f}"
    monto_descuento_display.short_description = "Descuento (Gs.)"

    def costo_envio_display(self, obj):
        return f"Gs. {obj.costo_envio:,.0f}"
    costo_envio_display.short_description = "Envio (Gs.)"

    def cantidad_items_display(self, obj):
        cantidad = getattr(obj, "_cantidad_items", 0)
        return f"{cantidad} items"
    cantidad_items_display.short_description = "Items"
    cantidad_items_display.admin_order_field = "_cantidad_items"


@admin.register(ItemOrden)
class ItemOrdenAdmin(admin.ModelAdmin):
    """
    Panel de administracion para Items de Orden.
    Completamente de solo lectura.
    """
    list_display = [
        "orden_numero",
        "nombre_producto",
        "nombre_variante",
        "cantidad",
        "precio_unitario_display",
        "subtotal_display",
    ]
    list_filter = ["orden__estado"]
    search_fields = [
        "^nombre_producto",
        "^nombre_variante",
        "^orden__usuario__username",
    ]
    ordering = ["-fecha_creacion"]
    list_select_related = ["orden", "orden__usuario"]
    list_per_page = 25
    readonly_fields = [
        "orden",
        "variante",
        "nombre_producto",
        "nombre_variante",
        "cantidad",
        "precio_unitario",
        "subtotal_display",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def orden_numero(self, obj):
        return f"#{str(obj.orden.id)[:8].upper()}"
    orden_numero.short_description = "N° Orden"

    def precio_unitario_display(self, obj):
        return f"Gs. {obj.precio_unitario:,.0f}"
    precio_unitario_display.short_description = "Precio unitario (Gs.)"

    def subtotal_display(self, obj):
        return format_html(
            '<span style="font-weight:bold;">Gs. {:,.0f}</span>',
            obj.subtotal
        )
    subtotal_display.short_description = "Subtotal (Gs.)"


@admin.register(HistorialEstadoOrden)
class HistorialEstadoOrdenAdmin(admin.ModelAdmin):
    """
    Panel de administracion para el Historial de Estados.
    Solo lectura - logs de auditoria.
    """
    list_display = [
        "orden_numero",
        "estado_anterior",
        "estado_nuevo",
        "cambiado_por",
        "fecha",
        "comentario"
    ]
    list_filter = ["estado_nuevo", "fecha"]
    search_fields = [
        "^orden__usuario__username",
        "comentario"
    ]
    ordering = ["-fecha"]
    list_select_related = ["orden", "orden__usuario", "cambiado_por"]
    list_per_page = 25
    readonly_fields = [
        "orden",
        "estado_anterior",
        "estado_nuevo",
        "cambiado_por",
        "fecha",
        "comentario"
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def orden_numero(self, obj):
        return f"#{str(obj.orden.id)[:8].upper()}"
    orden_numero.short_description = "N° Orden"