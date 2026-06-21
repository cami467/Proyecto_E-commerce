from django.contrib import admin
from django.utils.html import mark_safe
from .models import Notificacion


# ==============================================================================
# ACCIONES EN LOTE
# ==============================================================================

@admin.action(description="Marcar como leídas")
def marcar_leidas(modeladmin, request, queryset):
    cantidad = 0
    for notificacion in queryset.filter(leida=False):
        notificacion.marcar_leida()
        cantidad += 1
    modeladmin.message_user(request, f"{cantidad} notificación(es) marcada(s) como leída(s).")


# ==============================================================================
# ADMIN DE NOTIFICACIÓN
# ==============================================================================

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    """
    Panel de administración para Notificaciones.
    Solo lectura para el contenido — las notificaciones se generan
    automáticamente desde las tareas de Celery.
    """
    list_display = [
        "col_usuario",
        "col_tipo",
        "titulo",
        "col_leida",
        "fecha_creacion",
    ]
    list_filter = ["tipo", "leida", "fecha_creacion"]
    search_fields = ["^usuario__username", "titulo", "mensaje"]
    ordering = ["-fecha_creacion"]
    readonly_fields = [
        "usuario",
        "tipo",
        "titulo",
        "mensaje",
        "referencia_id",
        "fecha_creacion",
        "fecha_leida",
    ]
    list_select_related = ["usuario"]
    list_per_page = 25
    date_hierarchy = "fecha_creacion"
    actions = [marcar_leidas]

    def has_add_permission(self, request):
        return False

    def col_usuario(self, obj):
        return obj.usuario.username
    col_usuario.short_description = "Usuario"
    col_usuario.admin_order_field = "usuario__username"

    def col_tipo(self, obj):
        return obj.get_tipo_display()
    col_tipo.short_description = "Tipo"
    col_tipo.admin_order_field = "tipo"

    def col_leida(self, obj):
        if obj.leida:
            return mark_safe(
                '<span style="color:#155724;font-weight:bold;">✓ Leída</span>'
            )
        return mark_safe(
            '<span style="color:#856404;font-weight:bold;">● No leída</span>'
        )
    col_leida.short_description = "Estado"
    col_leida.admin_order_field = "leida"