from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Categoria, Producto, Variante, ImagenProducto


# ==============================================================================
# MIXINS REUTILIZABLES
# ==============================================================================

class PreviewImagenMixin:
    """
    Mixin reutilizable para vistas previas de imagenes.
    Protege contra archivos inexistentes o corruptos.
    Usa clases CSS en lugar de estilos inline.
    """
    class Media:
        css = {
            "all": ("admin/css/admin_productos.css",)
        }

    def preview_imagen(self, obj):
        if obj.imagen and hasattr(obj.imagen, "url"):
            try:
                return format_html(
                    '<img src="{0}" class="preview-imagen" />',
                    obj.imagen.url,
                )
            except ValueError:
                pass
        return mark_safe(
            '<span class="preview-sin-imagen">Sin imagen</span>'
        )
    preview_imagen.short_description = "Vista previa"


# ==============================================================================
# ACCIONES EN LOTE
# ==============================================================================

@admin.action(description="Activar elementos seleccionados")
def realizar_activacion(modeladmin, request, queryset):
    # Activa en bloque los registros seleccionados (esta_activo=True)
    queryset.update(esta_activo=True)


@admin.action(description="Desactivar elementos seleccionados")
def realizar_desactivacion(modeladmin, request, queryset):
    # Desactiva en bloque los registros seleccionados (esta_activo=False)
    queryset.update(esta_activo=False)


@admin.action(description="Marcar como destacados")
def marcar_destacados(modeladmin, request, queryset):
    # Marca como destacados los registros seleccionados (es_destacado=True)
    queryset.update(es_destacado=True)


@admin.action(description="Quitar de destacados")
def quitar_destacados(modeladmin, request, queryset):
    # Quita la marca de destacados de los registros seleccionados (es_destacado=False)
    queryset.update(es_destacado=False)



# ==============================================================================
# INLINES
# ==============================================================================

class VarianteInline(admin.TabularInline):
    """
    Muestra las variantes dentro del formulario del producto.
    Permite agregar y editar variantes sin salir del producto.
    """
    model = Variante
    extra = 1
    fields = [
        "nombre",
        "sku",
        "modificador_precio",
        "inventario",
        "stock_minimo",
        "esta_activo",
    ]
    show_change_link = True


class ImagenProductoInline(PreviewImagenMixin, admin.TabularInline):
    """
    Muestra las imagenes dentro del formulario del producto.
    """
    model = ImagenProducto
    extra = 1
    fields = ["imagen", "preview_imagen", "es_principal", "orden", "esta_activo"]
    readonly_fields = ["preview_imagen"]
    show_change_link = True


# ==============================================================================
# ADMINS
# ==============================================================================

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    """
    Panel de administracion para Categorias.
    Soporta jerarquia padre/hijo con validacion de ciclos.
    """
    class Media:
        css = {"all": ("admin/css/admin_productos.css",)}

    list_display = [
        "nombre",
        "categoria_padre",
        "cantidad_productos",
        "esta_activo",
    ]
    list_filter = ["esta_activo", "categoria_padre"]
    search_fields = ["^nombre", "descripcion"]
    prepopulated_fields = {"slug": ("nombre",)}
    ordering = ["nombre"]
    list_select_related = ["categoria_padre"]
    list_per_page = 25
    actions = [realizar_activacion, realizar_desactivacion]

    def get_queryset(self, request):
        """Inyecta conteo agrupado en SQL para evitar consultas N+1."""
        qs = super().get_queryset(request)
        return qs.annotate(
            _prod_activos_count=Count(
                "productos", filter=Q(productos__esta_activo=True)
            )
        )

    def cantidad_productos(self, obj):
        return f"{obj._prod_activos_count} productos"
    cantidad_productos.short_description = "Productos activos"
    cantidad_productos.admin_order_field = "_prod_activos_count"


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    """
    Panel de administracion para Productos.
    Incluye variantes e imagenes.
    """
    class Media:
        css = {"all": ("admin/css/admin_productos.css",)}

    list_display = [
        "nombre",
        "categoria",
        "precio_base",
        "precio_final",
        "porcentaje_descuento",
        "tasa_iva",
        "es_destacado",
        "cantidad_variantes",
        "esta_activo",
    ]
    list_filter = ["esta_activo", "es_destacado", "categoria"]
    search_fields = ["=slug", "^nombre"]
    prepopulated_fields = {"slug": ("nombre",)}
    ordering = ["-fecha_creacion"]
    inlines = [VarianteInline, ImagenProductoInline]
    readonly_fields = ["precio_final", "fecha_creacion", "fecha_actualizacion"]
    list_select_related = ["categoria"]
    autocomplete_fields = ["categoria"]
    list_per_page = 20
    date_hierarchy = "fecha_creacion"
    actions = [
        realizar_activacion,
        realizar_desactivacion,
        marcar_destacados,
        quitar_destacados,
    ]

    fieldsets = (
        ("Informacion principal", {
            "fields": ("nombre", "slug", "categoria", "descripcion")
        }),
        ("Precios e impuestos", {
            "fields": ("precio_base", "porcentaje_descuento", "tasa_iva", "precio_final")
        }),
        ("Opciones", {
            "fields": ("es_destacado", "esta_activo")
        }),
        ("Fechas", {
            "fields": ("fecha_creacion", "fecha_actualizacion"),
            "classes": ("collapse",)
        }),
    )

    def get_queryset(self, request):
        """Anotacion SQL para optimizar el contador de variantes."""
        qs = super().get_queryset(request)
        return qs.annotate(
            _var_activas_count=Count(
                "variantes", filter=Q(variantes__esta_activo=True)
            )
        )

    def precio_final(self, obj):
        """
        Muestra el precio final calculado.
        Protegido contra objetos sin guardar o sin precio_base todavia
        (por ejemplo, el formulario vacio de "agregar producto" que Django
        arma en memoria para renderizar los campos de solo lectura antes
        de que el usuario haya cargado ningun dato).
        """
        if obj.pk is None or obj.precio_base is None:
            return mark_safe(
                '<span class="preview-sin-imagen">—</span>'
            )
        precio_formateado = "{:,.0f}".format(int(obj.precio_con_descuento))
        return format_html(
            '<span style="font-weight:bold;color:#155724;">Gs. {0}</span>',
            precio_formateado,
        )
    precio_final.short_description = "Precio final"

    def cantidad_variantes(self, obj):
        return f"{obj._var_activas_count} variantes"
    cantidad_variantes.short_description = "Variantes activas"
    cantidad_variantes.admin_order_field = "_var_activas_count"


@admin.register(Variante)
class VarianteAdmin(admin.ModelAdmin):
    """
    Panel de administracion para Variantes.
    Muestra alertas visuales de stock con CSS.
    """
    class Media:
        css = {"all": ("admin/css/admin_productos.css",)}

    list_display = [
        "producto",
        "nombre",
        "sku",
        "precio_total",
        "estado_stock",
        "inventario",
        "stock_minimo",
        "esta_activo",
    ]
    list_filter = ["esta_activo", "producto__categoria"]
    search_fields = ["=sku", "^nombre", "^producto__nombre"]
    ordering = ["producto__nombre", "nombre"]
    readonly_fields = ["precio_total", "tiene_stock", "requiere_reposicion"]
    list_select_related = ["producto"]
    autocomplete_fields = ["producto"]
    list_per_page = 25
    actions = [realizar_activacion, realizar_desactivacion]

    fieldsets = (
        ("Informacion principal", {
            "fields": ("producto", "nombre", "sku", "atributos")
        }),
        ("Precio y Stock", {
            "fields": (
                "modificador_precio",
                "precio_total",
                "inventario",
                "stock_minimo",
                "tiene_stock",
                "requiere_reposicion",
            )
        }),
        ("Estado", {
            "fields": ("esta_activo",)
        }),
    )

    def estado_stock(self, obj):
        """
        Muestra el estado del stock con badges CSS.
        """
        if obj.inventario <= 0:
            return mark_safe(
                '<span class="badge-stock-vacio">🔴 Sin stock (0)</span>'
            )
        elif obj.requiere_reposicion:
            return format_html(
                '<span class="badge-stock-bajo">🟠 Stock bajo ({0})</span>',
                obj.inventario,
            )
        return format_html(
            '<span class="badge-stock-ok">🟢 OK ({0})</span>',
            obj.inventario,
        )
    estado_stock.short_description = "Estado stock"
    estado_stock.admin_order_field = "inventario"


@admin.register(ImagenProducto)
class ImagenProductoAdmin(PreviewImagenMixin, admin.ModelAdmin):
    """
    Panel de administracion para Imagenes de Productos.
    """
    list_display = [
        "producto",
        "preview_imagen",
        "es_principal",
        "orden",
        "esta_activo",
    ]
    list_filter = ["es_principal", "esta_activo"]
    search_fields = ["^producto__nombre"]
    ordering = ["producto__nombre", "orden"]
    list_select_related = ["producto"]
    autocomplete_fields = ["producto"]
    list_per_page = 20
    actions = [realizar_activacion, realizar_desactivacion]