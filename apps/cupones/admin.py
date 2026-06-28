from decimal import Decimal
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.utils.html import mark_safe
from .models import Cupon


# ==============================================================================
# ACCIONES EN LOTE
# ==============================================================================

@admin.action(description="Activar cupones seleccionados")
def activar_cupones(modeladmin, request, queryset):
    cantidad = queryset.update(esta_activo=True)
    modeladmin.message_user(request, f"{cantidad} cupón(es) activado(s).")


@admin.action(description="Desactivar cupones seleccionados")
def desactivar_cupones(modeladmin, request, queryset):
    cantidad = queryset.update(esta_activo=False)
    modeladmin.message_user(request, f"{cantidad} cupón(es) desactivado(s).")


# ==============================================================================
# HELPER MONETARIO
# ==============================================================================

def _gs(valor) -> str:
    """Formatea un valor como Guaraníes con separadores de miles."""
    try:
        return f"Gs. {int(Decimal(str(valor or 0))):,}".replace(",", ".")
    except Exception:
        return "Gs. 0"


# ==============================================================================
# ADMIN DE CUPÓN
# ==============================================================================

@admin.register(Cupon)
class CuponAdmin(admin.ModelAdmin):
    """
    Panel de administración para Cupones.

    Permite crear, editar y desactivar cupones de descuento.
    Muestra el estado de vigencia en tiempo real.
    """
    list_display = [
        "codigo",
        "col_tipo_descuento",
        "col_estado_vigencia",
        "col_usos",
        "monto_minimo_display",
        "fecha_vencimiento",
        "esta_activo",
    ]
    list_filter = ["tipo", "esta_activo", "fecha_inicio", "fecha_vencimiento"]
    search_fields = ["^codigo", "descripcion"]
    ordering = ["-fecha_creacion"]
    list_per_page = 25
    date_hierarchy = "fecha_creacion"
    filter_horizontal = ["usuarios_permitidos"]
    readonly_fields = [
        "usos_actuales",
        "col_usos_restantes",
        "fecha_creacion",
        "fecha_actualizacion",
    ]
    actions = [activar_cupones, desactivar_cupones]

    fieldsets = (
        ("Información del cupón", {
            "fields": (
                "codigo",
                "descripcion",
                "esta_activo",
            )
        }),
        ("Configuración del descuento", {
            "fields": (
                "tipo",
                "valor",
                "monto_minimo",
            )
        }),
        ("Control de usos", {
            "fields": (
                "limite_usos",
                "usos_actuales",
                "col_usos_restantes",
            )
        }),
        ("Vigencia", {
            "fields": (
                "fecha_inicio",
                "fecha_vencimiento",
            )
        }),
        ("Usuarios permitidos", {
            "fields": ("usuarios_permitidos",),
            "description": "Dejá vacío para que cualquier usuario pueda usarlo.",
        }),
        ("Fechas del sistema", {
            "fields": (
                "fecha_creacion",
                "fecha_actualizacion",
            ),
            "classes": ("collapse",)
        }),
    )

    # ------------------------------------------------------------------
    # COLUMNAS PERSONALIZADAS
    # ------------------------------------------------------------------

    def col_tipo_descuento(self, obj):
        """Muestra el tipo y valor del descuento en una sola columna."""
        if obj.tipo == Cupon.TipoDescuento.PORCENTAJE:
            return mark_safe(
                f'<span style="color:#004085;font-weight:bold;">'
                f'{int(obj.valor)}%</span>'
            )
        valor_formateado = f"{int(obj.valor):,}".replace(",", ".")
        return mark_safe(
            f'<span style="color:#155724;font-weight:bold;">'
            f'Gs. {valor_formateado}</span>'
        )
    col_tipo_descuento.short_description = "Descuento"
    col_tipo_descuento.admin_order_field = "valor"

    def col_estado_vigencia(self, obj):
        """Muestra el estado de vigencia en tiempo real con badge de color."""
        ahora = timezone.now()

        if not obj.esta_activo:
            return mark_safe(
                '<span style="background:#e2e3e5;color:#383d41;'
                'padding:3px 8px;border-radius:4px;font-weight:bold;">'
                'Inactivo</span>'
            )
        if ahora < obj.fecha_inicio:
            return mark_safe(
                '<span style="background:#cce5ff;color:#004085;'
                'padding:3px 8px;border-radius:4px;font-weight:bold;">'
                'Próximo</span>'
            )
        if obj.fecha_vencimiento and ahora > obj.fecha_vencimiento:
            return mark_safe(
                '<span style="background:#f8d7da;color:#721c24;'
                'padding:3px 8px;border-radius:4px;font-weight:bold;">'
                'Vencido</span>'
            )
        if not obj.tiene_usos_disponibles:
            return mark_safe(
                '<span style="background:#fff3cd;color:#856404;'
                'padding:3px 8px;border-radius:4px;font-weight:bold;">'
                'Sin usos</span>'
            )
        return mark_safe(
            '<span style="background:#d4edda;color:#155724;'
            'padding:3px 8px;border-radius:4px;font-weight:bold;">'
            'Vigente</span>'
        )
    col_estado_vigencia.short_description = "Vigencia"

    def col_usos(self, obj):
        """Muestra usos actuales vs límite."""
        if obj.limite_usos is None:
            return f"{obj.usos_actuales} / ∞"
        porcentaje = (obj.usos_actuales / obj.limite_usos) * 100
        color = "#721c24" if porcentaje >= 90 else (
            "#856404" if porcentaje >= 70 else "#155724"
        )
        return mark_safe(
            f'<span style="color:{color};font-weight:bold;">'
            f'{obj.usos_actuales} / {obj.limite_usos}</span>'
        )
    col_usos.short_description = "Usos"
    col_usos.admin_order_field = "usos_actuales"

    def monto_minimo_display(self, obj):
        """Muestra el monto mínimo formateado."""
        if obj.monto_minimo == 0:
            return "Sin mínimo"
        return _gs(obj.monto_minimo)
    monto_minimo_display.short_description = "Monto mínimo"
    monto_minimo_display.admin_order_field = "monto_minimo"

    def col_usos_restantes(self, obj):
        """Muestra los usos restantes del cupón."""
        if obj._state.adding:
            return mark_safe(
                '<span style="color:#6c757d;">'
                'Se calculará al guardar</span>'
            )
        restantes = obj.usos_restantes
        if restantes is None:
            return "Sin límite"
        if restantes == 0:
            return mark_safe(
                '<span style="color:#721c24;font-weight:bold;">Agotado</span>'
            )
        return str(restantes)
    col_usos_restantes.short_description = "Usos restantes"