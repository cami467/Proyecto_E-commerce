from decimal import Decimal
from typing import TYPE_CHECKING

from core.exceptions import CarritoVacio
from .models import Orden

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


def crear_orden_desde_carrito(
    usuario: "AbstractUser",
    *,
    costo_envio: Decimal = Decimal("0.00"),
    monto_descuento: Decimal = Decimal("0.00"),
    codigo_cupon: str = "",
    notas: str = "",
) -> Orden:
    """
    Servicio de aplicacion para crear una orden desde el carrito
    de un usuario.

    Responsabilidades:
        - Verificar que el usuario tenga un carrito asociado.
        - Delegar toda la logica de negocio al metodo
          Orden.crear_desde_carrito().

    La logica de negocio (validacion de stock, creacion de items,
    calculo de totales, historial y limpieza del carrito) permanece
    centralizada en el modelo Orden.

    Args:
        usuario: Usuario propietario del carrito.
        costo_envio: Monto del costo de envio en Guaranies.
        monto_descuento: Monto total de descuento aplicado en Guaranies.
        codigo_cupon: Codigo de cupon utilizado.
        notas: Observaciones adicionales de la orden.

    Raises:
        CarritoVacio:
            Si el usuario no posee un carrito asociado.

    Returns:
        Orden: Instancia de la orden creada y confirmada.
    """
    carrito = getattr(usuario, "carrito", None)

    if carrito is None:
        raise CarritoVacio(
            "No se puede crear la orden porque el usuario no tiene un carrito."
        )

    return Orden.crear_desde_carrito(
        carrito=carrito,
        usuario_accion=usuario,
        costo_envio=costo_envio,
        monto_descuento=monto_descuento,
        codigo_cupon=codigo_cupon,
        notas=notas,
    )