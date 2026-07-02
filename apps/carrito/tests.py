from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.productos.models import Categoria, Producto, Variante
from .models import Carrito, ItemCarrito

Usuario = get_user_model()


class CarritoTestMixin:
    """Crea datos reutilizables para pruebas de carrito."""

    def crear_datos_base(self):
        self.usuario = Usuario.objects.create_user(
            username="carrito_test",
            email="carrito_test@tienda.com",
            password="Password123!"
        )
        self.otro_usuario = Usuario.objects.create_user(
            username="otro_carrito_test",
            email="otro_carrito_test@tienda.com",
            password="Password123!"
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
        self.variante_sin_stock = Variante.objects.create(
            producto=self.producto,
            nombre="Talle 41",
            sku="CARRITO-TEST-002",
            inventario=0,
        )
        self.variante_inactiva = Variante.objects.create(
            producto=self.producto,
            nombre="Talle 42",
            sku="CARRITO-TEST-003",
            inventario=10,
            esta_activo=False,
        )


class CarritoModelTestCase(CarritoTestMixin, TestCase):
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
        self.crear_datos_base()
        self.carrito = Carrito.objects.create(usuario=self.usuario)

    def test_usuario_solo_puede_tener_un_carrito(self):
        """La relacion OneToOne impide crear un segundo carrito para el mismo usuario."""
        with self.assertRaises(IntegrityError):
            Carrito.objects.create(usuario=self.usuario)

    def test_agregar_item_nuevo_al_carrito(self):
        """Agregar una variante nueva crea un ItemCarrito correctamente."""
        item = self.carrito.agregar_o_actualizar_item(
            variante=self.variante,
            cantidad=2,
        )
        self.assertEqual(self.carrito.items.count(), 1)
        self.assertEqual(item.cantidad, 2)

    def test_agregar_misma_variante_suma_cantidades(self):
        """Agregar la misma variante actualiza cantidad y no duplica filas."""
        self.carrito.agregar_o_actualizar_item(self.variante, cantidad=2)
        item = self.carrito.agregar_o_actualizar_item(self.variante, cantidad=3)

        self.assertEqual(self.carrito.items.count(), 1)
        self.assertEqual(item.cantidad, 5)

    def test_no_se_permite_la_misma_variante_dos_veces(self):
        """La restriccion unica de carrito+variante impide duplicados."""
        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=1,
        )
        with self.assertRaises(IntegrityError):
            ItemCarrito.objects.create(
                carrito=self.carrito,
                variante=self.variante,
                cantidad=1,
            )

    def test_no_permite_agregar_mas_cantidad_que_stock(self):
        """El carrito no permite guardar mas unidades que el stock disponible."""
        with self.assertRaises(Exception):
            self.carrito.agregar_o_actualizar_item(
                variante=self.variante,
                cantidad=99,
            )

    def test_subtotal_del_item_se_calcula_correctamente(self):
        """El subtotal del item es precio_total de la variante x cantidad."""
        item = ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=3,
        )
        self.assertEqual(item.subtotal, Decimal("600000"))

    def test_vaciar_carrito_elimina_todos_los_items(self):
        """vaciar el carrito borra todos sus items asociados."""
        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=1,
        )
        self.assertEqual(self.carrito.items.count(), 1)

        self.carrito.vaciar()

        self.assertEqual(self.carrito.items.count(), 0)


class CarritoAPITestCase(CarritoTestMixin, APITestCase):
    """Pruebas de API para permisos y reglas de negocio del carrito."""

    def setUp(self):
        self.crear_datos_base()
        self.carrito_url = reverse("carrito-list")
        self.agregar_url = reverse("carrito-agregar")

    def test_usuario_no_autenticado_no_puede_ver_carrito(self):
        """El carrito exige autenticacion."""
        response = self.client.get(self.carrito_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_usuario_autenticado_obtiene_carrito(self):
        """La API crea y retorna el carrito del usuario autenticado."""
        self.client.force_authenticate(user=self.usuario)
        response = self.client.get(self.carrito_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cantidad_items"], 0)
        self.assertEqual(Carrito.objects.filter(usuario=self.usuario).count(), 1)

    def test_agregar_item_al_carrito(self):
        """La API permite agregar una variante disponible al carrito."""
        self.client.force_authenticate(user=self.usuario)
        response = self.client.post(
            self.agregar_url,
            {
                "variante_id": str(self.variante.id),
                "cantidad": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["cantidad"], 2)
        self.assertEqual(ItemCarrito.objects.count(), 1)

    def test_agregar_misma_variante_suma_cantidad(self):
        """Agregar dos veces la misma variante suma cantidad."""
        self.client.force_authenticate(user=self.usuario)
        self.client.post(
            self.agregar_url,
            {"variante_id": str(self.variante.id), "cantidad": 2},
            format="json",
        )
        response = self.client.post(
            self.agregar_url,
            {"variante_id": str(self.variante.id), "cantidad": 3},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["cantidad"], 5)
        self.assertEqual(ItemCarrito.objects.count(), 1)

    def test_no_permite_agregar_variante_inactiva(self):
        """La API rechaza variantes inactivas."""
        self.client.force_authenticate(user=self.usuario)
        response = self.client.post(
            self.agregar_url,
            {"variante_id": str(self.variante_inactiva.id), "cantidad": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_permite_superar_stock_acumulado(self):
        """La API valida stock considerando lo que el usuario ya tenia en carrito."""
        self.client.force_authenticate(user=self.usuario)
        self.client.post(
            self.agregar_url,
            {"variante_id": str(self.variante.id), "cantidad": 10},
            format="json",
        )
        response = self.client.post(
            self.agregar_url,
            {"variante_id": str(self.variante.id), "cantidad": 10},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_puede_modificar_item_de_otro_usuario(self):
        """Un usuario no puede modificar items de otro carrito."""
        carrito_otro = Carrito.objects.create(usuario=self.otro_usuario)
        item_otro = ItemCarrito.objects.create(
            carrito=carrito_otro,
            variante=self.variante,
            cantidad=1,
        )

        self.client.force_authenticate(user=self.usuario)
        response = self.client.patch(
            reverse("carrito-item-detail", args=[item_otro.id]),
            {"cantidad": 2},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_actualizar_cantidad_cero_elimina_item(self):
        """Actualizar cantidad a cero elimina el item del carrito."""
        carrito = Carrito.objects.create(usuario=self.usuario)
        item = ItemCarrito.objects.create(
            carrito=carrito,
            variante=self.variante,
            cantidad=2,
        )

        self.client.force_authenticate(user=self.usuario)
        response = self.client.patch(
            reverse("carrito-item-detail", args=[item.id]),
            {"cantidad": 0},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(ItemCarrito.objects.filter(id=item.id).exists())
