from rest_framework import serializers
from rest_framework import serializers as drf_serializers
from rest_framework.validators import UniqueValidator
from drf_spectacular.utils import extend_schema_field
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError

Usuario = get_user_model()


# ==============================================================================
# SERIALIZER DE REGISTRO
# ==============================================================================

class RegistroSerializer(serializers.ModelSerializer):
    """
    Serializer para registro de nuevos usuarios.
    Valida email unico, contraseña segura y coincidencia de passwords.
    """
    email = serializers.EmailField(
        required=True,
        validators=[
            UniqueValidator(
                queryset=Usuario.objects.all(),
                lookup="iexact",
                message="Ya existe una cuenta con este email."
            )
        ]
    )
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"}
    )
    password2 = serializers.CharField(
        write_only=True,
        style={"input_type": "password"}
    )

    class Meta:
        model = Usuario
        fields = ["username", "email", "password", "password2", "telefono"]

    def validate_email(self, value):
        """Normaliza el email a minusculas."""
        return value.lower()

    def validate_password(self, value):
        """Aplica validadores de contraseña oficiales de Django."""
        try:
            password_validation.validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, data):
        """Verifica coincidencia de contraseñas de manera segura."""
        password = data.get("password")
        password2 = data.get("password2")
        if password and password2 and password != password2:
            raise serializers.ValidationError({
                "password2": "Las contraseñas no coinciden."
            })
        return data

    def create(self, validated_data):
        """Crea el usuario con contraseña hasheada de forma escalable."""
        validated_data.pop("password2", None)
        return Usuario.objects.create_user(**validated_data)


# ==============================================================================
# SERIALIZER DE PERFIL
# ==============================================================================

class UsuarioSerializer(serializers.ModelSerializer):
    """
    Serializer para ver y editar el perfil del usuario autenticado.
    Incluye validacion de email unico excluyendo al usuario actual.
    """
    nombre_completo = serializers.SerializerMethodField()
    email = serializers.EmailField(required=True)

    class Meta:
        model = Usuario
        fields = [
            "id",
            "username",
            "email",
            "nombre_completo",
            "telefono",
            "avatar",
            "date_joined",
        ]
        read_only_fields = ["id", "date_joined"]

    @extend_schema_field(drf_serializers.CharField(allow_null=True))
    def get_nombre_completo(self, obj):
        """
        Genera nombre completo dinamicamente.
        Usa username como fallback si no hay nombre.
        """
        nombre = f"{obj.first_name} {obj.last_name}".strip()
        return nombre if nombre else obj.username

    def validate_email(self, value):
        """
        Normaliza email y verifica unicidad excluyendo al usuario actual.
        Funciona tanto en creacion como en edicion.
        """
        value = value.lower()
        queryset = Usuario.objects.filter(email__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                "Ya existe una cuenta con este email."
            )
        return value