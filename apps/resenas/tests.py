from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase

from apps.productos.models import Categoria, Producto, Variante
from apps.ordenes.models import Orden, ItemOrden
from .models import Resena

Usuario = get_user_model()


class ResenaModelTestCase(TestCase):
    """
    Suite de pruebas QA para el modulo de Resenas.

    Cubre:
        - Verificacion automatica de compra (es_verificada).
        - Restriccion unica usuario + producto.
        - Validacion de rango de calificacion (1-5).
        - Validacion de longitud maxima de titulo.
        - Generacion automatica de fecha_creacion.
    """

    def setUp(self):
        """Prepara usuarios, categoria, producto, variante y orden de prueba."""
        self.user_comprador = Usuario.objects.create_user(
            username="comprador",
            email="comprador@tienda.com",
            password="Password123"
        )
        self.user_curioso = Usuario.objects.create_user(
            username="curioso",
            email="curioso@tienda.com",
            password="Password123"
        )

        self.categoria = Categoria.objects.create(
            nombre="Ropa de Prueba"
        )

        self.producto = Producto.objects.create(
            nombre="Sweater De Lana",
            categoria=self.categoria,
            precio_base=Decimal("150000"),
            esta_activo=True
        )

        self.variante = Variante.objects.create(
            producto=self.producto,
            nombre="Talle Unico",
            sku="SWEATER-LANA-U",
            inventario=10
        )

        # Orden confirmada del comprador, con un item que referencia
        # la variante del producto. Esto es lo que activa es_verificada=True.
        self.orden = Orden.objects.create(
            usuario=self.user_comprador,
            estado=Orden.Estado.CONFIRMED,
            subtotal=Decimal("150000"),
            total=Decimal("150000"),
        )
        ItemOrden.objects.create(
            orden=self.orden,
            variante=self.variante,
            cantidad=1,
            precio_unitario=Decimal("150000"),
            nombre_producto=self.producto.nombre,
            nombre_variante=self.variante.nombre,
        )

    # ------------------------------------------------------------------
    # VERIFICACION DE COMPRA
    # ------------------------------------------------------------------

    def test_resena_comprador_es_verificada(self):
        """Un usuario con orden confirmada del producto debe quedar verificado."""
        from apps.ordenes.models import Orden

        resena = Resena.objects.create(
            usuario=self.user_comprador,
            producto=self.producto,
            calificacion=5,
            titulo="Excelente",
            comentario="Me encanto el abrigo."
        )
        self.assertTrue(resena.es_verificada)

    def test_resena_no_comprador_no_es_verificada(self):
        """Un usuario sin ordenes del producto debe quedar sin verificar."""
        resena = Resena.objects.create(
            usuario=self.user_curioso,
            producto=self.producto,
            calificacion=4,
            titulo="Lindo",
            comentario="Se ve bien aunque no lo compre aqui."
        )
        self.assertFalse(resena.es_verificada)

    # ------------------------------------------------------------------
    # RESTRICCION UNICA
    # ------------------------------------------------------------------

    def test_restriccion_unica_usuario_producto(self):
        """Un usuario no puede dejar dos resenas para el mismo producto."""
        Resena.objects.create(
            usuario=self.user_curioso,
            producto=self.producto,
            calificacion=3
        )
        with self.assertRaises(IntegrityError):
            Resena.objects.create(
                usuario=self.user_curioso,
                producto=self.producto,
                calificacion=5
            )

    # ------------------------------------------------------------------
    # VALIDACIONES DE CAMPO
    # ------------------------------------------------------------------

    def test_validacion_rango_calificacion(self):
        """No se permiten calificaciones fuera del rango 1-5."""
        resena_invalida = Resena(
            usuario=self.user_curioso,
            producto=self.producto,
            calificacion=6
        )
        with self.assertRaises(ValidationError):
            resena_invalida.full_clean()

    def test_limite_maximo_longitud_titulo(self):
        """El titulo no puede superar los 200 caracteres."""
        titulo_valido = "A" * 200
        titulo_invalido = "A" * 201

        resena_limite = Resena(
            usuario=self.user_curioso,
            producto=self.producto,
            calificacion=5,
            titulo=titulo_valido
        )
        resena_limite.full_clean()

        resena_excedida = Resena(
            usuario=self.user_curioso,
            producto=self.producto,
            calificacion=5,
            titulo=titulo_invalido
        )
        with self.assertRaises(ValidationError):
            resena_excedida.full_clean()

    # ------------------------------------------------------------------
    # CAMPOS AUTOMATICOS
    # ------------------------------------------------------------------

    def test_fecha_creacion_se_genera_automaticamente(self):
        """fecha_creacion debe asignarse automaticamente al crear."""
        resena = Resena.objects.create(
            usuario=self.user_curioso,
            producto=self.producto,
            calificacion=5
        )
        self.assertIsNotNone(resena.fecha_creacion)

    # ------------------------------------------------------------------
    # PROPIEDAD ESTRELLAS
    # ------------------------------------------------------------------

    def test_propiedad_estrellas_formato_visual(self):
        """La propiedad estrellas debe mostrar el formato visual correcto."""
        resena = Resena.objects.create(
            usuario=self.user_curioso,
            producto=self.producto,
            calificacion=3
        )
        self.assertEqual(resena.estrellas, "⭐⭐⭐☆☆")
        
    # ------------------------------------------------------------------
    # OPTIMIZACION DE RENDIMIENTO
    # ------------------------------------------------------------------

    def test_editar_resena_no_recalcula_verificacion(self):
        """
        Al editar una resena existente no debe ejecutarse la consulta
        de verificacion de compra nuevamente, solo el UPDATE.
        """
        resena = Resena.objects.create(
            usuario=self.user_curioso,
            producto=self.producto,
            calificacion=4,
            titulo="Primer titulo"
        )

        resena.titulo = "Titulo modificado"

        with self.assertNumQueries(1):
            resena.save()