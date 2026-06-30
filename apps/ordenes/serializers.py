from decimal import Decimal
from typing import TYPE_CHECKING

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, OpenApiTypes

from .models import Orden, ItemOrden, HistorialEstadoOrden

if TYPE_CHECKING:
    pass


# ==============================================================================
# CONSTANTES DE NEGOCIO
# ==============================================================================

MAX_COSTO_ENVIO = Decimal("9_999_999")
"""
Tope máximo del costo de envío en Guaraníes.
Evita que un error en el frontend envíe valores fuera de rango
que pasarían la validación de tipo pero no tienen sentido de negocio.
"""


# ==============================================================================
# SERIALIZER DE ITEM DE ORDEN
# ==============================================================================

class ItemOrdenSerializer(serializers.ModelSerializer):
    """
    Serializer de solo lectura para los ítems de una orden confirmada.

    Los precios están congelados al momento de la compra mediante los
    campos nombre_producto, nombre_variante y precio_unitario del modelo.
    Esto garantiza que si un producto cambia de nombre o precio después,
    la orden histórica siempre refleja los valores originales.

    Campos calculados:
        subtotal (int): precio_unitario × cantidad en Guaraníes.
                        Declarado como IntegerField explícito para que
                        DRF lo serialice correctamente desde la
                        @property del modelo sin colisión de nombres.
    """
    subtotal = serializers.IntegerField(read_only=True)

    class Meta:
        model = ItemOrden
        fields = [
            "id",
            "variante",
            "nombre_producto",
            "nombre_variante",
            "cantidad",
            "precio_unitario",
            "tasa_iva",
            "subtotal",
            "monto_iva",
        ]
        read_only_fields = fields

    def to_representation(self, instance: ItemOrden) -> dict:
        """
        Garantiza que precio_unitario y subtotal siempre se
        serialicen como enteros, eliminando el separador decimal
        innecesario para Guaraníes (ej: 135000 en lugar de 135000.00).
        """
        data = super().to_representation(instance)
        data["precio_unitario"] = int(instance.precio_unitario)
        data["subtotal"] = int(instance.subtotal)
        data["monto_iva"] = int(instance.monto_iva)
        return data


# ==============================================================================
# SERIALIZER DE HISTORIAL DE ESTADO
# ==============================================================================

class HistorialEstadoOrdenSerializer(serializers.ModelSerializer):
    """
    Serializer de solo lectura para el historial de cambios de estado.

    Cada entrada representa un evento auditado con quién realizó
    el cambio, desde qué estado, hacia qué estado y cuándo.
    Incluye el username del responsable para legibilidad directa
    en el frontend sin necesidad de una llamada adicional.

    Este historial es inmutable — ningún campo puede modificarse
    una vez registrado para preservar la integridad de la auditoría.
    """
    cambiado_por_username = serializers.CharField(
        source="cambiado_por.username",
        read_only=True
    )
    estado_anterior_display = serializers.SerializerMethodField(
        help_text="Etiqueta legible del estado anterior."
    )
    estado_nuevo_display = serializers.SerializerMethodField(
        help_text="Etiqueta legible del estado nuevo."
    )

    class Meta:
        model = HistorialEstadoOrden
        fields = [
            "id",
            "estado_anterior",
            "estado_anterior_display",
            "estado_nuevo",
            "estado_nuevo_display",
            "cambiado_por",
            "cambiado_por_username",
            "fecha",
            "comentario",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_estado_anterior_display(self, obj: HistorialEstadoOrden) -> str | None:
        """
        Retorna la etiqueta legible del estado anterior.
        Puede ser None si la orden fue creada directamente en un estado
        sin estado previo (ej: primera entrada del historial).
        """
        if not obj.estado_anterior:
            return None
        return dict(Orden.Estado.choices).get(obj.estado_anterior, obj.estado_anterior)

    @extend_schema_field(OpenApiTypes.STR)
    def get_estado_nuevo_display(self, obj: HistorialEstadoOrden) -> str:
        """Retorna la etiqueta legible del estado nuevo."""
        return dict(Orden.Estado.choices).get(obj.estado_nuevo, obj.estado_nuevo)


# ==============================================================================
# SERIALIZERS DE ORDEN — LECTURA
# ==============================================================================

class OrdenListSerializer(serializers.ModelSerializer):
    """
    Serializer resumido para el listado paginado de órdenes.

    Optimizado para GET /api/ordenes/ donde se listan muchas órdenes
    simultáneamente. Deliberadamente excluye items e historial para
    evitar queries anidadas innecesarias en el listado.

    La lógica de formato de numero_orden vive en el modelo (propiedad
    numero_orden_display) siguiendo el principio de responsabilidad única:
    el serializer solo expone, el modelo formatea.

    Rendimiento: la vista debe usar select_related("usuario") para
    evitar N+1 al acceder a campos del usuario si se agregan en el futuro.
    """
    estado_display = serializers.CharField(
        source="get_estado_display",
        read_only=True,
        help_text="Etiqueta legible del estado actual de la orden."
    )
    numero_orden = serializers.CharField(
        source="numero_orden_display",
        read_only=True,
        help_text="Identificador legible de la orden. Ej: #A3F2B1C4"
    )

    class Meta:
        model = Orden
        fields = [
            "id",
            "numero_orden",
            "estado",
            "estado_display",
            "subtotal",
            "monto_descuento",
            "costo_envio",
            "total",
            "fecha_creacion",
        ]
        read_only_fields = fields

    def to_representation(self, instance: Orden) -> dict:
        """
        Convierte todos los montos monetarios a enteros en Guaraníes
        para consistencia con el formato de la API.
        """
        data = super().to_representation(instance)
        for campo in ("subtotal", "monto_descuento", "costo_envio", "total"):
            if data.get(campo) is not None:
                data[campo] = int(getattr(instance, campo, 0) or 0)
        return data


class OrdenSerializer(serializers.ModelSerializer):
    """
    Serializer completo para el detalle de una orden individual.

    Incluye la lista completa de ítems con precios congelados y
    el historial íntegro de cambios de estado para trazabilidad total.

    Usado en: GET /api/ordenes/{id}/

    Nota de rendimiento: este serializer carga relaciones anidadas.
    La vista correspondiente DEBE usar:
        .select_related("usuario")
        .prefetch_related("items__variante__producto", "historial_estados__cambiado_por")
    para evitar el problema N+1. Si no se aplica el prefetch, con una
    orden de 20 ítems se generarían 40+ queries adicionales.
    """
    items = ItemOrdenSerializer(
        many=True,
        read_only=True,
        help_text="Lista de ítems con precios congelados al momento de la compra."
    )
    historial_estados = HistorialEstadoOrdenSerializer(
        many=True,
        read_only=True,
        help_text="Historial completo de cambios de estado para auditoría."
    )
    estado_display = serializers.CharField(
        source="get_estado_display",
        read_only=True,
        help_text="Etiqueta legible del estado actual."
    )
    numero_orden = serializers.CharField(
        source="numero_orden_display",
        read_only=True,
        help_text="Identificador legible de la orden. Ej: #A3F2B1C4"
    )
    puede_cancelarse = serializers.BooleanField(
        read_only=True,
        help_text="Indica si la orden puede cancelarse según su estado actual."
    )

    class Meta:
        model = Orden
        fields = [
            "id",
            "numero_orden",
            "usuario",
            "estado",
            "estado_display",
            "puede_cancelarse",
            "subtotal",
            "monto_descuento",
            "costo_envio",
            "total",
            "codigo_cupon",
            "notas",
            "items",
            "historial_estados",
            "fecha_creacion",
            "fecha_actualizacion",
        ]
        read_only_fields = fields

    def to_representation(self, instance: Orden) -> dict:
        """
        Convierte todos los montos monetarios a enteros en Guaraníes
        y normaliza campos opcionales vacíos para consistencia del frontend.

        Un campo codigo_cupon vacío se retorna como None en lugar de ""
        para que el frontend pueda distinguir entre "sin cupón" y
        "cupón aplicado pero inválido".
        """
        data = super().to_representation(instance)
        for campo in ("subtotal", "monto_descuento", "costo_envio", "total"):
            if data.get(campo) is not None:
                data[campo] = int(getattr(instance, campo, 0) or 0)
        if not data.get("codigo_cupon"):
            data["codigo_cupon"] = None
        return data


# ==============================================================================
# SERIALIZERS DE ORDEN — ESCRITURA
# ==============================================================================

class CrearOrdenSerializer(serializers.Serializer):
    """
    Serializer para crear una orden desde el carrito activo del usuario.

    El carrito se obtiene automáticamente desde request.user en la vista,
    el cliente nunca envía un carrito_id para prevenir acceso cruzado
    entre usuarios.

    Validaciones aplicadas:
        costo_envio:
            - Tipo: Decimal, 0 decimales (Guaraníes).
            - min_value=0 rechaza negativos nativamente sin validate_ extra.
            - max_value=MAX_COSTO_ENVIO previene errores de datos fuera de rango.
        codigo_cupon:
            - Se normaliza a mayúsculas y sin espacios antes de llegar a la vista.
            - La validación de existencia y vigencia ocurre en el servicio,
              no aquí, para mantener la lógica de negocio centralizada.
        notas:
            - Texto libre, máximo 1000 caracteres para prevenir entradas abusivas.
    """
    costo_envio = serializers.DecimalField(
        max_digits=12,
        decimal_places=0,
        min_value=Decimal("0"),
        max_value=MAX_COSTO_ENVIO,
        default=Decimal("0"),
        required=False,
        help_text=f"Costo de envío en Guaraníes. Máximo: {MAX_COSTO_ENVIO:,.0f} Gs."
    )
    codigo_cupon = serializers.CharField(
        max_length=50,
        required=False,
        default="",
        allow_blank=True,
        help_text="Código de cupón de descuento (opcional)."
    )
    notas = serializers.CharField(
        required=False,
        default="",
        allow_blank=True,
        max_length=1_000,
        help_text="Observaciones adicionales. Máximo 1000 caracteres."
    )

    def validate_codigo_cupon(self, value: str) -> str:
        """
        Normaliza el código de cupón: elimina espacios y convierte a mayúsculas.
        La validación de existencia y vigencia ocurre en el servicio de negocio.
        """
        return value.strip().upper() if value else ""

    def validate_notas(self, value: str) -> str:
        """Elimina espacios al inicio y al final de las notas."""
        return value.strip() if value else ""


class CancelarOrdenSerializer(serializers.Serializer):
    """
    Serializer para solicitar la cancelación de una orden existente.

    La validación de si la orden puede cancelarse según su estado
    ocurre en la vista mediante orden.puede_cancelarse y en el
    método orden.cancelar() del modelo, no aquí.

    El comentario es opcional pero se recomienda para auditoría.
    Límite de 500 caracteres para mantener los logs legibles.
    """
    comentario = serializers.CharField(
        required=False,
        default="",
        allow_blank=True,
        max_length=500,
        help_text=(
            "Motivo de la cancelación (opcional). "
            "Queda registrado permanentemente en el historial de estados."
        )
    )

    def validate_comentario(self, value: str) -> str:
        """Elimina espacios al inicio y al final del comentario."""
        return value.strip() if value else ""