from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.productos.models import Categoria, Producto, Variante
from apps.cupones.models import Cupon

Usuario = get_user_model()


class Command(BaseCommand):
    """
    Carga datos de demostración para desarrollo.

    Crea usuarios, categorías, productos, variantes y un cupón
    de prueba. Es idempotente: si los datos ya existen, no los
    duplica (usa get_or_create en todos los casos).

    Uso:
        python manage.py cargar_datos_demo
    """
    help = "Carga datos de demostración (usuarios, productos, cupones) para QA."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Cargando datos de demostración...")

        cliente = self._crear_usuario_cliente()
        categorias = self._crear_categorias()
        self._crear_productos(categorias)
        self._crear_cupon()

        self.stdout.write(self.style.SUCCESS(
            "\n Datos de demostración cargados exitosamente.\n"
            f"   Usuario cliente: {cliente.username} / Pass123456\n"
        ))

    def _crear_usuario_cliente(self) -> Usuario:
        """Crea un usuario cliente de prueba (no admin)."""
        usuario, creado = Usuario.objects.get_or_create(
            username="cliente_test",
            defaults={
                "email": "cliente_test@example.com",
                "first_name": "Cliente",
                "last_name": "De Prueba",
            }
        )
        if creado:
            usuario.set_password("Pass123456")
            usuario.save()
            self.stdout.write("  ✓ Usuario cliente_test creado.")
        else:
            self.stdout.write("  • Usuario cliente_test ya existía.")
        return usuario

    def _crear_categorias(self) -> dict[str, Categoria]:
        """Crea categorías base. Retorna un diccionario nombre→instancia."""
        nombres = ["Calzado", "Ropa", "Accesorios"]
        categorias = {}

        for nombre in nombres:
            categoria, creado = Categoria.objects.get_or_create(
                nombre=nombre,
                categoria_padre=None,
                defaults={"descripcion": f"Categoría de {nombre.lower()}"}
            )
            categorias[nombre] = categoria
            estado = "creada" if creado else "ya existía"
            self.stdout.write(f"  ✓ Categoría '{nombre}' {estado}.")

        return categorias

    def _crear_productos(self, categorias: dict[str, Categoria]) -> None:
        """Crea productos de ejemplo con sus variantes."""
        productos_demo = [
            {
                "nombre": "Nike Air Max",
                "categoria": "Calzado",
                "precio_base": Decimal("450000"),
                "descripcion": "Zapatillas deportivas Nike Air Max.",
                "variantes": [
                    ("Talle 40 - Negro", "NIKE-AIRMAX-40-NEG", 10),
                    ("Talle 42 - Negro", "NIKE-AIRMAX-42-NEG", 8),
                    ("Talle 42 - Blanco", "NIKE-AIRMAX-42-BLA", 5),
                ],
            },
            {
                "nombre": "Adidas Ultraboost",
                "categoria": "Calzado",
                "precio_base": Decimal("520000"),
                "descripcion": "Zapatillas para running Adidas Ultraboost.",
                "variantes": [
                    ("Talle 41 - Gris", "ADIDAS-UB-41-GRI", 6),
                    ("Talle 43 - Gris", "ADIDAS-UB-43-GRI", 4),
                ],
            },
            {
                "nombre": "Remera Básica Algodón",
                "categoria": "Ropa",
                "precio_base": Decimal("85000"),
                "descripcion": "Remera 100% algodón, corte clásico.",
                "variantes": [
                    ("Talle M - Blanco", "REMERA-M-BLA", 15),
                    ("Talle L - Blanco", "REMERA-L-BLA", 12),
                    ("Talle M - Negro", "REMERA-M-NEG", 10),
                ],
            },
            {
                "nombre": "Gorra Trucker",
                "categoria": "Accesorios",
                "precio_base": Decimal("65000"),
                "descripcion": "Gorra trucker ajustable, talle único.",
                "variantes": [
                    ("Único - Negro", "GORRA-UNI-NEG", 20),
                ],
            },
        ]

        for data in productos_demo:
            producto, creado = Producto.objects.get_or_create(
                nombre=data["nombre"],
                categoria=categorias[data["categoria"]],
                defaults={
                    "precio_base": data["precio_base"],
                    "descripcion": data["descripcion"],
                }
            )
            estado = "creado" if creado else "ya existía"
            self.stdout.write(f"  ✓ Producto '{data['nombre']}' {estado}.")

            for nombre_variante, sku, inventario in data["variantes"]:
                _, var_creada = Variante.objects.get_or_create(
                    producto=producto,
                    sku=sku,
                    defaults={
                        "nombre": nombre_variante,
                        "inventario": inventario,
                        "stock_minimo": 2,
                    }
                )
                if var_creada:
                    self.stdout.write(f"    ✓ Variante '{nombre_variante}' creada.")

    def _crear_cupon(self) -> None:
        """Crea un cupón de prueba reutilizable en QA."""
        cupon, creado = Cupon.objects.get_or_create(
            codigo="DESCUENTO10",
            defaults={
                "tipo": Cupon.TipoDescuento.PORCENTAJE,
                "valor": Decimal("10"),
                "monto_minimo": Decimal("0"),
                "limite_usos": 100,
                "esta_activo": True,
            }
        )
        estado = "creado" if creado else "ya existía"
        self.stdout.write(f"  ✓ Cupón DESCUENTO10 {estado}.")