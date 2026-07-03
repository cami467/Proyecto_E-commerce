from decimal import Decimal
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, OpenApiTypes

from .models import Cupon


# ==============================================================================
# SERIALIZER DE LECTURA — LISTADO
# ==============================================================================

class CuponListSerializer(serializers.ModelSerializer):
    """
    Serializer resumido para listado de cupones.
    Solo expone los campos necesarios para que el frontend
    muestre la lista sin cargar datos innecesarios.
    """
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    esta_vigente = serializers.BooleanField(read_only=True)
    usos_restantes = serializers.SerializerMethodField()

    class Meta:
        model = Cupon
        fields = [
            "id",
            "codigo",
            "tipo",
            "tipo_display",
            "valor",
            "monto_minimo",
            "esta_vigente",
            "usos_restantes",
            "fecha_vencimiento",
            "esta_activo",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.INT)
    def get_usos_restantes(self, obj: Cupon):
        """Retorna los usos restantes o None si no tiene límite."""
        return obj.usos_restantes

    def to_representation(self, instance: Cupon) -> dict:
        """Convierte montos a enteros en Guaraníes."""
        data = super().to_representation(instance)
        data["monto_minimo"] = int(instance.monto_minimo)
        if instance.tipo == Cupon.TipoDescuento.MONTO_FIJO:
            data["valor"] = int(instance.valor)
        return data


# ==============================================================================
# SERIALIZER DE LECTURA — DETALLE
# ==============================================================================

class CuponSerializer(serializers.ModelSerializer):
    """
    Serializer completo para el detalle de un cupón.
    Incluye todos los campos incluyendo usuarios permitidos.
    """
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    esta_vigente = serializers.BooleanField(read_only=True)
    tiene_usos_disponibles = serializers.BooleanField(read_only=True)
    usos_restantes = serializers.SerializerMethodField()

    class Meta:
        model = Cupon
        fields = [
            "id",
            "codigo",
            "descripcion",
            "tipo",
            "tipo_display",
            "valor",
            "monto_minimo",
            "limite_usos",
            "usos_actuales",
            "usos_restantes",
            "esta_vigente",
            "tiene_usos_disponibles",
            "fecha_inicio",
            "fecha_vencimiento",
            "usuarios_permitidos",
            "esta_activo",
            "fecha_creacion",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.INT)
    def get_usos_restantes(self, obj: Cupon):
        return obj.usos_restantes

    def to_representation(self, instance: Cupon) -> dict:
        """Convierte montos a enteros en Guaraníes."""
        data = super().to_representation(instance)
        data["monto_minimo"] = int(instance.monto_minimo)
        if instance.tipo == Cupon.TipoDescuento.MONTO_FIJO:
            data["valor"] = int(instance.valor)
        return data


# ==============================================================================
# SERIALIZER DE VALIDACIÓN DE CUPÓN
# ==============================================================================

class ValidarCuponSerializer(serializers.Serializer):
    """
    Serializer para validar un cupón antes de aplicarlo a una orden.
    """
    codigo = serializers.CharField(
        max_length=50,
        trim_whitespace=True,
        help_text="Código del cupón a validar."
    )
    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=0,
        min_value=Decimal("1"),
        help_text="Subtotal de la orden en Guaraníes."
    )

    def validate_codigo(self, value: str) -> str:
        """Normaliza y valida el código recibido desde el frontend."""
        codigo = Cupon.normalizar_codigo(value)
        if not Cupon.CODIGO_REGEX.match(codigo):
            raise serializers.ValidationError(
                "El código del cupón tiene un formato inválido."
            )
        return codigo


class CuponAplicadoSerializer(serializers.Serializer):
    """
    Serializer de respuesta al validar un cupón exitosamente.
    """
    codigo = serializers.CharField()
    tipo = serializers.CharField()
    tipo_display = serializers.CharField()
    valor = serializers.DecimalField(max_digits=12, decimal_places=2)

    # decimal_places=0 porque el dinero se maneja como enteros de Guaraníes
    subtotal_original = serializers.DecimalField(max_digits=12, decimal_places=0, coerce_to_string=False)
    monto_descuento = serializers.DecimalField(max_digits=12, decimal_places=0, coerce_to_string=False)
    total_con_descuento = serializers.DecimalField(max_digits=12, decimal_places=0, coerce_to_string=False)
    mensaje = serializers.CharField()

    def to_representation(self, instance: dict) -> dict:
        """
        Si el cupón es de monto fijo, muestra 'valor' como entero
        sin decimales porque representa Guaraníes.
        """
        data = super().to_representation(instance)
        if instance.get("tipo") == Cupon.TipoDescuento.MONTO_FIJO:
            data["valor"] = int(instance.get("valor", 0))
        return data
