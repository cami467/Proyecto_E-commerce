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

VEINTITANTOS = {
    21: "VEINTIUNO", 22: "VEINTIDOS", 23: "VEINTITRES",
    24: "VEINTICUATRO", 25: "VEINTICINCO", 26: "VEINTISEIS",
    27: "VEINTISIETE", 28: "VEINTIOCHO", 29: "VEINTINUEVE",
}

def _convertir_decenas(numero: int) -> str:
    """
    Convierte un numero de 0 a 99 a letras.

    """
    if numero in DECENAS_ESPECIALES:
        return DECENAS_ESPECIALES[numero]
    if numero in VEINTITANTOS:
        return VEINTITANTOS[numero]
    if numero < 10:
        return UNIDADES[numero]
    decena, unidad = divmod(numero, 10)
    if unidad == 0:
        return DECENAS[decena]
    texto_unidad = "UNO" if unidad == 1 else UNIDADES[unidad]
    return f"{DECENAS[decena]} Y {texto_unidad}"


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

    Regla gramatical "UN" vs "UNO":
        "UN" se usa correctamente solo cuando precede a un
        sustantivo (UN MIL, UN MILLON). Si el numero completo
        termina exactamente en la palabra "UN" sin nada despues
        (ej: 1, 21, 31, 101), la palabra correcta es "UNO". Por
        eso se aplica un ajuste final sobre el resultado completo
        en lugar de tratar de resolverlo en cada sub-funcion, ya
        que "UN" dentro de "UN MIL" o "UN MILLON" no debe tocarse.

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

    resultado = " ".join(partes).strip()

    # Ajuste final: si el resultado termina en la palabra "UN" sola
    # (no seguida de MIL/MILLON, que ya se generan correctos arriba),
    # se corrige a "UNO". Cubre los casos 1, 21, 31, 101, etc.
    if resultado.endswith(" UN"):
        resultado = resultado[: -len("UN")] + "UNO"
    elif resultado == "UN":
        resultado = "UNO"

    return resultado