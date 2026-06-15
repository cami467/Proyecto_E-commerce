from django.contrib import admin
from django.utils.html import mark_safe
from django.db.models import Avg, Count
from .models import Resena


# ==============================================================================
# ACCIONES EN LOTE
# ==============================================================================

@admin.action(description="Activar reseñas seleccionadas")
def activar_resenas(modeladmin, request, queryset):
    cantidad = queryset.update(esta_activo=True)
    modeladmin.message_user(request, f"{cantidad} reseña(s) activada(s).")


@admin.action(description="Desactivar reseñas seleccionadas")
def desactivar_resenas(modeladmin, request, queryset):
    cantidad = queryset.update(esta_activo=False)
    modeladmin.message_user(request, f"{cantidad} reseña(s) desactivada(s).")


# ==============================================================================
# ADMIN DE RESEÑA
# ==============================================================================

@admin.register(Resena)
class ResenaAdmin(admin.ModelAdmin):
    """
    Panel de administración para Reseñas.

    Permite moderar reseñas activándolas o desactivándolas.
    Las reseñas desactivadas no aparecen en la API.
    Muestra si la reseña es de un comprador verificado.
    """
    list_display = [
        "col_usuario",
        "col_producto",
        "col_calificacion",
        "titulo",
        "col_verificada",
        "esta_activo",
        "fecha_creacion",
    ]
    list_filter = [
        "calificacion",
        "es_verificada",
        "esta_activo",
        "fecha_creacion",
    ]
    search_fields = [
        "^usuario__username",
        "^usuario__email",
        "^producto__nombre",
        "titulo",
        "comentario",
    ]
    ordering = ["-fecha_creacion"]
    readonly_fields = [
        "usuario",
        "producto",
        "calificacion",
        "es_verificada",
        "col_estrellas",
        "fecha_creacion",
        "fecha_actualizacion",
    ]
    list_select_related = ["usuario", "producto"]
    list_per_page = 25
    date_hierarchy = "fecha_creacion"
    actions = [activar_resenas, desactivar_resenas]

    fieldsets = (
        ("Información de la reseña", {
            "fields": (
                "usuario",
                "producto",
                "col_estrellas",
                "titulo",
                "comentario",
            )
        }),
        ("Estado", {
            "fields": (
                "es_verificada",
                "esta_activo",
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
        return super().get_queryset(request).select_related(
            "usuario", "producto"
        )

    def col_usuario(self, obj):
        return obj.usuario.username
    col_usuario.short_description = "Usuario"
    col_usuario.admin_order_field = "usuario__username"

    def col_producto(self, obj):
        return obj.producto.nombre
    col_producto.short_description = "Producto"
    col_producto.admin_order_field = "producto__nombre"

    def col_calificacion(self, obj):
        """Muestra la calificación como estrellas con color."""
        colores = {
            1: "#721c24",
            2: "#856404",
            3: "#856404",
            4: "#155724",
            5: "#155724",
        }
        color = colores.get(obj.calificacion, "#000")
        estrellas = "⭐" * obj.calificacion
        return mark_safe(
            f'<span style="color:{color};font-weight:bold;">'
            f'{estrellas} ({obj.calificacion}/5)</span>'
        )
    col_calificacion.short_description = "Calificación"
    col_calificacion.admin_order_field = "calificacion"

    def col_verificada(self, obj):
        """Muestra si la reseña es de un comprador verificado."""
        if obj.es_verificada:
            return mark_safe(
                '<span style="background:#d4edda;color:#155724;'
                'padding:3px 8px;border-radius:4px;font-weight:bold;">'
                '✓ Verificada</span>'
            )
        return mark_safe(
            '<span style="background:#e2e3e5;color:#383d41;'
            'padding:3px 8px;border-radius:4px;">'
            'No verificada</span>'
        )
    col_verificada.short_description = "Compra verificada"
    col_verificada.admin_order_field = "es_verificada"

    def col_estrellas(self, obj):
        """Muestra las estrellas completas e incompletas."""
        return obj.estrellas
    col_estrellas.short_description = "Calificación visual"