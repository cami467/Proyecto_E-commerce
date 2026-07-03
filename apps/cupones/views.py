from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.exceptions import CuponInvalido
from .models import Cupon
from .serializers import (
    CuponSerializer,
    CuponListSerializer,
    ValidarCuponSerializer,
    CuponAplicadoSerializer,
)


# ==============================================================================
# VIEWSET DE CUPONES
# ==============================================================================

class CuponViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet de cupones.

    Endpoints para usuarios autenticados:
        GET  /api/cupones/          - Listar cupones vigentes disponibles
        GET  /api/cupones/{codigo}/ - Detalle de un cupón disponible
        POST /api/cupones/validar/  - Validar y calcular descuento

    Seguridad:
        - Usuarios normales solo ven cupones activos, vigentes y disponibles.
        - Cupones restringidos solo aparecen al usuario asignado.
        - Staff puede ver todos los cupones.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["^codigo", "descripcion"]
    ordering_fields = ["fecha_vencimiento", "fecha_creacion"]
    ordering = ["-fecha_creacion"]
    lookup_field = "codigo"

    def get_queryset(self):
        """
        Retorna solo cupones visibles para el usuario autenticado.
        """
        queryset = Cupon.objects.prefetch_related("usuarios_permitidos")

        if self.request.user.is_staff:
            return queryset

        ahora = timezone.now()
        return (
            queryset
            .filter(
                esta_activo=True,
                fecha_inicio__lte=ahora,
            )
            .filter(
                Q(fecha_vencimiento__isnull=True) |
                Q(fecha_vencimiento__gte=ahora)
            )
            .filter(
                Q(usuarios_permitidos__isnull=True) |
                Q(usuarios_permitidos=self.request.user)
            )
            .distinct()
        )

    def get_serializer_class(self):
        if self.action == "list":
            return CuponListSerializer
        if self.action == "validar":
            return ValidarCuponSerializer
        return CuponSerializer

    # ------------------------------------------------------------------
    # ACCIÓN: VALIDAR CUPÓN
    # ------------------------------------------------------------------

    @action(
        detail=False,
        methods=["post"],
        url_path="validar",
        url_name="validar"
    )
    def validar(self, request) -> Response:
        """
        Valida un cupón y calcula el descuento para una orden.
        """
        serializer = ValidarCuponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        codigo = serializer.validated_data["codigo"]
        subtotal = serializer.validated_data["subtotal"]

        try:
            cupon = Cupon.objects.prefetch_related("usuarios_permitidos").get(codigo=codigo)
        except Cupon.DoesNotExist:
            return Response(
                {"detail": "El cupón ingresado no es válido."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            cupon.validar(usuario=request.user, subtotal=subtotal)
        except CuponInvalido as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        monto_descuento = cupon.calcular_descuento(subtotal)
        total_con_descuento = subtotal - monto_descuento

        respuesta = CuponAplicadoSerializer({
            "codigo": cupon.codigo,
            "tipo": cupon.tipo,
            "tipo_display": cupon.get_tipo_display(),
            "valor": cupon.valor,
            "subtotal_original": subtotal,
            "monto_descuento": monto_descuento,
            "total_con_descuento": total_con_descuento,
            "mensaje": "Cupón aplicado exitosamente. ¡Aprovechá tu descuento!",
        })

        return Response(respuesta.data, status=status.HTTP_200_OK)
