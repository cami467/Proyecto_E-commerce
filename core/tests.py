from django.test import TestCase

from core.numeros_en_letras import numero_a_letras


class NumeroALetrasTestCase(TestCase):
    """
    Suite de pruebas QA para el conversor de numeros a letras.

    Cubre:
        - Caso cero.
        - Unidades simples (1-9).
        - Casos especiales del 10 al 20.
        - Veintitantos (21-29).
        - Decenas con "Y" (31, 45, 99).
        - Centenas, incluyendo el caso especial 100 = "CIEN".
        - Miles (1000, casos especiales de "UN MIL" vs "DOS MIL").
        - Millones (1000000, "UN MILLON" vs "DOS MILLONES").
        - Numeros combinados grandes (el caso real de la factura: 1026000).
        - La regla gramatical UN vs UNO al final del numero.
    """

    def test_cero(self):
        self.assertEqual(numero_a_letras(0), "CERO")

    def test_unidades_simples(self):
        self.assertEqual(numero_a_letras(1), "UNO")
        self.assertEqual(numero_a_letras(5), "CINCO")
        self.assertEqual(numero_a_letras(9), "NUEVE")

    def test_casos_especiales_diez_a_veinte(self):
        self.assertEqual(numero_a_letras(10), "DIEZ")
        self.assertEqual(numero_a_letras(11), "ONCE")
        self.assertEqual(numero_a_letras(15), "QUINCE")
        self.assertEqual(numero_a_letras(19), "DIECINUEVE")
        self.assertEqual(numero_a_letras(20), "VEINTE")

    def test_veintitantos(self):
        self.assertEqual(numero_a_letras(21), "VEINTIUNO")
        self.assertEqual(numero_a_letras(25), "VEINTICINCO")
        self.assertEqual(numero_a_letras(29), "VEINTINUEVE")

    def test_decenas_con_y(self):
        self.assertEqual(numero_a_letras(31), "TREINTA Y UNO")
        self.assertEqual(numero_a_letras(45), "CUARENTA Y CINCO")
        self.assertEqual(numero_a_letras(99), "NOVENTA Y NUEVE")

    def test_decenas_exactas_sin_y(self):
        self.assertEqual(numero_a_letras(30), "TREINTA")
        self.assertEqual(numero_a_letras(80), "OCHENTA")

    def test_centena_especial_cien(self):
        """100 es CIEN, no CIENTO."""
        self.assertEqual(numero_a_letras(100), "CIEN")

    def test_centenas_compuestas(self):
        self.assertEqual(numero_a_letras(101), "CIENTO UNO")
        self.assertEqual(numero_a_letras(200), "DOSCIENTOS")
        self.assertEqual(numero_a_letras(345), "TRESCIENTOS CUARENTA Y CINCO")

    def test_mil_exacto(self):
        """1000 es MIL (no se dice 'un mil' en español, a diferencia de 'un millon')."""
        self.assertEqual(numero_a_letras(1000), "MIL")

    def test_miles_compuestos(self):
        self.assertEqual(numero_a_letras(2000), "DOS MIL")
        self.assertEqual(numero_a_letras(1500), "MIL QUINIENTOS")
        self.assertEqual(numero_a_letras(15000), "QUINCE MIL")

    def test_millon_exacto(self):
        """1000000 es UN MILLON, no UNO MILLON."""
        self.assertEqual(numero_a_letras(1_000_000), "UN MILLON")

    def test_millones_compuestos(self):
        self.assertEqual(numero_a_letras(2_000_000), "DOS MILLONES")

    def test_caso_real_factura_un_millon_veintiseis_mil(self):
        """Caso real visto en la factura de UniNorte: 1.026.000."""
        self.assertEqual(numero_a_letras(1_026_000), "UN MILLON VEINTISEIS MIL")

    def test_caso_real_factura_un_millon_doscientos_treinta_mil(self):
        """Caso real de nuestra propia factura de prueba: 1.230.000."""
        self.assertEqual(numero_a_letras(1_230_000), "UN MILLON DOSCIENTOS TREINTA MIL")

    def test_regla_gramatical_un_vs_uno_al_final(self):
        """
        En español, 'mil' nunca lleva 'UN' adelante (se dice 'mil', no
        'un mil'), pero 'millon' si lo requiere ('un millon', nunca
        solo 'millon'). UNO se usa cuando el numero termina solo en
        UN sin nada despues (21, 31, 101).
        """
        self.assertEqual(numero_a_letras(21), "VEINTIUNO")
        self.assertEqual(numero_a_letras(31), "TREINTA Y UNO")
        self.assertEqual(numero_a_letras(101), "CIENTO UNO")
        # Estos no deben verse afectados por el ajuste UN->UNO
        self.assertEqual(numero_a_letras(1000), "MIL")
        self.assertEqual(numero_a_letras(1_000_000), "UN MILLON")

    def test_numero_con_millones_miles_y_centenas_combinados(self):
        """Caso combinado complejo: 3.456.789."""
        resultado = numero_a_letras(3_456_789)
        self.assertIn("TRES MILLONES", resultado)
        self.assertIn("CUATROCIENTOS CINCUENTA Y SEIS MIL", resultado)
        self.assertIn("SETECIENTOS OCHENTA Y NUEVE", resultado)

    def test_acepta_string_numerico(self):
        """numero_a_letras debe poder recibir un Decimal o string convertible a int."""
        self.assertEqual(numero_a_letras("500"), "QUINIENTOS")