from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from apps.productos.models import Categoria, Producto, Variante
from apps.carrito.models import Carrito, ItemCarrito
from core.exceptions import CarritoVacio, StockInsuficiente
from .models import Orden, ItemOrden, HistorialEstadoOrden
from .services import crear_orden_desde_carrito
from rest_framework.test import APITestCase

Usuario = get_user_model()


class OrdenModelTestCase(TestCase):
    """
    Suite de pruebas QA para el modulo de Ordenes.

    Cubre:
        - Creacion de orden desde el carrito (camino feliz).
        - Validacion de stock insuficiente.
        - Validacion de carrito vacio.
        - Congelamiento de precios en ItemOrden.
        - Descuento correcto de stock al confirmar.
        - Cancelacion de orden y devolucion de stock.
        - Restriccion de estados para cancelar.
        - Registro en HistorialEstadoOrden.
    """

    def setUp(self):
        """Prepara usuario, categoria, producto, variante y carrito."""
        self.usuario = Usuario.objects.create_user(
            username="comprador_test",
            email="comprador_test@tienda.com",
            password="Password123"
        )

        self.categoria = Categoria.objects.create(nombre="Ropa de Prueba")

        self.producto = Producto.objects.create(
            nombre="Campera de Prueba",
            categoria=self.categoria,
            precio_base=Decimal("200000"),
            esta_activo=True
        )

        self.variante = Variante.objects.create(
            producto=self.producto,
            nombre="Talle M",
            sku="CAMPERA-TEST-M",
            inventario=10,
            stock_minimo=2
        )

        self.carrito = Carrito.objects.create(usuario=self.usuario)

    # ------------------------------------------------------------------
    # CREACION DESDE EL CARRITO
    # ------------------------------------------------------------------

    def test_crear_orden_desde_carrito_camino_feliz(self):
        """Crear una orden valida descuenta stock y limpia el carrito."""
        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=2
        )

        orden = crear_orden_desde_carrito(
            usuario=self.usuario,
            costo_envio=Decimal("10000"),
        )

        self.variante.refresh_from_db()

        self.assertEqual(orden.estado, Orden.Estado.CONFIRMED)
        self.assertEqual(orden.items.count(), 1)
        self.assertEqual(self.variante.inventario, 8)  # 10 - 2
        self.assertEqual(self.carrito.items.count(), 0)  # carrito limpiado
        self.assertEqual(orden.subtotal, Decimal("400000"))  # 200000 x 2
        self.assertEqual(orden.total, Decimal("410000"))  # + envio

    def test_crear_orden_con_carrito_vacio_lanza_excepcion(self):
        """No se puede crear una orden sin items en el carrito."""
        with self.assertRaises(CarritoVacio):
            crear_orden_desde_carrito(usuario=self.usuario)

    def test_crear_orden_con_stock_insuficiente_lanza_excepcion(self):
        """No se puede crear una orden si no hay stock suficiente."""
        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=999  # mas que el inventario disponible
        )

        with self.assertRaises(StockInsuficiente):
            crear_orden_desde_carrito(usuario=self.usuario)

        # El stock no debe haberse modificado tras el error
        self.variante.refresh_from_db()
        self.assertEqual(self.variante.inventario, 10)

    def test_orden_congela_el_precio_al_crear(self):
        """
        El precio del item queda congelado en el momento de la compra,
        sin importar si el producto cambia de precio despues.
        """
        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=1
        )

        orden = crear_orden_desde_carrito(usuario=self.usuario)
        item_orden = orden.items.first()
        precio_congelado = item_orden.precio_unitario

        # Cambiamos el precio del producto despues de la compra
        self.producto.precio_base = Decimal("999999")
        self.producto.save()

        item_orden.refresh_from_db()
        self.assertEqual(item_orden.precio_unitario, precio_congelado)
        self.assertNotEqual(item_orden.precio_unitario, Decimal("999999"))

    def test_orden_guarda_snapshot_de_nombres(self):
        """
        ItemOrden guarda el nombre del producto y variante en el
        momento de la compra, independiente de cambios futuros.
        """
        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=1
        )

        orden = crear_orden_desde_carrito(usuario=self.usuario)
        item_orden = orden.items.first()

        self.assertEqual(item_orden.nombre_producto, "Campera de Prueba")
        self.assertEqual(item_orden.nombre_variante, "Talle M")

    def test_orden_registra_historial_al_crearse(self):
        """Crear una orden genera una entrada en el historial de estados."""
        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=1
        )

        orden = crear_orden_desde_carrito(usuario=self.usuario)

        self.assertEqual(orden.historial_estados.count(), 1)
        historial = orden.historial_estados.first()
        self.assertEqual(historial.estado_nuevo, Orden.Estado.CONFIRMED)
        self.assertEqual(historial.cambiado_por, self.usuario)

    # ------------------------------------------------------------------
    # CANCELACION
    # ------------------------------------------------------------------

    def test_cancelar_orden_devuelve_stock(self):
        """Cancelar una orden confirmada devuelve el stock descontado."""
        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=3
        )
        orden = crear_orden_desde_carrito(usuario=self.usuario)

        self.variante.refresh_from_db()
        self.assertEqual(self.variante.inventario, 7)  # 10 - 3

        orden.cancelar(usuario_accion=self.usuario, comentario="Prueba de cancelacion")

        self.variante.refresh_from_db()
        orden.refresh_from_db()

        self.assertEqual(self.variante.inventario, 10)  # stock devuelto
        self.assertEqual(orden.estado, Orden.Estado.CANCELLED)

    def test_cancelar_orden_registra_historial(self):
        """Cancelar una orden agrega una nueva entrada al historial."""
        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=1
        )
        orden = crear_orden_desde_carrito(usuario=self.usuario)
        orden.cancelar(usuario_accion=self.usuario)

        self.assertEqual(orden.historial_estados.count(), 2)
        ultimo = orden.historial_estados.first()
        self.assertEqual(ultimo.estado_anterior, Orden.Estado.CONFIRMED)
        self.assertEqual(ultimo.estado_nuevo, Orden.Estado.CANCELLED)

    def test_no_se_puede_cancelar_orden_ya_cancelada(self):
        """Una orden ya cancelada no puede volver a cancelarse."""
        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=1
        )
        orden = crear_orden_desde_carrito(usuario=self.usuario)
        orden.cancelar(usuario_accion=self.usuario)

        with self.assertRaises(Exception):
            orden.cancelar(usuario_accion=self.usuario)

    # ------------------------------------------------------------------
    # PROPIEDADES Y CAMPOS CALCULADOS
    # ------------------------------------------------------------------

    def test_puede_cancelarse_segun_estado(self):
        """puede_cancelarse solo es True en pending o confirmed."""
        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=1
        )
        orden = crear_orden_desde_carrito(usuario=self.usuario)
        self.assertTrue(orden.puede_cancelarse)

        orden.cancelar(usuario_accion=self.usuario)
        self.assertFalse(orden.puede_cancelarse)

    def test_numero_orden_display_formato(self):
        """numero_orden_display retorna formato #XXXXXXXX en mayusculas."""
        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=1
        )
        orden = crear_orden_desde_carrito(usuario=self.usuario)

        self.assertTrue(orden.numero_orden_display.startswith("#"))
        self.assertEqual(len(orden.numero_orden_display), 9)  # "#" + 8 caracteres

class OrdenReglasNegocioTestCase(TestCase):
    """Pruebas de reglas de negocio adicionales para crear órdenes."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="orden_reglas",
            email="orden_reglas@tienda.com",
            password="Password123!"
        )
        self.categoria = Categoria.objects.create(nombre="Accesorios Orden")
        self.producto = Producto.objects.create(
            nombre="Auricular Orden",
            categoria=self.categoria,
            precio_base=Decimal("100000"),
            esta_activo=True,
        )
        self.variante = Variante.objects.create(
            producto=self.producto,
            nombre="Negro",
            sku="ORDEN-AURICULAR-NEGRO",
            inventario=5,
            stock_minimo=1,
            esta_activo=True,
        )
        self.carrito = Carrito.objects.create(usuario=self.usuario)

    def test_no_crea_orden_con_descuento_mayor_al_subtotal(self):
        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=1,
        )

        with self.assertRaises(ValueError):
            crear_orden_desde_carrito(
                usuario=self.usuario,
                monto_descuento=Decimal("999999"),
            )

        self.variante.refresh_from_db()
        self.assertEqual(self.variante.inventario, 5)
        self.assertEqual(Orden.objects.count(), 0)

    def test_no_crea_orden_con_variante_inactiva(self):
        self.variante.esta_activo = False
        self.variante.save(update_fields=["esta_activo"])

        ItemCarrito.objects.create(
            carrito=self.carrito,
            variante=self.variante,
            cantidad=1,
        )

        with self.assertRaises(ValueError):
            crear_orden_desde_carrito(usuario=self.usuario)

        self.assertEqual(Orden.objects.count(), 0)


class EstadisticasAdminAPITestCase(APITestCase):
    """
    Pruebas de acceso al endpoint de estadisticas administrativas.
    Cubre: acceso permitido a staff, denegado a cliente autenticado,
    y denegado a usuario anonimo.
    """

    def setUp(self):
        self.admin = Usuario.objects.create_user(
            username="admin_test",
            email="admin@correo.com",
            password="Password123!",
            is_staff=True,
        )

        self.cliente = Usuario.objects.create_user(
            username="cliente_test",
            email="cliente@correo.com",
            password="Password123!",
        )

        self.url = reverse("estadisticas-admin")

    def test_admin_puede_ver_estadisticas(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertIn("resumen", response.data)
        self.assertIn("ventas_por_mes", response.data)
        self.assertIn("productos_mas_vendidos", response.data)

    def test_cliente_no_puede_ver_estadisticas(self):
        self.client.force_authenticate(user=self.cliente)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_usuario_anonimo_no_puede_ver_estadisticas(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )