from rest_framework import status
from rest_framework.exceptions import APIException


class CarritoVacio(APIException):
    """Se lanza cuando el usuario intenta confirmar una compra con el carrito vacío."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "El carrito está vacío."
    default_code = "carrito_vacio"


class StockInsuficiente(APIException):
    """Se lanza cuando la cantidad solicitada supera el stock disponible."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "No hay suficiente stock disponible."
    default_code = "stock_insuficiente"

    def __init__(self, detail=None, code=None, producto=None, disponible=None):
        if detail is None and producto and disponible is not None:
            detail = f"No hay suficiente stock para '{producto}'. Disponible: {disponible}."
        super().__init__(detail, code)


class CuponInvalido(APIException):
    """Se lanza cuando el cupón no existe, está vencido o alcanzó su límite."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "El cupón ingresado no es válido."
    default_code = "cupon_invalido"


class PagoFallido(APIException):
    """Se lanza cuando la pasarela de pago rechaza la transacción."""
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "El pago no pudo ser procesado."
    default_code = "pago_fallido"

    def __init__(self, detail=None, code=None, razon=None):
        if detail is None and razon:
            detail = f"El pago no pudo ser procesado. Motivo: {razon}."
        super().__init__(detail, code)