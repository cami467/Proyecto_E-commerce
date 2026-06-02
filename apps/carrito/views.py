from rest_framework import status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Carrito, ItemCarrito
from .serializers import (
    AgregarItemSerializer,
    ActualizarCantidadSerializer,
    CarritoSerializer,
    ItemCarritoSerializer,
)
from core.exceptions import StockInsuficiente
from apps.productos.models import Variante


# ==============================================================================
# VIEWSET DEL CARRITO
# ==============================================================================

class CarritoViewSet(viewsets.GenericViewSet):
    """
    ViewSet del carrito de compras.
    Cada usuario tiene un unico carrito que se crea automaticamente.

    GET    /api/carrito/           - Ver el carrito actual
    POST   /api/carrito/agregar/   - Agregar item al carrito
    DELETE /api/carrito/vaciar/    - Vaciar el carrito completo
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CarritoSerializer

    def get_carrito(self):
        """
        Obtiene o crea el carrito del usuario autenticado.
        Optimizado con prefetch para evitar N+1.
        """
        carrito, _ = Carrito.objects.prefetch_related(
            "items__variante__producto"
        ).get_or_create(usuario=self.request.user)
        return carrito

    def list(self, request):
        """
        Retorna el carrito del usuario con todos sus items.
        GET /api/carrito/
        """
        carrito = self.get_carrito()
        serializer = CarritoSerializer(
            carrito,
            context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="agregar")
    def agregar(self, request):
        """
        Agrega una variante al carrito o incrementa su cantidad.
        POST /api/carrito/agregar/
        """
        serializer = AgregarItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        variante_id = serializer.validated_data["variante_id"]
        cantidad = serializer.validated_data["cantidad"]

        try:
            variante = Variante.objects.get(
                id=variante_id,
                esta_activo=True
            )
        except Variante.DoesNotExist:
            return Response(
                {"detail": "La variante no existe o no esta disponible."},
                status=status.HTTP_404_NOT_FOUND
            )

        carrito = self.get_carrito()

        try:
            item = carrito.agregar_o_actualizar_item(variante, cantidad)
        except StockInsuficiente as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        item_serializer = ItemCarritoSerializer(
            item,
            context={"request": request}
        )
        return Response(
            item_serializer.data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=["delete"], url_path="vaciar")
    def vaciar(self, request):
        """
        Vacia completamente el carrito del usuario.
        DELETE /api/carrito/vaciar/
        """
        carrito = self.get_carrito()
        carrito.vaciar()
        return Response(
            {"mensaje": "Carrito vaciado exitosamente."},
            status=status.HTTP_200_OK
        )


# ==============================================================================
# VIEWSET DE ITEMS DEL CARRITO
# ==============================================================================

class ItemCarritoViewSet(
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet
):
    """
    ViewSet para gestionar items individuales del carrito.

    PATCH  /api/carrito/items/{id}/            - Actualizar cantidad
    DELETE /api/carrito/items/{id}/            - Eliminar item
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ActualizarCantidadSerializer

    def get_queryset(self):
        """
        Solo retorna items del carrito del usuario autenticado.
        Seguridad: nadie puede modificar items de otro usuario.
        """
        return ItemCarrito.objects.filter(
            carrito__usuario=self.request.user,
            esta_activo=True
        ).select_related("variante__producto")

    def partial_update(self, request, *args, **kwargs):
        """
        Actualiza la cantidad de un item del carrito.
        Si la cantidad es 0 el item se elimina automaticamente.
        PATCH /api/carrito/items/{id}/
        """
        item = self.get_object()
        serializer = ActualizarCantidadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        nueva_cantidad = serializer.validated_data["cantidad"]

        try:
            item.actualizar_cantidad(nueva_cantidad)
        except StockInsuficiente as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        if nueva_cantidad == 0:
            return Response(
                {"mensaje": "Item eliminado del carrito."},
                status=status.HTTP_200_OK
            )

        item_serializer = ItemCarritoSerializer(
            item,
            context={"request": request}
        )
        return Response(item_serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        Elimina un item del carrito.
        DELETE /api/carrito/items/{id}/
        """
        item = self.get_object()
        item.delete()
        return Response(
            {"mensaje": "Item eliminado del carrito."},
            status=status.HTTP_200_OK
        )