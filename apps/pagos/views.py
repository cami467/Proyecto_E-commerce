from typing import TYPE_CHECKING

import stripe
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.conf import settings
from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser
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
    SubirComprobanteSerializer,
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
        GET  /api/pagos/                        - Listar mis pagos
        GET  /api/pagos/{id}/                   - Detalle de un pago
        POST /api/pagos/crear/                  - Iniciar un pago
        POST /api/pagos/simular/                - Simular pago (solo DEBUG)
        POST /api/pagos/{id}/aprobar-efectivo/  - Aprobar pago en efectivo (solo admin)
        POST /api/pagos/{id}/comprobante/       - Subir comprobante de transferencia (dueño)
        POST /api/pagos/{id}/aprobar-transferencia/ - Aprobar transferencia (solo admin)
        POST /api/pagos/{id}/rechazar-transferencia/ - Rechazar transferencia (solo admin)

    Nota: el webhook de Stripe (POST /api/pagos/webhook/stripe/) NO vive
    en este ViewSet. Se registra aparte en urls.py como una vista Django
    plana, porque Stripe no puede autenticarse con JWT — su seguridad
    depende de la verificación de firma, no de IsAuthenticated.

    Seguridad:
        - Solo se retornan pagos de órdenes del usuario autenticado.
        - El filtro se aplica en get_queryset() para consistencia.
        - El endpoint de simulación solo funciona con DEBUG=True.
        - aprobar_efectivo, aprobar_transferencia y rechazar_transferencia
          requieren is_staff, y no filtran por usuario propietario,
          porque son acciones administrativas sobre pagos de cualquier cliente.

    Rendimiento:
        get_queryset() aplica select_related para evitar N+1.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["fecha_creacion", "monto", "estado"]
    ordering = ["-fecha_creacion"]

    def get_queryset(self):
        """
        El cliente autenticado solo ve los pagos de sus propias órdenes.
        Un admin (is_staff) ve todos los pagos del sistema, ya que este
        mismo endpoint es el que alimenta el panel de gestión de pagos.
        """
        usuario = self.request.user

        if not usuario or not usuario.is_authenticated:
            return Pago.objects.none()

        queryset = (
            Pago.objects
            .select_related("orden", "orden__usuario")
            .order_by("-fecha_creacion")
        )

        if usuario.is_staff:
            return queryset

        return queryset.filter(orden__usuario_id=usuario.id)

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
        if self.action == "comprobante":
            return SubirComprobanteSerializer
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
            5. Si la pasarela es Stripe, crea el PaymentIntent y agrega
               client_secret a la respuesta (solo en esta respuesta,
               nunca se persiste en la base).
            6. Retorna el pago creado.

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

        # La llamada a Stripe se hace FUERA de la transacción atómica:
        # es una llamada de red externa, y no conviene tener filas de
        # la base bloqueadas (select_for_update) mientras esperamos
        # la respuesta de un servicio de terceros.
        client_secret = None

        if pasarela == Pago.Pasarela.STRIPE:
            client_secret = self._crear_payment_intent(pago, orden)
            if client_secret is None:
                # _crear_payment_intent ya canceló el pago y logueó
                # el detalle en respuesta_pasarela si algo falló.
                return Response(
                    {
                        "detail": (
                            "No se pudo iniciar el pago con Stripe. "
                            "Intentá de nuevo en unos momentos."
                        )
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        response_serializer = PagoSerializer(
            pago,
            context=self.get_serializer_context()
        )
        data = response_serializer.data

        if client_secret:
            # client_secret NUNCA se guarda en el modelo (no forma
            # parte de PagoSerializer): se necesita una sola vez, en
            # el frontend, para inicializar el Payment Element.
            data["client_secret"] = client_secret

        return Response(data, status=status.HTTP_201_CREATED)

    def _crear_payment_intent(self, pago: Pago, orden) -> str | None:
        """
        Crea un PaymentIntent de Stripe para un pago recién creado.

        Guarda el payment_intent.id en id_transaccion y un resumen en
        respuesta_pasarela para auditoría. El pago_id (nuestro UUID) va
        en los metadata del PaymentIntent para que el webhook pueda
        encontrar el Pago sin depender de comparar id_transaccion,
        que el modelo normaliza a mayúsculas en clean() y por lo tanto
        no coincide caracter a caracter con el id que manda Stripe.

        Retorna el client_secret si todo salió bien, o None si hubo
        un error de comunicación con Stripe (y en ese caso el pago
        queda cancelado, para no dejar un PENDING fantasma que nunca
        va a poder completarse).
        """
        stripe.api_key = settings.STRIPE_SECRET_KEY

        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=int(pago.monto),
                currency="pyg",
                metadata={
                    "pago_id": str(pago.id),
                    "orden_id": str(orden.id),
                },
                automatic_payment_methods={"enabled": True},
            )
        except stripe.error.StripeError as error:
            pago.respuesta_pasarela = {
                "error": True,
                "mensaje": str(error),
                "fecha": timezone.now().isoformat(),
            }
            pago.save(update_fields=["respuesta_pasarela", "fecha_actualizacion"])
            pago.cancelar()
            return None

        pago.id_transaccion = payment_intent.id
        pago.respuesta_pasarela = {
            "payment_intent_id": payment_intent.id,
            "status": payment_intent.status,
        }
        pago.save(
            update_fields=[
                "id_transaccion",
                "respuesta_pasarela",
                "fecha_actualizacion",
            ]
        )

        return payment_intent.client_secret

    # ------------------------------------------------------------------
    # ACCIÓN: APROBAR PAGO EN EFECTIVO (SOLO ADMIN)
    # ------------------------------------------------------------------
    @extend_schema(
        responses={200: PagoSerializer},
        summary="Confirmar cobro en efectivo (admin)",
        description="Aprueba manualmente un pago en efectivo que quedó pendiente, una vez que el administrador confirma haber recibido el dinero.",
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="aprobar-efectivo",
        url_name="aprobar-efectivo",
        permission_classes=[IsAdminUser],
    )
    def aprobar_efectivo(self, request, pk=None):
        """
        Aprueba un pago en efectivo pendiente. Solo accesible para
        administradores (is_staff). Reutiliza Pago.marcar_aprobado(),
        que ya es atómico, idempotente, y dispara la notificación
        en tiempo real al usuario vía WebSocket.

        Nota: a diferencia del resto del ViewSet, esta acción no
        filtra por get_queryset() (que restringe a pagos del usuario
        autenticado) porque un admin necesita poder aprobar el pago
        de cualquier cliente, no solo el suyo propio.

        POST /api/pagos/{id}/aprobar-efectivo/
        """
        try:
            pago = Pago.objects.select_related("orden__usuario").get(pk=pk)
        except Pago.DoesNotExist:
            return Response(
                {"detail": "Pago no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if pago.pasarela != Pago.Pasarela.EFECTIVO:
            return Response(
                {"detail": "Este endpoint solo aprueba pagos en efectivo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not pago.esta_pendiente:
            return Response(
                {
                    "detail": (
                        f"El pago ya fue procesado "
                        f"(estado actual: {pago.get_estado_display()})."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        pago.marcar_aprobado(
            id_transaccion=f"EFE-{str(pago.id)[:8].upper()}",
            respuesta={
                "aprobado_manualmente_por": request.user.email,
                "fecha": timezone.now().isoformat(),
            },
        )
        pago.refresh_from_db()

        response_serializer = PagoSerializer(
            pago, context=self.get_serializer_context()
        )
        return Response(response_serializer.data)

    # ------------------------------------------------------------------
    # ACCIÓN: SUBIR COMPROBANTE DE TRANSFERENCIA (DUEÑO DEL PAGO)
    # ------------------------------------------------------------------
    @extend_schema(
        request=SubirComprobanteSerializer,
        responses={200: PagoSerializer},
        summary="Subir comprobante de transferencia",
        description="Permite al cliente adjuntar el comprobante de una transferencia bancaria a un pago propio que sigue pendiente.",
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="comprobante",
        url_name="comprobante",
        parser_classes=[MultiPartParser, FormParser],
    )
    def comprobante(self, request, pk=None):
        """
        Sube el comprobante de una transferencia bancaria.

        Solo el dueño de la orden puede subir el comprobante de su
        propio pago, y solo mientras siga pendiente. Se puede volver
        a subir (reemplaza el anterior) mientras el pago no se haya
        procesado todavía, por si el cliente se equivoca de archivo.

        POST /api/pagos/{id}/comprobante/
        Content-Type: multipart/form-data
        """
        try:
            pago = Pago.objects.select_related("orden__usuario").get(
                pk=pk,
                orden__usuario=request.user,
                pasarela=Pago.Pasarela.TRANSFERENCIA,
            )
        except Pago.DoesNotExist:
            return Response(
                {"detail": "Pago no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not pago.esta_pendiente:
            return Response(
                {
                    "detail": (
                        "El pago ya fue procesado, no se puede "
                        "modificar el comprobante."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SubirComprobanteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pago.comprobante = serializer.validated_data["comprobante"]
        pago.referencia_cliente = serializer.validated_data.get(
            "referencia_cliente", ""
        )
        pago.observacion_cliente = serializer.validated_data.get(
            "observacion_cliente", ""
        )
        pago.save(
            update_fields=[
                "comprobante",
                "referencia_cliente",
                "observacion_cliente",
                "fecha_actualizacion",
            ]
        )

        response_serializer = PagoSerializer(
            pago, context=self.get_serializer_context()
        )
        return Response(response_serializer.data)

    # ------------------------------------------------------------------
    # ACCIÓN: APROBAR TRANSFERENCIA (SOLO ADMIN)
    # ------------------------------------------------------------------
    @extend_schema(
        responses={200: PagoSerializer},
        summary="Aprobar transferencia bancaria (admin)",
        description="Aprueba manualmente un pago por transferencia luego de verificar el comprobante subido por el cliente.",
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="aprobar-transferencia",
        url_name="aprobar-transferencia",
        permission_classes=[IsAdminUser],
    )
    def aprobar_transferencia(self, request, pk=None):
        """
        Aprueba un pago por transferencia pendiente, tras revisar el
        comprobante subido por el cliente. Solo accesible para admins.
        Reutiliza Pago.marcar_aprobado(), igual que aprobar_efectivo.

        POST /api/pagos/{id}/aprobar-transferencia/
        """
        try:
            pago = Pago.objects.select_related("orden__usuario").get(pk=pk)
        except Pago.DoesNotExist:
            return Response(
                {"detail": "Pago no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if pago.pasarela != Pago.Pasarela.TRANSFERENCIA:
            return Response(
                {"detail": "Este endpoint solo aprueba pagos por transferencia."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not pago.esta_pendiente:
            return Response(
                {
                    "detail": (
                        f"El pago ya fue procesado "
                        f"(estado actual: {pago.get_estado_display()})."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        pago.marcar_aprobado(
            id_transaccion=f"TRF-{str(pago.id)[:8].upper()}",
            respuesta={
                "aprobado_manualmente_por": request.user.email,
                "fecha": timezone.now().isoformat(),
                "referencia_cliente": pago.referencia_cliente,
            },
        )
        pago.refresh_from_db()

        response_serializer = PagoSerializer(
            pago, context=self.get_serializer_context()
        )
        return Response(response_serializer.data)

    # ------------------------------------------------------------------
    # ACCIÓN: RECHAZAR TRANSFERENCIA (SOLO ADMIN)
    # ------------------------------------------------------------------
    @extend_schema(
        responses={200: PagoSerializer},
        summary="Rechazar transferencia bancaria (admin)",
        description="Rechaza un pago por transferencia cuando el comprobante no es válido o no se verificó el depósito.",
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="rechazar-transferencia",
        url_name="rechazar-transferencia",
        permission_classes=[IsAdminUser],
    )
    def rechazar_transferencia(self, request, pk=None):
        """
        Rechaza un pago por transferencia pendiente. Solo accesible
        para admins. Reutiliza Pago.marcar_rechazado(), que dispara
        la notificación al cliente automáticamente.

        POST /api/pagos/{id}/rechazar-transferencia/
        Body opcional:
            { "motivo": "El comprobante no corresponde al monto de la orden." }
        """
        try:
            pago = Pago.objects.select_related("orden__usuario").get(pk=pk)
        except Pago.DoesNotExist:
            return Response(
                {"detail": "Pago no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if pago.pasarela != Pago.Pasarela.TRANSFERENCIA:
            return Response(
                {"detail": "Este endpoint solo rechaza pagos por transferencia."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not pago.esta_pendiente:
            return Response(
                {
                    "detail": (
                        f"El pago ya fue procesado "
                        f"(estado actual: {pago.get_estado_display()})."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        motivo = request.data.get("motivo", "")

        pago.marcar_rechazado(
            respuesta={
                "rechazado_manualmente_por": request.user.email,
                "fecha": timezone.now().isoformat(),
                "motivo": motivo,
            },
        )
        pago.refresh_from_db()

        response_serializer = PagoSerializer(
            pago, context=self.get_serializer_context()
        )
        return Response(response_serializer.data)

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