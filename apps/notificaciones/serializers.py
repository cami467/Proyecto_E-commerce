from rest_framework import serializers
from .models import Notificacion


# ==============================================================================
# SERIALIZER DE LECTURA — LISTADO
# ==============================================================================

class NotificacionListSerializer(serializers.ModelSerializer):
    """
    Serializer resumido para listado de notificaciones del usuario.
    Optimizado para GET /api/notificaciones/ con muchos registros.
    """
    tipo_display = serializers.CharField(
        source="get_tipo_display",
        read_only=True
    )

    class Meta:
        model = Notificacion
        fields = [
            "id",
            "tipo",
            "tipo_display",
            "titulo",
            "leida",
            "referencia_id",
            "fecha_creacion",
        ]
        read_only_fields = fields


# ==============================================================================
# SERIALIZER DE LECTURA — DETALLE
# ==============================================================================

class NotificacionSerializer(serializers.ModelSerializer):
    """
    Serializer completo para el detalle de una notificación.
    Incluye el mensaje completo y la fecha de lectura.
    """
    tipo_display = serializers.CharField(
        source="get_tipo_display",
        read_only=True
    )

    class Meta:
        model = Notificacion
        fields = [
            "id",
            "tipo",
            "tipo_display",
            "titulo",
            "mensaje",
            "leida",
            "fecha_leida",
            "referencia_id",
            "fecha_creacion",
        ]
        read_only_fields = fields