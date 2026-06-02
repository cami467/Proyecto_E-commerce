from django.contrib import admin
from django.db.models import Count, Q
from .models import Carrito, ItemCarrito


# ==============================================================================
# ACCIONES EN LOTE
# ==============================================================================

@admin.action(description="Vaciar carritos seleccionados")
def vaciar_carritos(modeladmin, request, queryset):
    """Vacia todos los items de los carritos seleccionados."""
    cantidad = queryset.count()
    for carrito in queryset:
        carrito.vaciar()
    modeladmin.message_user(
        request,
        f"Se vaciaron {cantidad} carritos exitosamente."
    )


# ==============================================================================
# MIXIN REUTILIZABLE
# ==============================================================================

class SubtotalDisplayMixin:
    """
    Mixin para mostrar el subtotal calculado en el admin.
    Cualquier panel que lo use gana la columna de subtotal
    sin permitir que nadie lo edite manualmente.
    """
    readonly_fields = ("subtotal_display",)

    def subtotal_display(self, obj):
        """Retorna el subtotal calculado del item en Guaranies."""
        return f"Gs. {obj.subtotal:,.0f}"
    subtotal_display.short_description = "Subtotal (Gs.)"


# ==============================================================================
# INLINE
# ==============================================================================

class ItemCarritoInline(SubtotalDisplayMixin, admin.TabularInline):
    """
    Muestra los items directamente dentro del formulario del carrito.
    Como los renglones de una factura.
    """
    model = ItemCarrito
    extra = 0
    fields = (
        "variante",
        "cantidad",
        "subtotal_display",
        "esta_activo",
    )
    show_change_link = True
    autocomplete_fields = ("variante",)


# ==============================================================================
# ADMIN DE CARRITO
# ==============================================================================

@admin.register(Carrito)
class CarritoAdmin(admin.ModelAdmin):
    """
    Panel principal del Carrito de Compras.
    Muestra quien esta comprando y cuanto lleva acumulado.
    """
    list_display = (
        "usuario",
        "cantidad_items_display",
        "total_display",
        "esta_activo",
        "fecha_actualizacion",
    )
    list_filter = ("esta_activo",)
    search_fields = ("usuario__username", "usuario__email")
    readonly_fields = (
        "usuario",
        "cantidad_items_display",
        "total_display",
        "fecha_creacion",
        "fecha_actualizacion"
    )
    inlines = (ItemCarritoInline,)
    list_select_related = ("usuario",)
    list_per_page = 25
    actions = [vaciar_carritos]

    fields = (
        "usuario",
        "cantidad_items_display",
        "total_display",
        "esta_activo",
    )

    def get_queryset(self, request):
        """Optimiza con anotaciones SQL para evitar N+1."""
        return super().get_queryset(request).select_related(
            "usuario"
        ).annotate(
            _cantidad_items=Count(
                "items",
                filter=Q(items__esta_activo=True)
            )
        )

    def total_display(self, obj):
        """Muestra el total del carrito en Guaranies."""
        return f"Gs. {obj.total:,.0f}"
    total_display.short_description = "Total (Gs.)"

    def cantidad_items_display(self, obj):
        """Muestra la cantidad total de unidades en el carrito."""
        cantidad = getattr(obj, "_cantidad_items", obj.cantidad_items)
        return f"{cantidad} items"
    cantidad_items_display.short_description = "Unidades"
    cantidad_items_display.admin_order_field = "_cantidad_items"


# ==============================================================================
# ADMIN DE ITEM CARRITO
# ==============================================================================

@admin.register(ItemCarrito)
class ItemCarritoAdmin(SubtotalDisplayMixin, admin.ModelAdmin):
    """
    Panel de Items de Carrito.
    Permite ver todos los productos individuales de cada carrito.
    """
    list_display = (
        "carrito",
        "variante",
        "cantidad",
        "subtotal_display",
        "esta_activo",
        "fecha_actualizacion",
    )
    list_filter = ("esta_activo",)
    list_select_related = ("carrito__usuario", "variante__producto")
    search_fields = (
        "carrito__usuario__username",
        "variante__nombre",
        "variante__sku",
    )
    ordering = ["-fecha_creacion"]
    list_per_page = 25