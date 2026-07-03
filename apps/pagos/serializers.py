from decimal import Decimal
from typing import TYPE_CHECKING

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, OpenApiTypes

from .models import Pago

if TYPE_CHECKING:
    pass


# ==============================================================================
# CONSTANTES DE NEGOCIO
# ==============================================================================

MONTO_MINIMO_PAGO = Decimal("1")
"""
Monto mínimo aceptado para un pago en Guaraníes.
Evita que se procesen pagos de monto cero o negativo
antes de llegar al modelo.
"""

MONTO_MAXIMO_PAGO = Decimal("999999999")
"""
Tope máximo de un pago en Guaraníes.
Previene errores de datos fuera de rango que pasarían
la validación de tipo pero no tienen sentido de negocio.
"""


# ==============================================================================
# SERIALIZER DE LECTURA — LISTADO
# ==============================================================================

class PagoListSerializer(serializers.ModelSerializer):
    """
    Serializer resumido para el listado de pagos.

    Diseñado para GET /api/pagos/ donde se listan muchos pagos.
    No incluye respuesta_pasarela para reducir el payload
    y proteger datos sensibles de la pasarela en listados masivos.

    Campos calculados:
        estado_display: etiqueta legible del estado actual.
        pasarela_display: etiqueta legible de la pasarela usada.
        es_exitoso: indica si el pago fue aprobado.
    """
    estado_display = serializers.CharField(
        source="get_estado_display",
        read_only=True,
        help_text="Etiqueta legible del estado del pago."
    )
    pasarela_display = serializers.CharField(
        source="get_pasarela_display",
        read_only=True,
        help_text="Etiqueta legible de la pasarela utilizada."
    )
    es_exitoso = serializers.BooleanField(
        read_only=True,
        help_text="True si el pago fue aprobado por la pasarela."
    )

    class Meta:
        model = Pago
        fields = [
            "id",
            "orden",
            "pasarela",
            "pasarela_display",
            "estado",
            "estado_display",
            "es_exitoso",
            "monto",
            "id_transaccion",
            "fecha_procesado",
            "fecha_creacion",
        ]
        read_only_fields = fields

    def to_representation(self, instance: Pago) -> dict:
        """
        Convierte el monto a entero en Guaraníes.
        Elimina el separador decimal innecesario (ej: 150000 en lugar de 150000.00).
        """
        data = super().to_representation(instance)
        data["monto"] = int(instance.monto)
        return data


# ==============================================================================
# SERIALIZER DE LECTURA — DETALLE
# ==============================================================================

class PagoSerializer(serializers.ModelSerializer):
    """
    Serializer completo para el detalle de un pago individual.

    Incluye la respuesta completa de la pasarela para auditoría.
    Solo debe usarse en endpoints de detalle, nunca en listados,
    porque respuesta_pasarela puede contener objetos JSON grandes.

    Nota de seguridad:
        respuesta_pasarela puede contener datos sensibles de la
        pasarela de pago. Este endpoint debe estar restringido
        a usuarios staff o al propietario de la orden.

    Rendimiento:
        La vista debe usar select_related("orden__usuario")
        para evitar N+1 al acceder a datos de la orden.
    """
    estado_display = serializers.CharField(
        source="get_estado_display",
        read_only=True,
        help_text="Etiqueta legible del estado del pago."
    )
    pasarela_display = serializers.CharField(
        source="get_pasarela_display",
        read_only=True,
        help_text="Etiqueta legible de la pasarela utilizada."
    )
    es_exitoso = serializers.BooleanField(
        read_only=True,
        help_text="True si el pago fue aprobado por la pasarela."
    )
    esta_pendiente = serializers.BooleanField(
        read_only=True,
        help_text="True si el pago aun no fue procesado."
    )
    es_reembolsable = serializers.BooleanField(
        read_only=True,
        help_text="True si el pago puede ser reembolsado."
    )

    class Meta:
        model = Pago
        fields = [
            "id",
            "orden",
            "pasarela",
            "pasarela_display",
            "estado",
            "estado_display",
            "es_exitoso",
            "esta_pendiente",
            "es_reembolsable",
            "monto",
            "id_transaccion",
            "respuesta_pasarela",
            "fecha_procesado",
            "fecha_creacion",
            "fecha_actualizacion",
        ]
        read_only_fields = fields

    def to_representation(self, instance: Pago) -> dict:
        """
        Convierte el monto a entero en Guaraníes y normaliza
        campos opcionales para consistencia del frontend.

        Si id_transaccion esta vacio se retorna None en lugar de ""
        para que el frontend distinga entre pago no procesado
        y pago procesado sin ID de transaccion.
        """
        data = super().to_representation(instance)
        data["monto"] = int(instance.monto)
        if not data.get("id_transaccion"):
            data["id_transaccion"] = None
        return data


# ==============================================================================
# SERIALIZERS DE ESCRITURA
# ==============================================================================

class CrearPagoSerializer(serializers.Serializer):
    """
    Serializer para iniciar un pago sobre una orden existente.

    El monto del pago se toma del total de la orden en la vista.
    El usuario nunca envía el monto directamente para prevenir
    manipulaciones del precio desde el cliente.

    Validaciones aplicadas:
        pasarela:
            Debe ser una de las pasarelas habilitadas en el sistema.
            Valor inválido retorna 400 antes de llegar a la vista.
        orden_id:
            Se verifica que la orden exista, pertenezca al usuario
            autenticado y esté en un estado que permita pago.
            La verificación de propiedad ocurre en la vista,
            no aquí, para mantener la lógica de seguridad centralizada.

    Nota de diseño:
        Este serializer valida la entrada del cliente.
        La lógica de negocio (crear el registro Pago, llamar
        a la pasarela, actualizar el estado de la orden) ocurre
        en el servicio de pagos, no aquí.
    """
    orden_id = serializers.UUIDField(
        help_text="UUID de la orden a pagar."
    )
    pasarela = serializers.ChoiceField(
        choices=Pago.Pasarela.choices,
        help_text="Pasarela de pago a utilizar."
    )

    def validate_pasarela(self, value: str) -> str:
        """
        Verifica que la pasarela seleccionada esté habilitada.
        En producción se puede conectar a una configuración dinámica
        para habilitar/deshabilitar pasarelas sin deploy.
        """
        pasarelas_habilitadas = [
            Pago.Pasarela.EFECTIVO,
            Pago.Pasarela.TRANSFERENCIA,
            Pago.Pasarela.MERCADO_PAGO,
            Pago.Pasarela.STRIPE,
        ]
        if value not in pasarelas_habilitadas:
            raise serializers.ValidationError(
                f"La pasarela '{value}' no está habilitada en este momento."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        """Valida la orden antes de que la vista cree el pago."""
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Debes iniciar sesión para crear un pago."
            )

        from apps.ordenes.models import Orden

        try:
            orden = Orden.objects.get(
                id=attrs["orden_id"],
                usuario=request.user,
            )
        except Orden.DoesNotExist:
            raise serializers.ValidationError({
                "orden_id": "La orden no existe o no te pertenece."
            })

        if orden.total < MONTO_MINIMO_PAGO:
            raise serializers.ValidationError({
                "orden_id": "La orden no tiene un total válido para pagar."
            })
        if orden.total > MONTO_MAXIMO_PAGO:
            raise serializers.ValidationError({
                "orden_id": "El total de la orden supera el monto máximo permitido."
            })

        attrs["orden"] = orden
        return attrs


class SimularPagoSerializer(serializers.Serializer):
    """
    Serializer para simular el resultado de un pago en desarrollo.

    SOLO para uso en entornos de desarrollo y testing.
    Este endpoint NUNCA debe estar habilitado en producción.

    Permite simular pagos aprobados y rechazados sin conectarse
    a una pasarela real, facilitando el desarrollo del frontend
    y las pruebas de integración.

    La vista correspondiente debe verificar que DEBUG=True
    antes de procesar esta solicitud.
    """
    pago_id = serializers.UUIDField(
        help_text="UUID del pago a simular."
    )
    resultado = serializers.ChoiceField(
        choices=["approved", "rejected"],
        help_text="Resultado simulado: 'approved' o 'rejected'."
    )
    id_transaccion = serializers.CharField(
        required=False,
        default="SIM-TEST-001",
        max_length=255,
        help_text="ID de transacción simulado para testing."
    )

    def validate_id_transaccion(self, value: str) -> str:
        """Normaliza el ID de transacción simulado."""
        return value.strip().upper() if value else "SIM-TEST-001"