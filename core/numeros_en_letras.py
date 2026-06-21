"""
Conversor de numeros enteros a su representacion en letras,
en español, orientado a montos en Guaranies para facturacion.

Ejemplo:
    numero_a_letras(1026000) -> "UN MILLON VEINTISEIS MIL"
"""

UNIDADES = [
    "", "UN", "DOS", "TRES", "CUATRO", "CINCO",
    "SEIS", "SIETE", "OCHO", "NUEVE",
]
DECENAS_ESPECIALES = {
    10: "DIEZ", 11: "ONCE", 12: "DOCE", 13: "TRECE", 14: "CATORCE",
    15: "QUINCE", 16: "DIECISEIS", 17: "DIECISIETE", 18: "DIECIOCHO",
    19: "DIECINUEVE", 20: "VEINTE",
}
DECENAS = [
    "", "", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA",
    "SESENTA", "SETENTA", "OCHENTA", "NOVENTA",
]
CENTENAS = [
    "", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS",
    "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS",
]


def _convertir_decenas(numero: int) -> str:
    """Convierte un numero de 0 a 99 a letras."""
    if numero <= 20:
        return DECENAS_ESPECIALES.get(numero, UNIDADES[numero])
    decena, unidad = divmod(numero, 10)
    if unidad == 0:
        return DECENAS[decena]
    return f"{DECENAS[decena]} Y {UNIDADES[unidad]}"


def _convertir_centenas(numero: int) -> str:
    """Convierte un numero de 0 a 999 a letras."""
    if numero == 100:
        return "CIEN"
    centena, resto = divmod(numero, 100)
    texto_centena = CENTENAS[centena]
    texto_resto = _convertir_decenas(resto) if resto else ""
    return " ".join(filter(None, [texto_centena, texto_resto]))


def _convertir_miles(numero: int) -> str:
    """Convierte un numero de 0 a 999.999 a letras."""
    miles, resto = divmod(numero, 1000)
    partes = []
    if miles:
        if miles == 1:
            partes.append("MIL")
        else:
            partes.append(f"{_convertir_centenas(miles)} MIL")
    if resto:
        partes.append(_convertir_centenas(resto))
    return " ".join(partes)


def numero_a_letras(numero: int) -> str:
    """
    Convierte un numero entero (hasta 999.999.999) a su
    representacion en letras, en mayusculas, en español.

    Pensado para montos en Guaranies, que no tienen decimales.

    Args:
        numero: monto entero a convertir.

    Returns:
        str: representacion en letras, ej "UN MILLON VEINTISEIS MIL".
        Retorna "CERO" si el numero es 0.
    """
    numero = int(numero)
    if numero == 0:
        return "CERO"

    millones, resto_millones = divmod(numero, 1_000_000)
    partes = []

    if millones:
        if millones == 1:
            partes.append("UN MILLON")
        else:
            partes.append(f"{_convertir_miles(millones)} MILLONES")

    if resto_millones:
        partes.append(_convertir_miles(resto_millones))

    return " ".join(partes).strip()