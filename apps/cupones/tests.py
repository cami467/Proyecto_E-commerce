from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.exceptions import CuponInvalido
from .models import Cupon

Usuario = get_user_model()


class CuponModelTestCase(TestCase):
    """
    Suite de pruebas QA para el modulo de Cupones.

    Cubre:
        - Calculo de descuento por porcentaje y por monto fijo.
        - El descuento nunca supera el subtotal de la orden.
        - Validacion de cupon inactivo.
        - Validacion de cupon vencido.
        - Validacion de cupon que aun no inicia su vigencia.
        - Validacion de limite de usos alcanzado.
        - Validacion de monto minimo no alcanzado.
        - Cupon restringido a usuarios especificos.
        - Incremento de usos_actuales.
        - Normalizacion del codigo a mayusculas.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="cliente_cupon_test",
            email="cliente_cupon_test@tienda.com",
            password="Password123"
        )
        self.ahora = timezone.now()

    def _crear_cupon(self, **overrides) -> Cupon:
        """Helper para crear un cupon con valores por defecto razonables."""
        defaults = {
            "codigo": "test10",
            "tipo": Cupon.TipoDescuento.PORCENTAJE,
            "valor": Decimal("10"),
            "monto_minimo": Decimal("0"),
            "limite_usos": 100,
            "fecha_inicio": self.ahora - timedelta(days=1),
            "fecha_vencimiento": self.ahora + timedelta(days=30),
            "esta_activo": True,
        }
        defaults.update(overrides)
        return Cupon.objects.create(**defaults)

    # ------------------------------------------------------------------
    # NORMALIZACION
    # ------------------------------------------------------------------

    def test_codigo_se_normaliza_a_mayusculas(self):
        """El codigo del cupon se guarda siempre en mayusculas."""
        cupon = self._crear_cupon(codigo="descuento10")
        self.assertEqual(cupon.codigo, "DESCUENTO10")

    # ------------------------------------------------------------------
    # CALCULO DE DESCUENTO
    # ------------------------------------------------------------------

    def test_calcular_descuento_porcentaje(self):
        """Un cupon de 10% sobre 100000 descuenta 10000."""
        cupon = self._crear_cupon(tipo=Cupon.TipoDescuento.PORCENTAJE, valor=Decimal("10"))
        descuento = cupon.calcular_descuento(Decimal("100000"))
        self.assertEqual(descuento, Decimal("10000"))

    def test_calcular_descuento_monto_fijo(self):
        """Un cupon de monto fijo descuenta exactamente ese valor."""
        cupon = self._crear_cupon(tipo=Cupon.TipoDescuento.MONTO_FIJO, valor=Decimal("25000"))
        descuento = cupon.calcular_descuento(Decimal("100000"))
        self.assertEqual(descuento, Decimal("25000"))

    def test_descuento_nunca_supera_el_subtotal(self):
        """Un cupon de monto fijo mayor al subtotal nunca lo supera."""
        cupon = self._crear_cupon(tipo=Cupon.TipoDescuento.MONTO_FIJO, valor=Decimal("999999"))
        descuento = cupon.calcular_descuento(Decimal("50000"))
        self.assertEqual(descuento, Decimal("50000"))

    # ------------------------------------------------------------------
    # VALIDACIONES DE ESTADO
    # ------------------------------------------------------------------

    def test_cupon_inactivo_lanza_excepcion(self):
        """Un cupon con esta_activo=False no puede usarse."""
        cupon = self._crear_cupon(esta_activo=False)
        with self.assertRaises(CuponInvalido):
            cupon.validar(usuario=self.usuario, subtotal=Decimal("100000"))

    def test_cupon_vencido_lanza_excepcion(self):
        """Un cupon cuya fecha_vencimiento ya paso no puede usarse."""
        cupon = self._crear_cupon(
            fecha_inicio=self.ahora - timedelta(days=60),
            fecha_vencimiento=self.ahora - timedelta(days=1),
        )
        with self.assertRaises(CuponInvalido):
            cupon.validar(usuario=self.usuario, subtotal=Decimal("100000"))

    def test_cupon_que_aun_no_inicia_lanza_excepcion(self):
        """Un cupon cuya fecha_inicio es futura no puede usarse todavia."""
        cupon = self._crear_cupon(
            fecha_inicio=self.ahora + timedelta(days=5),
            fecha_vencimiento=self.ahora + timedelta(days=30),
        )
        with self.assertRaises(CuponInvalido):
            cupon.validar(usuario=self.usuario, subtotal=Decimal("100000"))

    def test_cupon_sin_fecha_vencimiento_es_vigente(self):
        """Un cupon sin fecha_vencimiento (None) nunca vence."""
        cupon = self._crear_cupon(fecha_vencimiento=None)
        self.assertTrue(cupon.esta_vigente)

    # ------------------------------------------------------------------
    # LIMITE DE USOS
    # ------------------------------------------------------------------

    def test_cupon_sin_usos_disponibles_lanza_excepcion(self):
        """Un cupon que alcanzo su limite_usos no puede usarse de nuevo."""
        cupon = self._crear_cupon(limite_usos=1, usos_actuales=1)
        with self.assertRaises(CuponInvalido):
            cupon.validar(usuario=self.usuario, subtotal=Decimal("100000"))

    def test_cupon_sin_limite_usos_siempre_tiene_usos_disponibles(self):
        """Un cupon con limite_usos=None nunca se agota."""
        cupon = self._crear_cupon(limite_usos=None, usos_actuales=9999)
        self.assertTrue(cupon.tiene_usos_disponibles)

    def test_incrementar_uso_aumenta_el_contador(self):
        """incrementar_uso() suma 1 a usos_actuales y persiste el cambio."""
        cupon = self._crear_cupon(usos_actuales=5)
        cupon.incrementar_uso()

        cupon.refresh_from_db()
        self.assertEqual(cupon.usos_actuales, 6)

    def test_usos_restantes_calcula_correctamente(self):
        """usos_restantes retorna limite_usos menos usos_actuales."""
        cupon = self._crear_cupon(limite_usos=10, usos_actuales=3)
        self.assertEqual(cupon.usos_restantes, 7)

    # ------------------------------------------------------------------
    # MONTO MINIMO
    # ------------------------------------------------------------------

    def test_subtotal_menor_al_minimo_lanza_excepcion(self):
        """Si el subtotal no alcanza el monto_minimo, el cupon es invalido."""
        cupon = self._crear_cupon(monto_minimo=Decimal("200000"))
        with self.assertRaises(CuponInvalido):
            cupon.validar(usuario=self.usuario, subtotal=Decimal("100000"))

    def test_subtotal_igual_al_minimo_es_valido(self):
        """Si el subtotal es exactamente el monto_minimo, el cupon es valido."""
        cupon = self._crear_cupon(monto_minimo=Decimal("100000"))
        # No debe lanzar excepcion
        cupon.validar(usuario=self.usuario, subtotal=Decimal("100000"))

    # ------------------------------------------------------------------
    # RESTRICCION POR USUARIO
    # ------------------------------------------------------------------

    def test_cupon_restringido_a_otro_usuario_lanza_excepcion(self):
        """Un cupon con usuarios_permitidos no puede usarlo otro usuario."""
        otro_usuario = Usuario.objects.create_user(
            username="otro_usuario_cupon",
            email="otro_usuario_cupon@tienda.com",
            password="Password123"
        )
        cupon = self._crear_cupon()
        cupon.usuarios_permitidos.add(otro_usuario)

        with self.assertRaises(CuponInvalido):
            cupon.validar(usuario=self.usuario, subtotal=Decimal("100000"))

    def test_cupon_restringido_permite_al_usuario_correcto(self):
        """El usuario incluido en usuarios_permitidos si puede usar el cupon."""
        cupon = self._crear_cupon()
        cupon.usuarios_permitidos.add(self.usuario)

        # No debe lanzar excepcion
        cupon.validar(usuario=self.usuario, subtotal=Decimal("100000"))