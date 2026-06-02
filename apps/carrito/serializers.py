from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Carrito, ItemCarrito
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
        read_only_fields = ["id", "subtotal"]

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
    y que haya stock suficiente.
    """
    variante_id = serializers.UUIDField()
    cantidad = serializers.IntegerField(min_value=1, default=1)

    def validate(self, data):
        """Validacion cruzada de variante y stock disponible."""
        from apps.productos.models import Variante

        try:
            variante = Variante.objects.get(
                id=data["variante_id"],
                esta_activo=True
            )
        except Variante.DoesNotExist:
            raise serializers.ValidationError({
                "variante_id": "La variante no existe o no esta disponible."
            })

        if variante.inventario < data["cantidad"]:
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
        read_only_fields = ["id", "usuario", "total", "cantidad_items"]

    @extend_schema_field(ItemCarritoSerializer(many=True))
    def get_items(self, obj):
        """
        Retorna unicamente los items activos del carrito.
        Usa select_related para evitar N+1 queries.
        """
        items_activos = obj.items.filter(
            esta_activo=True
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