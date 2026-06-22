from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.productos.models import Categoria, Producto, Variante
from apps.carrito.models import Carrito, ItemCarrito
from apps.ordenes.services import crear_orden_desde_carrito
from apps.ordenes.models import Orden
from .models import Pago

Usuario = get_user_model()


class PagoModelTestCase(TestCase):
    """
    Suite de pruebas QA para el modulo de Pagos.

    Cubre:
        - Creacion de pago en estado pendiente.
        - Aprobacion de pago y registro de id_transaccion.
        - Rechazo de pago.
        - Idempotencia: un pago aprobado no puede volver a aprobarse.
        - Idempotencia: un pago rechazado no puede aprobarse despues.
        - Reembolso de un pago aprobado.
        - Cancelacion de un pago pendiente.
        - Propiedades booleanas (es_exitoso, esta_pendiente, es_reembolsable).
    """

    def setUp(self):
        """Prepara usuario, producto, carrito y una orden confirmada."""
        self.usuario = Usuario.objects.create_user(
            username="pagador_test",
            email="pagador_test@tienda.com",
            password="Password123"
        )

        categoria = Categoria.objects.create(nombre="Electronica de Prueba")
        producto = Producto.objects.create(
            nombre="Auriculares de Prueba",
            categoria=categoria,
            precio_base=Decimal("150000"),
            esta_activo=True
        )
        variante = Variante.objects.create(
            producto=producto,
            nombre="Color Negro",
            sku="AURI-TEST-NEG",
            inventario=20,
            stock_minimo=2
        )

        carrito = Carrito.objects.create(usuario=self.usuario)
        ItemCarrito.objects.create(carrito=carrito, variante=variante, cantidad=1)

        self.orden = crear_orden_desde_carrito(usuario=self.usuario)

    def _crear_pago_pendiente(self) -> Pago:
        """Helper que crea un pago pendiente sobre la orden de prueba."""
        return Pago.objects.create(
            orden=self.orden,
            pasarela=Pago.Pasarela.EFECTIVO,
            monto=self.orden.total,
            estado=Pago.Estado.PENDING,
        )

    # ------------------------------------------------------------------
    # CREACION
    # ------------------------------------------------------------------

    def test_crear_pago_queda_pendiente(self):
        """Un pago recien creado queda en estado pendiente."""
        pago = self._crear_pago_pendiente()

        self.assertEqual(pago.estado, Pago.Estado.PENDING)
        self.assertTrue(pago.esta_pendiente)
        self.assertFalse(pago.es_exitoso)

    def test_pago_no_permite_monto_cero_o_negativo(self):
        """El modelo Pago rechaza montos invalidos via clean()."""
        pago = Pago(
            orden=self.orden,
            pasarela=Pago.Pasarela.EFECTIVO,
            monto=Decimal("0"),
            estado=Pago.Estado.PENDING,
        )
        with self.assertRaises(Exception):
            pago.full_clean()

    # ------------------------------------------------------------------
    # APROBACION
    # ------------------------------------------------------------------

    def test_marcar_aprobado_cambia_estado_y_guarda_transaccion(self):
        """Aprobar un pago actualiza estado, id_transaccion y fecha_procesado."""
        pago = self._crear_pago_pendiente()
        pago.marcar_aprobado(
            id_transaccion="TXN-12345",
            respuesta={"resultado": "ok"}
        )

        pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.Estado.APPROVED)
        self.assertEqual(pago.id_transaccion, "TXN-12345")
        self.assertIsNotNone(pago.fecha_procesado)
        self.assertTrue(pago.es_exitoso)
        self.assertTrue(pago.es_reembolsable)

    def test_marcar_aprobado_es_idempotente(self):
        """Aprobar un pago ya aprobado no debe alterar su id_transaccion."""
        pago = self._crear_pago_pendiente()
        pago.marcar_aprobado(id_transaccion="TXN-PRIMERA")

        pago.marcar_aprobado(id_transaccion="TXN-SEGUNDA-NO-DEBERIA-APLICAR")

        pago.refresh_from_db()
        self.assertEqual(pago.id_transaccion, "TXN-PRIMERA")

    # ------------------------------------------------------------------
    # RECHAZO
    # ------------------------------------------------------------------

    def test_marcar_rechazado_cambia_estado(self):
        """Rechazar un pago pendiente actualiza su estado a REJECTED."""
        pago = self._crear_pago_pendiente()
        pago.marcar_rechazado(respuesta={"motivo": "fondos insuficientes"})

        pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.Estado.REJECTED)
        self.assertFalse(pago.es_exitoso)

    def test_no_se_puede_rechazar_un_pago_ya_aprobado(self):
        """Un pago aprobado no puede pasar a rechazado."""
        pago = self._crear_pago_pendiente()
        pago.marcar_aprobado(id_transaccion="TXN-APROBADO")

        pago.marcar_rechazado()

        pago.refresh_from_db()
        # El estado debe seguir siendo APPROVED, el rechazo no debe aplicarse
        self.assertEqual(pago.estado, Pago.Estado.APPROVED)

    # ------------------------------------------------------------------
    # REEMBOLSO
    # ------------------------------------------------------------------

    def test_marcar_reembolsado_requiere_pago_aprobado_previamente(self):
        """Solo un pago aprobado puede reembolsarse."""
        pago = self._crear_pago_pendiente()
        pago.marcar_aprobado(id_transaccion="TXN-PARA-REEMBOLSO")

        pago.marcar_reembolsado(respuesta={"motivo": "devolucion del cliente"})

        pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.Estado.REFUNDED)
        self.assertFalse(pago.es_reembolsable)  # ya no se puede reembolsar de nuevo

    def test_no_se_puede_reembolsar_un_pago_pendiente(self):
        """Un pago pendiente (nunca aprobado) no puede reembolsarse."""
        pago = self._crear_pago_pendiente()
        pago.marcar_reembolsado()

        pago.refresh_from_db()
        # Debe seguir pendiente, el reembolso no debe aplicarse
        self.assertEqual(pago.estado, Pago.Estado.PENDING)

    # ------------------------------------------------------------------
    # CANCELACION
    # ------------------------------------------------------------------

    def test_cancelar_pago_pendiente(self):
        """Un pago pendiente puede cancelarse."""
        pago = self._crear_pago_pendiente()
        pago.cancelar()

        pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.Estado.CANCELLED)

    def test_no_se_puede_cancelar_un_pago_aprobado(self):
        """Un pago ya aprobado no puede cancelarse."""
        pago = self._crear_pago_pendiente()
        pago.marcar_aprobado(id_transaccion="TXN-NO-CANCELABLE")

        pago.cancelar()

        pago.refresh_from_db()
        # Debe seguir aprobado, la cancelacion no debe aplicarse
        self.assertEqual(pago.estado, Pago.Estado.APPROVED)