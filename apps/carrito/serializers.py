from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import Carrito, ItemCarrito
from apps.productos.models import Variante
from apps.productos.serializers import VarianteListSerializer


# ==============================================================================
# SERIALIZER DE ITEM CARRITO
# ==============================================================================

class ItemCarritoSerializer(serializers.ModelSerializer):
    """
    Serializer completo de ItemCarrito.
    Incluye datos de la variante y el subtotal calculado.
    """
    variante_detalle = VarianteListSerializer(
        source="variante",
        read_only=True
    )
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = ItemCarrito
        fields = [
            "id",
            "variante",
            "variante_detalle",
            "cantidad",
            "subtotal",
            "esta_activo",
        ]
        read_only_fields = [
            "id",
            "variante",
            "variante_detalle",
            "subtotal",
            "esta_activo",
        ]

    @extend_schema_field(serializers.IntegerField())
    def get_subtotal(self, obj):
        """Retorna el subtotal del item en Guaranies."""
        return int(obj.subtotal)

    def validate_cantidad(self, value):
        """La cantidad debe ser mayor a cero."""
        if value <= 0:
            raise serializers.ValidationError(
                "La cantidad debe ser mayor a cero."
            )
        return value


class AgregarItemSerializer(serializers.Serializer):
    """
    Serializer para agregar un item al carrito.
    Valida la existencia de la variante, que este activa
    y que haya stock suficiente considerando la cantidad ya cargada.
    """
    variante_id = serializers.PrimaryKeyRelatedField(
        source="variante",
        queryset=Variante.objects.filter(esta_activo=True),
        error_messages={
            "does_not_exist": "La variante no existe o no esta disponible.",
            "incorrect_type": "El identificador de la variante no es valido.",
        },
    )
    cantidad = serializers.IntegerField(min_value=1, default=1)

    def validate(self, data):
        """Validacion cruzada de variante y stock disponible."""
        variante = data["variante"]
        cantidad = data["cantidad"]
        request = self.context.get("request")
        cantidad_actual = 0

        if request and request.user and request.user.is_authenticated:
            item_existente = ItemCarrito.objects.filter(
                carrito__usuario=request.user,
                variante=variante,
            ).only("cantidad").first()
            if item_existente:
                cantidad_actual = item_existente.cantidad

        cantidad_total = cantidad_actual + cantidad
        if variante.inventario < cantidad_total:
            raise serializers.ValidationError({
                "cantidad": (
                    f"No hay suficiente stock. "
                    f"Disponible: {variante.inventario} unidades."
                )
            })

        return data


class ActualizarCantidadSerializer(serializers.Serializer):
    """
    Serializer para actualizar la cantidad de un item.
    Si la cantidad es 0 el item se elimina automaticamente.
    """
    cantidad = serializers.IntegerField(min_value=0)

    def validate_cantidad(self, value):
        """Evita cantidades exageradas por error o abuso."""
        if value > 999:
            raise serializers.ValidationError(
                "La cantidad maxima permitida por item es 999."
            )
        return value


# ==============================================================================
# SERIALIZER DE CARRITO
# ==============================================================================

class CarritoSerializer(serializers.ModelSerializer):
    """
    Serializer completo del Carrito.
    Incluye solo los items activos con sus detalles y el total general.
    """
    items = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    cantidad_items = serializers.SerializerMethodField()

    class Meta:
        model = Carrito
        fields = [
            "id",
            "usuario",
            "items",
            "cantidad_items",
            "total",
            "esta_activo",
        ]
        read_only_fields = [
            "id",
            "usuario",
            "items",
            "total",
            "cantidad_items",
            "esta_activo",
        ]

    @extend_schema_field(ItemCarritoSerializer(many=True))
    def get_items(self, obj):
        """
        Retorna unicamente los items activos del carrito.
        Usa select_related para evitar N+1 queries.
        """
        items_activos = obj.items.filter(
            esta_activo=True,
            variante__esta_activo=True,
        ).select_related("variante__producto")
        return ItemCarritoSerializer(
            items_activos,
            many=True,
            context=self.context
        ).data

    @extend_schema_field(serializers.IntegerField())
    def get_total(self, obj):
        """Retorna el total del carrito en Guaranies."""
        return int(obj.total)

    @extend_schema_field(serializers.IntegerField())
    def get_cantidad_items(self, obj):
        """Retorna la cantidad total de unidades en el carrito."""
        return obj.cantidad_items
