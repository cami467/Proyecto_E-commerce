from decimal import Decimal
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Prefetch
from django.http import HttpResponse
from .factura import generar_factura_pdf
from django.http import Http404

from core.exceptions import CarritoVacio, StockInsuficiente, CuponInvalido
from apps.cupones.models import Cupon
from .models import Orden, ItemOrden, HistorialEstadoOrden
from .serializers import (
    OrdenSerializer,
    OrdenListSerializer,
    CrearOrdenSerializer,
    CancelarOrdenSerializer,
)
from .services import crear_orden_desde_carrito


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
# VIEWSET DE ÓRDENES
# ==============================================================================
@extend_schema(parameters=[
    OpenApiParameter("id", OpenApiTypes.UUID, OpenApiParameter.PATH)
])
class OrdenViewSet(
    SerializerContextMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet de solo lectura para órdenes del usuario autenticado.
    La creación y cancelación se manejan como acciones separadas.

    Endpoints disponibles:
        GET    /api/ordenes/               - Listar mis órdenes (paginado)
        GET    /api/ordenes/{id}/          - Detalle de una orden
        POST   /api/ordenes/crear/         - Crear orden desde el carrito
        POST   /api/ordenes/{id}/cancelar/ - Cancelar una orden
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["fecha_creacion", "total", "estado"]
    ordering = ["-fecha_creacion"]

    def get_queryset(self):
        usuario = self.request.user
        queryset = Orden.objects.filter(
            usuario=usuario
        ).select_related("usuario")

        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                Prefetch(
                    "items",
                    queryset=ItemOrden.objects.select_related(
                        "variante__producto"
                    ).order_by("fecha_creacion")
                ),
                Prefetch(
                    "historial_estados",
                    queryset=HistorialEstadoOrden.objects.select_related(
                        "cambiado_por"
                    ).order_by("-fecha")
                ),
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return OrdenListSerializer
        if self.action == "crear":
            return CrearOrdenSerializer
        if self.action == "cancelar":
            return CancelarOrdenSerializer
        return OrdenSerializer

    def _obtener_orden_completa(self, orden_id):
        """
        Helper reutilizable que retorna una orden con
        todos sus ítems e historial prefetcheados.
        Evita duplicar el mismo prefetch en crear() y cancelar().
        """
        return (
            Orden.objects
            .filter(pk=orden_id)
            .select_related("usuario")
            .prefetch_related(
                Prefetch(
                    "items",
                    queryset=ItemOrden.objects.select_related(
                        "variante__producto"
                    ).order_by("fecha_creacion")
                ),
                Prefetch(
                    "historial_estados",
                    queryset=HistorialEstadoOrden.objects.select_related(
                        "cambiado_por"
                    ).order_by("-fecha")
                ),
            )
            .first()
        )

    # ------------------------------------------------------------------
    # ACCIÓN: CREAR ORDEN
    # ------------------------------------------------------------------

    @action(
        detail=False,
        methods=["post"],
        url_path="crear",
        url_name="crear"
    )
    def crear(self, request) -> Response:
        """
        Crea una orden desde el carrito activo del usuario.

        Si se envía codigo_cupon, se valida y se calcula el descuento
        ANTES de crear la orden, usando la misma lógica de negocio
        que el endpoint /api/cupones/validar/.

        Errores posibles:
            400 - CarritoVacio: el usuario no tiene items en el carrito.
            400 - StockInsuficiente: alguna variante no tiene stock suficiente.
            400 - CuponInvalido: el cupón no es aplicable.

        POST /api/ordenes/crear/
        Body (todos opcionales):
            {
                "costo_envio": 15000,
                "codigo_cupon": "DESCUENTO10",
                "notas": "Entregar después de las 18hs."
            }
        """
        

        serializer = CrearOrdenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        costo_envio = serializer.validated_data["costo_envio"]
        codigo_cupon = serializer.validated_data["codigo_cupon"]
        notas = serializer.validated_data["notas"]
        
        carrito = getattr(request.user, "carrito", None)
        monto_descuento = Decimal("0")
        cupon = None

        if codigo_cupon:
            if carrito is None or not carrito.items.exists():
                return Response(
                    {"detail": "El carrito no contiene productos."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            subtotal_actual = sum(
                item.subtotal for item in carrito.items.all()
            )

            try:
                cupon = Cupon.objects.get(codigo=codigo_cupon)
            except Cupon.DoesNotExist:
                return Response(
                    {"detail": f"El cupón '{codigo_cupon}' no existe."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                cupon.validar(usuario=request.user, subtotal=subtotal_actual)
            except CuponInvalido as exc:
                return Response(
                    {"detail": str(exc)},
                    status=status.HTTP_400_BAD_REQUEST
                )

            monto_descuento = cupon.calcular_descuento(subtotal_actual)

        # Esto se ejecuta SIEMPRE, haya o no cupón.
        try:
            orden = crear_orden_desde_carrito(
                usuario=request.user,
                costo_envio=costo_envio,
                monto_descuento=monto_descuento,
                codigo_cupon=codigo_cupon,
                notas=notas,
            )
        except CarritoVacio as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except StockInsuficiente as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Solo incrementamos el uso si efectivamente se usó un cupón válido.
        if cupon is not None:
            cupon.incrementar_uso()

        orden_completa = self._obtener_orden_completa(orden.pk)

        response_serializer = OrdenSerializer(
            orden_completa,
            context=self.get_serializer_context()
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )

    # ------------------------------------------------------------------
    # ACCIÓN: CANCELAR ORDEN
    # ------------------------------------------------------------------

    @action(
        detail=True,
        methods=["post"],
        url_path="cancelar",
        url_name="cancelar"
    )
    def cancelar(self, request, pk=None) -> Response:
        """
        Cancela una orden existente del usuario autenticado.

        POST /api/ordenes/{id}/cancelar/
        Body (opcional):
            {
                "comentario": "Me arrepentí de la compra."
            }
        """
        orden = self.get_object()

        serializer = CancelarOrdenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not orden.puede_cancelarse:
            return Response(
                {
                    "detail": (
                        f"No se puede cancelar una orden en estado "
                        f"'{orden.get_estado_display()}'. "
                        f"Solo se pueden cancelar órdenes pendientes o confirmadas."
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        try:
            orden.cancelar(
                usuario_accion=request.user,
                comentario=serializer.validated_data["comentario"]
            )
        except Exception as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        orden_actualizada = self._obtener_orden_completa(orden.pk)

        response_serializer = OrdenSerializer(
            orden_actualizada,
            context=self.get_serializer_context()
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    # ------------------------------------------------------------------
    # ACCIÓN: DESCARGAR FACTURA
    # ------------------------------------------------------------------

    @action(
        detail=True,
        methods=["get"],
        url_path="factura",
        url_name="factura"
    )
    def factura(self, request, pk=None) -> HttpResponse:
        """
        Genera y descarga el PDF de la factura legal de una orden.

        Solo disponible para órdenes que ya fueron confirmadas
        (no tiene sentido facturar una orden pendiente o cancelada).

        GET /api/ordenes/{id}/factura/
        Respuesta: application/pdf descargable.
        """
        try:
            orden = self.get_object()
        except Http404:
            return Response(
            {"detail": "La orden no existe o no te pertenece."},
            status=status.HTTP_404_NOT_FOUND
        )

        estados_facturables = ["confirmed", "processing", "shipped", "delivered"]
        if orden.estado not in estados_facturables:
            return Response(
                {
                    "detail": (
                        f"No se puede generar factura de una orden en estado "
                        f"'{orden.get_estado_display()}'."
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        orden_completa = self._obtener_orden_completa(orden.pk)
        buffer = generar_factura_pdf(orden_completa)
        nombre_archivo = f"factura_{orden_completa.numero_orden_display.replace('#', '')}.pdf"

        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
        return response