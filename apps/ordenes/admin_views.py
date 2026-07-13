from django.contrib.auth import get_user_model
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncMonth
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ordenes.models import Orden, ItemOrden
from apps.pagos.models import Pago
from apps.productos.models import Producto, Variante


Usuario = get_user_model()


class EstadisticasAdminView(APIView):
    """
    Devuelve las estadísticas generales del e-commerce.

    Solo disponible para usuarios administradores.
    GET /api/admin/estadisticas/
    """

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        pagos_aprobados = Pago.objects.filter(
            estado=Pago.Estado.APPROVED
        )

        ventas_aprobadas = (
            pagos_aprobados.aggregate(total=Sum("monto"))["total"]
            or 0
        )

        resumen = {
            "ventas_aprobadas": ventas_aprobadas,
            "ordenes_totales": Orden.objects.count(),
            "pagos_totales": Pago.objects.count(),
            "pagos_aprobados": pagos_aprobados.count(),
            "pagos_pendientes": Pago.objects.filter(
                estado=Pago.Estado.PENDING
            ).count(),
            "usuarios_totales": Usuario.objects.count(),
            "productos_totales": Producto.objects.count(),
            "productos_activos": Producto.objects.filter(
                esta_activo=True
            ).count(),
        }

        ordenes_por_estado = list(
            Orden.objects.values("estado")
            .annotate(cantidad=Count("id"))
            .order_by("estado")
        )

        ventas_por_mes = list(
            pagos_aprobados.annotate(
                mes=TruncMonth("fecha_procesado")
            )
            .values("mes")
            .annotate(total=Sum("monto"))
            .order_by("mes")
        )

        ventas_por_mes = [
            {
                "mes": item["mes"].strftime("%Y-%m")
                if item["mes"]
                else "Sin fecha",
                "total": item["total"] or 0,
            }
            for item in ventas_por_mes
        ]

        # subtotal es una @property de ItemOrden (precio_unitario * cantidad
        # calculado en Python), no una columna real de la base. Para poder
        # sumarlo en SQL hay que reconstruir la misma expresión con F(),
        # envuelta en ExpressionWrapper para que Django sepa el tipo de
        # dato resultante (Decimal, igual que precio_unitario).
        expresion_subtotal = ExpressionWrapper(
            F("precio_unitario") * F("cantidad"),
            output_field=DecimalField(max_digits=14, decimal_places=0),
        )

        # El alias de la primera anotacion NO puede llamarse "cantidad"
        # (igual que el campo real): si se llamara asi, Django resuelve
        # el F("cantidad") de expresion_subtotal contra esa anotacion ya
        # agregada (Sum) en lugar del campo original, y explota con
        # "es un agregado" al intentar sumar un Sum dentro de otro Sum.
        productos_mas_vendidos_raw = list(
            ItemOrden.objects.values("nombre_producto")
            .annotate(
                unidades=Sum("cantidad"),
                ingresos=Sum(expresion_subtotal),
            )
            .order_by("-unidades")[:10]
        )

        productos_mas_vendidos = [
            {
                "nombre_producto": item["nombre_producto"],
                "cantidad": item["unidades"],
                "ingresos": item["ingresos"],
            }
            for item in productos_mas_vendidos_raw
        ]

        stock_bajo = list(
            Variante.objects.filter(
                esta_activo=True,
                inventario__lte=F("stock_minimo"),
            )
            .values(
                "id",
                "producto__nombre",
                "nombre",
                "inventario",
                "stock_minimo",
            )
            .order_by("inventario")[:10]
        )

        stock_bajo = [
            {
                "variante_id": item["id"],
                "producto": item["producto__nombre"],
                "variante": item["nombre"],
                "inventario": item["inventario"],
                "stock_minimo": item["stock_minimo"],
            }
            for item in stock_bajo
        ]

        return Response(
            {
                "resumen": resumen,
                "ordenes_por_estado": ordenes_por_estado,
                "ventas_por_mes": ventas_por_mes,
                "productos_mas_vendidos": productos_mas_vendidos,
                "stock_bajo": stock_bajo,
            }
        )