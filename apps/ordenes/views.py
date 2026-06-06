from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Prefetch

from core.exceptions import CarritoVacio, StockInsuficiente
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
    Necesario para que campos como numero_orden_display funcionen
    correctamente en todos los endpoints.
    """
    def get_serializer_context(self) -> dict:
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


# ==============================================================================
# VIEWSET DE ÓRDENES
# ==============================================================================

class OrdenViewSet(
    SerializerContextMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet de solo lectura para órdenes del usuario autenticado.

    Un usuario solo puede ver sus propias órdenes.
    La creación y cancelación se manejan como acciones separadas
    para mantener semántica REST clara.

    Endpoints disponibles:
        GET    /api/ordenes/              - Listar mis órdenes (paginado)
        GET    /api/ordenes/{id}/         - Detalle de una orden
        POST   /api/ordenes/crear/        - Crear orden desde el carrito
        POST   /api/ordenes/{id}/cancelar/ - Cancelar una orden

    Seguridad:
        - Solo se retornan órdenes del usuario autenticado.
        - Un usuario nunca puede ver ni cancelar órdenes de otro usuario.
        - El filtro se aplica en get_queryset(), no en la vista individual,
          para que la seguridad sea consistente en todos los endpoints.

    Rendimiento:
        - get_queryset() aplica select_related y prefetch_related
          para evitar el problema N+1 en detalle y listado.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["fecha_creacion", "total", "estado"]
    ordering = ["-fecha_creacion"]

    def get_queryset(self):
        """
        Retorna únicamente las órdenes del usuario autenticado.

        Aplica prefetch optimizado según la acción:
        - list: solo datos base, sin ítems ni historial.
        - retrieve: carga completa con ítems, variantes y historial.

        El filtro por usuario se aplica siempre, sin excepciones,
        para prevenir acceso cruzado entre usuarios.
        """
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
        """
        Usa el serializer resumido para listados y el completo
        para detalle, creación y cancelación.
        """
        if self.action == "list":
            return OrdenListSerializer
        if self.action == "crear":
            return CrearOrdenSerializer
        if self.action == "cancelar":
            return CancelarOrdenSerializer
        return OrdenSerializer

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

        Flujo:
            1. Valida los parámetros del request (costo_envio, cupon, notas).
            2. Delega la lógica de negocio al servicio crear_orden_desde_carrito().
            3. Retorna la orden completa con todos sus ítems.

        Errores posibles:
            400 - CarritoVacio: el usuario no tiene items en el carrito.
            400 - StockInsuficiente: alguna variante no tiene stock suficiente.

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

        try:
            orden = crear_orden_desde_carrito(
                usuario=request.user,
                costo_envio=serializer.validated_data["costo_envio"],
                codigo_cupon=serializer.validated_data["codigo_cupon"],
                notas=serializer.validated_data["notas"],
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

        orden_completa = (
            Orden.objects
            .filter(pk=orden.pk)
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

        La seguridad se garantiza en dos capas:
            1. get_queryset() filtra por usuario, así que get_object()
               nunca retorna una orden de otro usuario (retorna 404).
            2. orden.puede_cancelarse verifica que el estado lo permita.

        Si la orden no puede cancelarse por su estado actual,
        retorna 409 Conflict con un mensaje descriptivo.

        Flujo al cancelar exitosamente:
            - El stock de cada variante se devuelve automáticamente.
            - Se registra la cancelación en el historial de estados.
            - Se retorna la orden actualizada con estado "cancelled".

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

        orden_actualizada = (
            Orden.objects
            .filter(pk=orden.pk)
            .select_related("usuario")
            .prefetch_related(
                Prefetch(
                    "historial_estados",
                    queryset=HistorialEstadoOrden.objects.select_related(
                        "cambiado_por"
                    ).order_by("-fecha")
                ),
                Prefetch(
                    "items",
                    queryset=ItemOrden.objects.select_related(
                        "variante__producto"
                    ).order_by("fecha_creacion")
                ),
            )
            .first()
        )

        response_serializer = OrdenSerializer(
            orden_actualizada,
            context=self.get_serializer_context()
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)
