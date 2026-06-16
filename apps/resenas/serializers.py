from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, OpenApiTypes

from .models import Resena


# ==============================================================================
# SERIALIZER DE LECTURA — LISTADO
# ==============================================================================

class ResenaListSerializer(serializers.ModelSerializer):
    """
    Serializer resumido para listado de reseñas.

    Optimizado para GET /api/resenas/ donde se listan muchas reseñas.
    Incluye datos del usuario y el producto sin cargar relaciones pesadas.
    """
    usuario_username = serializers.CharField(
        source="usuario.username",
        read_only=True
    )
    producto_nombre = serializers.CharField(
        source="producto.nombre",
        read_only=True
    )
    estrellas = serializers.CharField(read_only=True)

    class Meta:
        model = Resena
        fields = [
            "id",
            "usuario",
            "usuario_username",
            "producto",
            "producto_nombre",
            "calificacion",
            "estrellas",
            "titulo",
            "es_verificada",
            "esta_activo",
            "fecha_creacion",
        ]
        read_only_fields = fields


# ==============================================================================
# SERIALIZER DE LECTURA — DETALLE
# ==============================================================================

class ResenaSerializer(serializers.ModelSerializer):
    """
    Serializer completo para el detalle de una reseña.
    Incluye el comentario completo y todos los campos.
    """
    usuario_username = serializers.CharField(
        source="usuario.username",
        read_only=True
    )
    producto_nombre = serializers.CharField(
        source="producto.nombre",
        read_only=True
    )
    estrellas = serializers.CharField(read_only=True)

    class Meta:
        model = Resena
        fields = [
            "id",
            "usuario",
            "usuario_username",
            "producto",
            "producto_nombre",
            "calificacion",
            "estrellas",
            "titulo",
            "comentario",
            "es_verificada",
            "esta_activo",
            "fecha_creacion",
            "fecha_actualizacion",
        ]
        read_only_fields = [
            "id",
            "usuario",
            "usuario_username",
            "producto_nombre",
            "estrellas",
            "es_verificada",
            "fecha_creacion",
            "fecha_actualizacion",
        ]


# ==============================================================================
# SERIALIZER DE ESCRITURA
# ==============================================================================

class CrearResenaSerializer(serializers.ModelSerializer):
    """
    Serializer para crear o actualizar una reseña.

    El usuario se toma automáticamente del request.
    El producto se envía como UUID.

    Validaciones:
        - calificacion: debe ser entre 1 y 5.
        - Un usuario no puede reseñar el mismo producto dos veces.
          La restricción UniqueConstraint del modelo lo garantiza
          a nivel de base de datos.
        - El producto debe existir y estar activo.
    """
    class Meta:
        model = Resena
        fields = [
            "producto",
            "calificacion",
            "titulo",
            "comentario",
        ]

    def validate_calificacion(self, value: int) -> int:
        """La calificación debe ser entre 1 y 5."""
        if not 1 <= value <= 5:
            raise serializers.ValidationError(
                "La calificación debe ser entre 1 y 5 estrellas."
            )
        return value

    def validate_titulo(self, value: str) -> str:
        """Limpia espacios del título."""
        return value.strip() if value else ""

    def validate_comentario(self, value: str) -> str:
        """Limpia espacios del comentario."""
        return value.strip() if value else ""

    def validate(self, data: dict) -> dict:
        """
        Verifica que el usuario no haya reseñado ya este producto.
        Funciona tanto en creación como en actualización.
        """
        usuario = self.context["request"].user
        producto = data.get("producto")

        if producto:
            queryset = Resena.objects.filter(
                usuario=usuario,
                producto=producto
            )
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise serializers.ValidationError({
                    "producto": (
                        "Ya dejaste una reseña para este producto. "
                        "Podés editarla desde tu perfil."
                    )
                })

        return data

    def create(self, validated_data: dict) -> Resena:
        """
        Crea la reseña asignando el usuario autenticado automáticamente.
        La verificación de compra se calcula en el modelo al guardar.
        """
        validated_data["usuario"] = self.context["request"].user
        return super().create(validated_data)