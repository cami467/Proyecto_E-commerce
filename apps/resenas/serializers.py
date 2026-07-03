from rest_framework import serializers

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
            "producto",
            "producto_nombre",
            "estrellas",
            "es_verificada",
            "esta_activo",
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
    El producto se envía como UUID solamente al crear.
    """

    class Meta:
        model = Resena
        fields = [
            "producto",
            "calificacion",
            "titulo",
            "comentario",
        ]

    def get_fields(self):
        """Evita cambiar el producto de una reseña ya creada."""
        fields = super().get_fields()
        if self.instance is not None:
            fields["producto"].read_only = True
        return fields

    def validate_calificacion(self, value: int) -> int:
        """La calificación debe ser entre 1 y 5."""
        if not 1 <= value <= 5:
            raise serializers.ValidationError(
                "La calificación debe ser entre 1 y 5 estrellas."
            )
        return value

    def validate_titulo(self, value: str) -> str:
        """Limpia espacios y valida una longitud mínima real del título."""
        titulo = value.strip() if value else ""
        if titulo and len(titulo) < 3:
            raise serializers.ValidationError(
                "El título debe tener al menos 3 caracteres."
            )
        return titulo

    def validate_comentario(self, value: str) -> str:
        """Limpia espacios y limita comentarios demasiado extensos."""
        comentario = value.strip() if value else ""
        if comentario and len(comentario) < 5:
            raise serializers.ValidationError(
                "El comentario debe tener al menos 5 caracteres."
            )
        if len(comentario) > 1000:
            raise serializers.ValidationError(
                "El comentario no puede superar los 1000 caracteres."
            )
        return comentario

    def validate(self, data: dict) -> dict:
        """
        Verifica reglas de negocio de creación/edición.
        """
        usuario = self.context["request"].user
        producto = data.get("producto")

        if self.instance is not None:
            data.pop("producto", None)
            return data

        if producto is None:
            raise serializers.ValidationError({
                "producto": "Debe indicar el producto que desea reseñar."
            })

        if not producto.esta_activo:
            raise serializers.ValidationError({
                "producto": "No se puede reseñar un producto inactivo."
            })

        if Resena.objects.filter(usuario=usuario, producto=producto).exists():
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
