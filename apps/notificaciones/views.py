from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notificacion
from .serializers import NotificacionSerializer, NotificacionListSerializer


# ==============================================================================
# VIEWSET DE NOTIFICACIONES
# ==============================================================================
@extend_schema_view(
    retrieve=extend_schema(
        summary="Obtener detalle de una notificación",
        description="Retorna el contenido completo de una notificación específica.",
        parameters=[
            OpenApiParameter(
                name="id",
                type=str,
                location=OpenApiParameter.PATH,
                description="UUID de la notificación",
            )
        ],
    ),
    marcar_leida=extend_schema(
        summary="Marcar notificación como leída",
        description="Cambia el estado de una notificación específica a leída de forma idempotente.",
        parameters=[
            OpenApiParameter(
                name="id",
                type=str,
                location=OpenApiParameter.PATH,
                description="UUID de la notificación a marcar",
            )
        ],
    ),
)
class NotificacionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet de solo lectura para notificaciones del usuario autenticado.

    Endpoints:
        GET  /api/notificaciones/              - Listar mis notificaciones
        GET  /api/notificaciones/{id}/         - Detalle de notificación
        POST /api/notificaciones/{id}/marcar_leida/  - Marcar como leída
        POST /api/notificaciones/marcar_todas_leidas/ - Marcar todas como leídas

    Seguridad:
        Un usuario solo puede ver y marcar como leídas sus propias
        notificaciones. El filtro se aplica siempre en get_queryset().

    Filtros disponibles:
        ?leida=true / ?leida=false
        ?tipo=orden_confirmada
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["fecha_creacion"]
    ordering = ["-fecha_creacion"]

    def get_queryset(self):
        queryset = Notificacion.objects.filter(
            usuario=self.request.user
        ).select_related("usuario")

        leida = self.request.query_params.get("leida")
        if leida is not None:
            queryset = queryset.filter(leida=leida.lower() == "true")

        tipo = self.request.query_params.get("tipo")
        if tipo:
            queryset = queryset.filter(tipo=tipo)

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return NotificacionListSerializer
        return NotificacionSerializer

    @action(detail=True, methods=["post"], url_path="marcar_leida")
    def marcar_leida(self, request, pk=None) -> Response:
        """
        Marca una notificación específica como leída.

        POST /api/notificaciones/{id}/marcar_leida/
        """
        notificacion = self.get_object()
        notificacion.marcar_leida()

        serializer = NotificacionSerializer(notificacion)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="marcar_todas_leidas")
    def marcar_todas_leidas(self, request) -> Response:
        """
        Marca todas las notificaciones no leídas del usuario como leídas.

        POST /api/notificaciones/marcar_todas_leidas/
        """
        from django.utils import timezone

        actualizadas = self.get_queryset().filter(leida=False).update(
            leida=True,
            fecha_leida=timezone.now()
        )

        return Response(
            {"mensaje": f"{actualizadas} notificación(es) marcada(s) como leída(s)."},
            status=status.HTTP_200_OK
        )