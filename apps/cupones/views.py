from decimal import Decimal
from django.db import models
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

    Endpoints públicos (usuarios autenticados):
        GET  /api/cupones/                    - Listar cupones vigentes
        GET  /api/cupones/{codigo}/           - Detalle de un cupón
        POST /api/cupones/validar/            - Validar y calcular descuento

    Endpoints de administración (solo staff):
        GET  /api/cupones/admin/              - Listar todos los cupones

    Seguridad:
        - Usuarios normales solo ven cupones vigentes y activos.
        - Solo admins ven cupones vencidos o inactivos.
        - La validación verifica que el cupón sea aplicable
          para el usuario y subtotal específicos.

    Rendimiento:
        lookup_field = "codigo" permite buscar por código
        directamente sin necesitar el UUID.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["^codigo", "descripcion"]
    ordering_fields = ["fecha_vencimiento", "fecha_creacion"]
    ordering = ["-fecha_creacion"]
    lookup_field = "codigo"

    def get_queryset(self):
        from django.utils import timezone
        from django.db.models import Q
        """
        Usuarios normales ven solo cupones vigentes y activos.
        Admins ven todos los cupones sin filtro.
        """
        if self.request.user.is_staff:
            return Cupon.objects.all()

        ahora = timezone.now()
        return Cupon.objects.filter(
            esta_activo=True,
            fecha_inicio__lte=ahora,
        ).filter(
            Q(fecha_vencimiento__isnull=True) |
            Q(fecha_vencimiento__gte=ahora)
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

        Permite que el frontend muestre el descuento en tiempo real
        antes de que el usuario confirme la compra.

        POST /api/cupones/validar/
        Body:
            {
                "codigo": "DESCUENTO10",
                "subtotal": 500000
            }

        Response exitosa:
            {
                "codigo": "DESCUENTO10",
                "tipo": "porcentaje",
                "tipo_display": "Porcentaje (%)",
                "valor": "10.00",
                "subtotal_original": 500000,
                "monto_descuento": 50000,
                "total_con_descuento": 450000,
                "mensaje": "Cupón aplicado exitosamente."
            }
        """
        serializer = ValidarCuponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        codigo = serializer.validated_data["codigo"]
        subtotal = serializer.validated_data["subtotal"]

        # Buscar el cupón
        try:
            cupon = Cupon.objects.get(codigo=codigo)
        except Cupon.DoesNotExist:
            return Response(
                {"detail": f"El cupón '{codigo}' no existe."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validar que el cupón sea aplicable
        try:
            cupon.validar(
                usuario=request.user,
                subtotal=subtotal
            )
        except CuponInvalido as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calcular el descuento
        monto_descuento = cupon.calcular_descuento(subtotal)
        total_con_descuento = subtotal - monto_descuento

        respuesta = CuponAplicadoSerializer({
            "codigo": cupon.codigo,
            "tipo": cupon.tipo,
            "tipo_display": cupon.get_tipo_display(),
            "valor": cupon.valor,
            "subtotal_original": (subtotal),
            "monto_descuento": (monto_descuento),
            "total_con_descuento": (total_con_descuento),
            "mensaje": "Cupón aplicado exitosamente. ¡Aprovechá tu descuento!",
        })

        return Response(respuesta.data, status=status.HTTP_200_OK)