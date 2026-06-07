from decimal import Decimal
from django.contrib import admin
from django.utils.html import format_html, mark_safe
from django.db import transaction
from django.db.models import Count
from .models import Orden, ItemOrden, HistorialEstadoOrden


# ==============================================================================
# HELPER MONETARIO
# ==============================================================================

def gs(valor) -> str:
    """
    Formatea un valor monetario como string en Guaraníes.
    Convierte primero a float puro para evitar que USE_L10N
    interfiera con el formateo dentro de format_html.
    Ejemplo: 135000 → 'Gs. 135.000'
    """
    try:
        numero = float(Decimal(str(valor or 0)))
        return f"Gs. {numero:,.0f}".replace(",", ".")
    except Exception:
        return "Gs. 0"


def gs_bold(valor) -> str:
    """
    Igual que gs() pero envuelto en negrita para columnas importantes.
    Retorna HTML seguro usando mark_safe sobre un string ya formateado.
    """
    return mark_safe(f'<span style="font-weight:bold;">{gs(valor)}</span>')


def gs_verde(valor) -> str:
    """
    Igual que gs() pero en color verde para totales de orden.
    """
    return mark_safe(
        f'<span style="font-weight:bold;color:#155724;">{gs(valor)}</span>'
    )


# ==============================================================================
# ACCIONES EN LOTE
# ==============================================================================

@admin.action(description="Cancelar órdenes seleccionadas")
def cancelar_ordenes(modeladmin, request, queryset):
    """
    Cancela cada orden en su propia transacción atómica.
    Si una falla no afecta a las demás.
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
    Ítems de la orden dentro del formulario de detalle.
    Solo lectura — los precios están congelados históricamente.
    """
    model = ItemOrden
    extra = 0
    fields = [
        "nombre_producto",
        "nombre_variante",
        "cantidad",
        "col_precio",
        "col_subtotal",
    ]
    readonly_fields = [
        "nombre_producto",
        "nombre_variante",
        "cantidad",
        "col_precio",
        "col_subtotal",
    ]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def col_precio(self, obj):
        return gs(obj.precio_unitario)
    col_precio.short_description = "Precio unitario"

    def col_subtotal(self, obj):
        return gs_bold(obj.subtotal)
    col_subtotal.short_description = "Subtotal"


class HistorialEstadoInline(admin.TabularInline):
    """
    Historial de cambios de estado — solo lectura para auditoría.
    """
    model = HistorialEstadoOrden
    extra = 0
    fields = [
        "estado_anterior",
        "estado_nuevo",
        "cambiado_por",
        "fecha",
        "comentario",
    ]
    readonly_fields = [
        "estado_anterior",
        "estado_nuevo",
        "cambiado_por",
        "fecha",
        "comentario",
    ]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ==============================================================================
# ADMIN DE ORDEN
# ==============================================================================

@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    """
    Panel principal de Órdenes.
    Incluye ítems e historial de estados como inlines de solo lectura.
    """
    list_display = [
        "col_numero",
        "usuario",
        "col_estado",
        "col_total",
        "col_items",
        "fecha_creacion",
    ]
    list_filter = ["estado", "fecha_creacion"]
    search_fields = [
        "^usuario__username",
        "^usuario__email",
        "codigo_cupon",
    ]
    ordering = ["-fecha_creacion"]
    readonly_fields = [
        "col_numero",
        "usuario",
        "col_subtotal",
        "col_descuento",
        "col_envio",
        "col_total",
        "fecha_creacion",
        "fecha_actualizacion",
    ]
    list_select_related = ["usuario"]
    list_per_page = 25
    date_hierarchy = "fecha_creacion"
    inlines = [ItemOrdenInline, HistorialEstadoInline]
    actions = [cancelar_ordenes]

    fieldsets = (
        ("Información de la orden", {
            "fields": (
                "col_numero",
                "usuario",
                "estado",
                "notas",
            )
        }),
        ("Montos en Guaraníes", {
            "fields": (
                "col_subtotal",
                "col_descuento",
                "col_envio",
                "col_total",
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
        return super().get_queryset(request).annotate(
            _cantidad_items=Count("items")
        ).select_related("usuario")

    def col_numero(self, obj):
        return f"#{str(obj.id)[:8].upper()}"
    col_numero.short_description = "N° Orden"

    def col_estado(self, obj):
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
        etiqueta = obj.get_estado_display()
        return mark_safe(
            f'<span style="background:{bg};color:{color};padding:3px 8px;'
            f'border-radius:4px;font-weight:bold;">{etiqueta}</span>'
        )
    col_estado.short_description = "Estado"
    col_estado.admin_order_field = "estado"

    def col_total(self, obj):
        return gs_verde(obj.total)
    col_total.short_description = "Total"
    col_total.admin_order_field = "total"

    def col_subtotal(self, obj):
        return gs(obj.subtotal)
    col_subtotal.short_description = "Subtotal"

    def col_descuento(self, obj):
        return gs(obj.monto_descuento)
    col_descuento.short_description = "Descuento"

    def col_envio(self, obj):
        return gs(obj.costo_envio)
    col_envio.short_description = "Envío"

    def col_items(self, obj):
        return f"{getattr(obj, '_cantidad_items', 0)} ítems"
    col_items.short_description = "Ítems"
    col_items.admin_order_field = "_cantidad_items"


# ==============================================================================
# ADMIN DE ITEM DE ORDEN
# ==============================================================================

@admin.register(ItemOrden)
class ItemOrdenAdmin(admin.ModelAdmin):
    """
    Solo lectura — los precios están congelados históricamente.
    """
    list_display = [
        "col_orden",
        "nombre_producto",
        "nombre_variante",
        "cantidad",
        "col_precio",
        "col_subtotal",
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
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def col_orden(self, obj):
        return f"#{str(obj.orden.id)[:8].upper()}"
    col_orden.short_description = "N° Orden"

    def col_precio(self, obj):
        return gs(obj.precio_unitario)
    col_precio.short_description = "Precio unitario"

    def col_subtotal(self, obj):
        return gs_bold(obj.subtotal)
    col_subtotal.short_description = "Subtotal"


# ==============================================================================
# ADMIN DE HISTORIAL DE ESTADO
# ==============================================================================

@admin.register(HistorialEstadoOrden)
class HistorialEstadoOrdenAdmin(admin.ModelAdmin):
    """
    Solo lectura — logs de auditoría inmutables.
    """
    list_display = [
        "col_orden",
        "estado_anterior",
        "estado_nuevo",
        "cambiado_por",
        "fecha",
        "comentario",
    ]
    list_filter = ["estado_nuevo", "fecha"]
    search_fields = [
        "^orden__usuario__username",
        "comentario",
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
        "comentario",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def col_orden(self, obj):
        return f"#{str(obj.orden.id)[:8].upper()}"
    col_orden.short_description = "N° Orden"