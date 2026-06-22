from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.productos.models import Categoria, Producto, Variante
from .models import Carrito, ItemCarrito

Usuario = get_user_model()


class CarritoModelTestCase(TestCase):
    """
    Suite de pruebas QA para el modulo de Carrito.

    Cubre:
        - Un usuario solo puede tener un carrito (OneToOne).
        - Agregar un item nuevo al carrito.
        - Agregar la misma variante dos veces suma cantidades, no duplica filas.
        - Restriccion unica de variante por carrito.
        - Calculo de subtotal por item.
        - Vaciar el carrito elimina todos sus items.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="carrito_test",
            email="carrito_test@tienda.com",
            password="Password123"
        )

        categoria = Categoria.objects.create(nombre="Calzado Carrito Test")
        self.producto = Producto.objects.create(
            nombre="Zapatillas Carrito Test",
            categoria=categoria,
            precio_base=Decimal("200000"),
        )
        self.variante = Variante.objects.create(
            producto=self.producto,
            nombre="Talle 40",
            sku="CARRITO-TEST-001",
            inventario=15,
        )

        self.carrito = Carrito.objects.create(usuario=self.usuario)

    def test_usuario_solo_puede_tener_un_carrito(self):
        """La relacion OneToOne impide crear un segundo carrito para el mismo usuario."""
        with self.assertRaises(Exception):
            Carrito.objects.create(usuario=self.usuario)

    def test_agregar_item_nuevo_al_carrito(self):
        """Agregar una variante nueva crea un ItemCarrito correctamente."""
        item = ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=2,
        )
        self.assertEqual(self.carrito.items.count(), 1)
        self.assertEqual(item.cantidad, 2)

    def test_no_se_permite_la_misma_variante_dos_veces(self):
        """
        La restriccion unica de carrito+variante impide crear dos filas
        de ItemCarrito para la misma variante en el mismo carrito.
        La logica de 'sumar cantidad' vive en el servicio de agregar,
        no en el modelo, pero el modelo debe impedir el duplicado.
        """
        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=1,
        )
        with self.assertRaises(Exception):
            ItemCarrito.objects.create(
                carrito=self.carrito,
                variante=self.variante,
                cantidad=1,
            )

    def test_subtotal_del_item_se_calcula_correctamente(self):
        """El subtotal del item es precio_total de la variante x cantidad."""
        item = ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=3,
        )
        # precio_total de la variante = 200000 (sin modificador ni descuento)
        self.assertEqual(item.subtotal, Decimal("600000"))

    def test_vaciar_carrito_elimina_todos_los_items(self):
        """vaciar el carrito borra todos sus items asociados."""
        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=1,
        )
        self.assertEqual(self.carrito.items.count(), 1)

        self.carrito.items.all().delete()

        self.assertEqual(self.carrito.items.count(), 0)