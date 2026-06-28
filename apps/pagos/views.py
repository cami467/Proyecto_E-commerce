from typing import TYPE_CHECKING
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.conf import settings
from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from core.exceptions import PagoFallido
from .models import Pago
from .serializers import (
    PagoSerializer,
    PagoListSerializer,
    CrearPagoSerializer,
    SimularPagoSerializer,
)


# ==============================================================================
# MIXIN DE CONTEXTO
# ==============================================================================

class SerializerContextMixin:
    """
    Mixin reutilizable que garantiza que el request siempre
    esté disponible en el contexto del serializer.
    """
    def get_serializer_context(self) -> dict:
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


# ==============================================================================
# VIEWSET DE PAGOS
# ==============================================================================
@extend_schema_view(
    retrieve=extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description="UUID del pago.",
            )
        ]
    )
)
class PagoViewSet(
    SerializerContextMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet de pagos del usuario autenticado.

    Un usuario solo puede ver los pagos de sus propias órdenes.
    La creación de pagos se maneja como acción separada.

    Endpoints:
        GET  /api/pagos/              - Listar mis pagos
        GET  /api/pagos/{id}/         - Detalle de un pago
        POST /api/pagos/crear/        - Iniciar un pago
        POST /api/pagos/simular/      - Simular pago (solo DEBUG)

    Seguridad:
        - Solo se retornan pagos de órdenes del usuario autenticado.
        - El filtro se aplica en get_queryset() para consistencia.
        - El endpoint de simulación solo funciona con DEBUG=True.

    Rendimiento:
        get_queryset() aplica select_related para evitar N+1.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["fecha_creacion", "monto", "estado"]
    ordering = ["-fecha_creacion"]

    def get_queryset(self):
        """
        Retorna únicamente los pagos de órdenes del usuario autenticado.
        El filtro por usuario se aplica siempre sin excepciones.
        """
        return Pago.objects.filter(
            orden__usuario=self.request.user
        ).select_related("orden__usuario")

    def get_serializer_class(self):
        """
        Usa el serializer resumido para listados y el completo
        para detalle y acciones de escritura.
        """
        if self.action == "list":
            return PagoListSerializer
        if self.action == "crear":
            return CrearPagoSerializer
        if self.action == "simular":
            return SimularPagoSerializer
        return PagoSerializer

    # ------------------------------------------------------------------
    # ACCIÓN: CREAR PAGO
    # ------------------------------------------------------------------

    @action(
        detail=False,
        methods=["post"],
        url_path="crear",
        url_name="crear"
    )
    def crear(self, request) -> Response:
        """
        Inicia un pago sobre una orden existente del usuario.

        El monto se toma del total de la orden, nunca del cliente,
        para prevenir manipulaciones de precio desde el frontend.

        Flujo:
            1. Valida orden_id y pasarela.
            2. Verifica que la orden pertenezca al usuario.
            3. Verifica que la orden esté en estado que permita pago.
            4. Crea el registro Pago en estado PENDING.
            5. Retorna el pago creado.

        Nota: La integración real con la pasarela (Stripe, Mercado Pago)
        se implementa aquí llamando al gateway correspondiente.
        Por ahora crea el pago en estado PENDING listo para procesarse.

        POST /api/pagos/crear/
        Body:
            {
                "orden_id": "uuid-de-la-orden",
                "pasarela": "efectivo"
            }
        """
        serializer = CrearPagoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        orden_id = serializer.validated_data["orden_id"]
        pasarela = serializer.validated_data["pasarela"]

        # Verificar que la orden exista y pertenezca al usuario
        try:
            from apps.ordenes.models import Orden
            orden = Orden.objects.get(
                id=orden_id,
                usuario=request.user
            )
        except Orden.DoesNotExist:
            return Response(
                {"detail": "La orden no existe o no te pertenece."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verificar que la orden esté en un estado que permita pago
        estados_pagables = [
            Orden.Estado.PENDING,
            Orden.Estado.CONFIRMED
        ]
        if orden.estado not in estados_pagables:
            return Response(
                {
                    "detail": (
                        f"No se puede pagar una orden en estado "
                        f"'{orden.get_estado_display()}'. "
                        f"Solo se pueden pagar órdenes pendientes o confirmadas."
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        # Verificar que no haya un pago aprobado previo
        if orden.pagos.filter(estado=Pago.Estado.APPROVED).exists():
            return Response(
                {"detail": "Esta orden ya tiene un pago aprobado."},
                status=status.HTTP_409_CONFLICT
            )

        # Crear el pago en estado PENDING
        pago = Pago.objects.create(
            orden=orden,
            pasarela=pasarela,
            monto=orden.total,
            estado=Pago.Estado.PENDING,
        )

        response_serializer = PagoSerializer(
            pago,
            context=self.get_serializer_context()
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )

    # ------------------------------------------------------------------
    # ACCIÓN: SIMULAR PAGO (SOLO DEBUG)
    # ------------------------------------------------------------------

    @action(
        detail=False,
        methods=["post"],
        url_path="simular",
        url_name="simular"
    )
    def simular(self, request) -> Response:
        """
        Simula el resultado de un pago para desarrollo y testing.

        IMPORTANTE: Este endpoint está deshabilitado en producción.
        Solo funciona cuando DEBUG=True en settings.

        Permite simular pagos aprobados y rechazados sin conectarse
        a una pasarela real, facilitando el desarrollo del frontend.

        POST /api/pagos/simular/
        Body:
            {
                "pago_id": "uuid-del-pago",
                "resultado": "approved",
                "id_transaccion": "SIM-TEST-001"
            }
        """
        # Bloqueo de seguridad: nunca disponible en producción
        if not settings.DEBUG:
            return Response(
                {"detail": "Este endpoint no está disponible en producción."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = SimularPagoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pago_id = serializer.validated_data["pago_id"]
        resultado = serializer.validated_data["resultado"]
        id_transaccion = serializer.validated_data["id_transaccion"]

        # Verificar que el pago exista y pertenezca al usuario
        try:
            pago = Pago.objects.select_related(
                "orden__usuario"
            ).get(
                id=pago_id,
                orden__usuario=request.user
            )
        except Pago.DoesNotExist:
            return Response(
                {"detail": "El pago no existe o no te pertenece."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verificar que el pago esté pendiente
        if not pago.esta_pendiente:
            return Response(
                {
                    "detail": (
                        f"No se puede simular un pago en estado "
                        f"'{pago.get_estado_display()}'. "
                        f"Solo se pueden simular pagos pendientes."
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        # Aplicar el resultado simulado
        respuesta_simulada = {
            "simulado": True,
            "resultado": resultado,
            "id_transaccion": id_transaccion,
            "fecha": timezone.now().isoformat(),
        }

        if resultado == "approved":
            pago.marcar_aprobado(
                id_transaccion=id_transaccion,
                respuesta=respuesta_simulada
            )
        else:
            pago.marcar_rechazado(respuesta=respuesta_simulada)

        response_serializer = PagoSerializer(
            pago,
            context=self.get_serializer_context()
        )
        return Response(response_serializer.data)
