from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """
    Panel de administración para el modelo Usuario personalizado.
    Incluye campos extra en formularios de creación y edición.
    """
    list_display = [
        "username",
        "email",
        "nombre_completo",
        "telefono",
        "is_staff",
        "is_active",
        "date_joined"
    ]
    list_filter = ["is_staff", "is_active"]
    search_fields = ["username", "email", "telefono"]
    ordering = ["-date_joined"]

    # Formulario de EDICION de usuario existente
    fieldsets = (
        ("Credenciales", {
            "fields": ("username", "password")
        }),
        ("Información personal", {
            "fields": (
                "first_name",
                "last_name",
                "email",
                "telefono",
                "avatar"
            )
        }),
        ("Permisos", {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions"
            )
        }),
        ("Fechas importantes", {
            "fields": ("last_login", "date_joined")
        }),
    )

    # Formulario de CREACION de usuario nuevo
    add_fieldsets = (
        ("Credenciales", {
            "classes": ("wide",),
            "fields": (
                "username",
                "email",
                "password1",
                "password2",
            )
        }),
        ("Información extra", {
            "classes": ("wide",),
            "fields": (
                "telefono",
                "avatar"
            )
        }),
    )
