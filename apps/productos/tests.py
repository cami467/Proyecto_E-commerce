from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from core.exceptions import StockInsuficiente
from .models import Categoria, Producto, Variante


class CategoriaModelTestCase(TestCase):
    """
    Suite de pruebas QA para Categoria.

    Cubre:
        - Generacion automatica de slug.
        - Prevencion de ciclos en la jerarquia de categorias.
        - Restriccion unica de nombre por categoria padre.
    """

    def test_slug_se_genera_automaticamente(self):
        """Si no se especifica slug, se genera a partir del nombre."""
        categoria = Categoria.objects.create(nombre="Calzado Deportivo")
        self.assertEqual(categoria.slug, "calzado-deportivo")

    def test_categoria_no_puede_ser_su_propio_padre(self):
        """clean() rechaza que una categoria sea padre de si misma."""
        categoria = Categoria.objects.create(nombre="Ropa")
        categoria.categoria_padre = categoria
        with self.assertRaises(ValidationError):
            categoria.clean()

    def test_detecta_ciclo_en_jerarquia(self):
        """clean() detecta ciclos indirectos en la jerarquia de categorias."""
        abuela = Categoria.objects.create(nombre="Indumentaria")
        madre = Categoria.objects.create(nombre="Camisetas", categoria_padre=abuela)
        hija = Categoria.objects.create(nombre="Deportivas", categoria_padre=madre)

        # Intentamos crear un ciclo: abuela pasa a depender de su propia nieta
        abuela.categoria_padre = hija
        with self.assertRaises(ValidationError):
            abuela.clean()


class ProductoModelTestCase(TestCase):
    """
    Suite de pruebas QA para Producto.

    Cubre:
        - Generacion automatica de slug.
        - Calculo de precio con descuento.
        - Restriccion unica de nombre por categoria.
        - Calculo del IVA incluido en el precio (10%, 5%, exento).
    """

    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Calzado Test")

    def test_slug_se_genera_automaticamente(self):
        """Si no se especifica slug, se genera a partir del nombre."""
        producto = Producto.objects.create(
            nombre="Zapatillas Running X",
            categoria=self.categoria,
            precio_base=Decimal("300000"),
        )
        self.assertEqual(producto.slug, "zapatillas-running-x")

    def test_precio_con_descuento_se_calcula_correctamente(self):
        """Un descuento del 20% sobre 100000 da un precio final de 80000."""
        producto = Producto.objects.create(
            nombre="Producto con Descuento",
            categoria=self.categoria,
            precio_base=Decimal("100000"),
            porcentaje_descuento=Decimal("20"),
        )
        self.assertEqual(producto.precio_con_descuento, Decimal("80000"))

    def test_sin_descuento_precio_final_es_igual_al_base(self):
        """Sin porcentaje_descuento, el precio final coincide con el base."""
        producto = Producto.objects.create(
            nombre="Producto Sin Descuento",
            categoria=self.categoria,
            precio_base=Decimal("150000"),
        )
        self.assertEqual(producto.precio_con_descuento, Decimal("150000"))

    def test_no_se_permite_nombre_duplicado_en_misma_categoria(self):
        """La restriccion unica impide nombres duplicados en la misma categoria."""
        Producto.objects.create(
            nombre="Remera Basica",
            categoria=self.categoria,
            precio_base=Decimal("50000"),
        )
        with self.assertRaises(Exception):
            Producto.objects.create(
                nombre="Remera Basica",
                categoria=self.categoria,
                precio_base=Decimal("60000"),
            )

    # ------------------------------------------------------------------
    # CALCULO DE IVA
    # ------------------------------------------------------------------

    def test_monto_iva_incluido_tasa_diez_por_ciento(self):
        """
        Para un producto de Gs. 110000 con IVA 10% incluido,
        el IVA contenido debe ser 10000 (110000 / 11).
        """
        producto = Producto.objects.create(
            nombre="Producto Gravado 10",
            categoria=self.categoria,
            precio_base=Decimal("110000"),
            tasa_iva=Producto.TasaIVA.DIEZ,
        )
        self.assertEqual(producto.monto_iva_incluido, Decimal("10000"))

    def test_monto_iva_incluido_tasa_cinco_por_ciento(self):
        """
        Para un producto de Gs. 105000 con IVA 5% incluido,
        el IVA contenido debe ser 5000 (105000 / 21).
        """
        producto = Producto.objects.create(
            nombre="Producto Gravado 5",
            categoria=self.categoria,
            precio_base=Decimal("105000"),
            tasa_iva=Producto.TasaIVA.CINCO,
        )
        self.assertEqual(producto.monto_iva_incluido, Decimal("5000"))

    def test_monto_iva_incluido_exento_es_cero(self):
        """Un producto exento de IVA siempre retorna 0 de IVA incluido."""
        producto = Producto.objects.create(
            nombre="Producto Exento",
            categoria=self.categoria,
            precio_base=Decimal("100000"),
            tasa_iva=Producto.TasaIVA.EXENTO,
        )
        self.assertEqual(producto.monto_iva_incluido, Decimal("0"))


class VarianteModelTestCase(TestCase):
    """
    Suite de pruebas QA para Variante.

    Cubre:
        - Calculo del precio total (precio del producto + modificador).
        - Reduccion de stock exitosa.
        - Reduccion de stock con cantidad insuficiente lanza excepcion.
        - Incremento de stock.
        - Propiedades tiene_stock y requiere_reposicion.
    """

    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Accesorios Test")
        self.producto = Producto.objects.create(
            nombre="Gorra de Prueba",
            categoria=self.categoria,
            precio_base=Decimal("50000"),
        )

    def test_precio_total_incluye_modificador(self):
        """El precio total de la variante suma el modificador al precio base."""
        variante = Variante.objects.create(
            producto=self.producto,
            nombre="Talle Unico - Edicion Especial",
            sku="GORRA-TEST-001",
            modificador_precio=Decimal("10000"),
            inventario=5,
        )
        self.assertEqual(variante.precio_total, Decimal("60000"))

    def test_reducir_stock_descuenta_inventario(self):
        """reducir_stock() descuenta correctamente el inventario disponible."""
        variante = Variante.objects.create(
            producto=self.producto,
            nombre="Talle Unico",
            sku="GORRA-TEST-002",
            inventario=10,
        )
        variante.reducir_stock(4)
        variante.refresh_from_db()
        self.assertEqual(variante.inventario, 6)

    def test_reducir_stock_insuficiente_lanza_excepcion(self):
        """reducir_stock() lanza StockInsuficiente si no hay suficiente inventario."""
        variante = Variante.objects.create(
            producto=self.producto,
            nombre="Talle Unico",
            sku="GORRA-TEST-003",
            inventario=3,
        )
        with self.assertRaises(StockInsuficiente):
            variante.reducir_stock(10)

        # El inventario no debe haberse modificado tras el error
        variante.refresh_from_db()
        self.assertEqual(variante.inventario, 3)

    def test_incrementar_stock_aumenta_inventario(self):
        """incrementar_stock() suma correctamente al inventario disponible."""
        variante = Variante.objects.create(
            producto=self.producto,
            nombre="Talle Unico",
            sku="GORRA-TEST-004",
            inventario=5,
        )
        variante.incrementar_stock(7)
        variante.refresh_from_db()
        self.assertEqual(variante.inventario, 12)

    def test_tiene_stock_es_false_cuando_inventario_es_cero(self):
        """tiene_stock retorna False cuando el inventario llega a cero."""
        variante = Variante.objects.create(
            producto=self.producto,
            nombre="Talle Unico",
            sku="GORRA-TEST-005",
            inventario=0,
        )
        self.assertFalse(variante.tiene_stock)

    def test_requiere_reposicion_segun_stock_minimo(self):
        """requiere_reposicion es True cuando inventario <= stock_minimo."""
        variante = Variante.objects.create(
            producto=self.producto,
            nombre="Talle Unico",
            sku="GORRA-TEST-006",
            inventario=2,
            stock_minimo=5,
        )
        self.assertTrue(variante.requiere_reposicion)

class ProductoSerializerTestCase(TestCase):
    """Pruebas de validacion de serializers del catalogo."""

    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Celulares")

    def test_producto_write_rechaza_precio_cero(self):
        from .serializers import ProductoWriteSerializer

        serializer = ProductoWriteSerializer(data={
            "nombre": "iPhone 15",
            "categoria": self.categoria.slug,
            "precio_base": "0",
            "porcentaje_descuento": "0",
            "tasa_iva": Producto.TasaIVA.DIEZ,
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn("precio_base", serializer.errors)

    def test_producto_write_rechaza_nombre_duplicado_misma_categoria_sin_importar_mayusculas(self):
        from .serializers import ProductoWriteSerializer

        Producto.objects.create(
            nombre="iPhone 15",
            categoria=self.categoria,
            precio_base=Decimal("5000000"),
        )
        serializer = ProductoWriteSerializer(data={
            "nombre": "iphone 15",
            "categoria": self.categoria.slug,
            "precio_base": "5200000",
            "porcentaje_descuento": "0",
            "tasa_iva": Producto.TasaIVA.DIEZ,
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn("nombre", serializer.errors)

    def test_variante_permite_stock_minimo_mayor_al_inventario(self):
        from .serializers import VarianteSerializer

        producto = Producto.objects.create(
            nombre="Samsung A55",
            categoria=self.categoria,
            precio_base=Decimal("2500000"),
        )
        serializer = VarianteSerializer(data={
            "producto": producto.id,
            "nombre": "Color Negro",
            "sku": "SAM-A55-NEGRO",
            "modificador_precio": "0",
            "inventario": 2,
            "stock_minimo": 5,
            "atributos": {"color": "negro"},
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_variante_rechaza_sku_duplicado_case_insensitive(self):
        from .serializers import VarianteSerializer

        producto = Producto.objects.create(
            nombre="Motorola G",
            categoria=self.categoria,
            precio_base=Decimal("1500000"),
        )
        Variante.objects.create(
            producto=producto,
            nombre="Azul",
            sku="MOTO-G-AZUL",
            inventario=3,
        )
        serializer = VarianteSerializer(data={
            "producto": producto.id,
            "nombre": "Azul Oscuro",
            "sku": "moto-g-azul",
            "modificador_precio": "0",
            "inventario": 1,
            "stock_minimo": 1,
            "atributos": {"color": "azul"},
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn("sku", serializer.errors)

    def test_categoria_serializer_rechaza_duplicado_raiz_case_insensitive(self):
        from .serializers import CategoriaSerializer

        Categoria.objects.create(nombre="Accesorios")
        serializer = CategoriaSerializer(data={
            "nombre": "accesorios",
            "descripcion": "Duplicada",
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn("nombre", serializer.errors)


class VarianteStockTransaccionalTestCase(TestCase):
    """Pruebas de reglas de negocio del stock."""

    def setUp(self):
        categoria = Categoria.objects.create(nombre="Audio")
        producto = Producto.objects.create(
            nombre="Auricular Bluetooth",
            categoria=categoria,
            precio_base=Decimal("180000"),
        )
        self.variante = Variante.objects.create(
            producto=producto,
            nombre="Negro",
            sku="AUD-BT-NEGRO",
            inventario=5,
        )

    def test_reducir_stock_rechaza_cero(self):
        with self.assertRaises(ValueError):
            self.variante.reducir_stock(0)

    def test_incrementar_stock_rechaza_cero(self):
        with self.assertRaises(ValueError):
            self.variante.incrementar_stock(0)
