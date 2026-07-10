from typing import TYPE_CHECKING
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.conf import settings
from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone

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
                description="UUID del pago a consultar",
            )
        ],
        summary="Ver detalle de un pago",
        description="Retorna la información completa de una transacción financiera específica.",
    ),
    list=extend_schema(
        summary="Listar mis pagos",
        description="Retorna el historial completo de pagos realizados o pendientes del usuario autenticado.",
    ),
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
        usuario = self.request.user

        if not usuario or not usuario.is_authenticated:
            return Pago.objects.none()

        return (
        Pago.objects
        .filter(orden__usuario_id=usuario.id)
        .select_related("orden", "orden__usuario")
        .order_by("-fecha_creacion")
    )

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

    
    @extend_schema(
        request=CrearPagoSerializer,
        responses={201: PagoSerializer},
        summary="Registrar o iniciar un pago",
        description="Inicia el proceso de pago para una orden pendiente, validando montos y estados.",
    )
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
        serializer = CrearPagoSerializer(
            data=request.data,
            context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        orden = serializer.validated_data["orden"]
        pasarela = serializer.validated_data["pasarela"]

        from apps.ordenes.models import Orden

        with transaction.atomic():
            orden = (
                Orden.objects
                .select_for_update()
                .get(pk=orden.pk, usuario=request.user)
            )

            estados_pagables = [
                Orden.Estado.PENDING,
                Orden.Estado.CONFIRMED,
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

            if orden.pagos.filter(estado=Pago.Estado.APPROVED).exists():
                return Response(
                    {"detail": "Esta orden ya tiene un pago aprobado."},
                    status=status.HTTP_409_CONFLICT
                )

            if orden.pagos.filter(estado=Pago.Estado.PENDING).exists():
                return Response(
                    {"detail": "Esta orden ya tiene un pago pendiente."},
                    status=status.HTTP_409_CONFLICT
                )

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
    @extend_schema(
        request=SimularPagoSerializer,
        responses={200: PagoSerializer},
        summary="Simular pasarela de pagos (Solo DEBUG)",
        description="Permite simular la aprobación o rechazo de una pasarela externa. Requiere DEBUG=True.",
    )
    @action(detail=False, methods=["post"], url_path="simular")
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
            raise PermissionDenied("El simulador de pagos solo está disponible en entorno de desarrollo.")

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
            raise ValidationError({"pago": "El pago no existe o no te pertenece."})

        # Verificar que el pago esté pendiente
        if not pago.esta_pendiente:
           raise ValidationError({
                "pago": f"No se puede simular un pago en estado '{pago.get_estado_display()}'. Solo se permiten pagos pendientes."
            })

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