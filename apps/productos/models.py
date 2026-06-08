from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.utils.text import slugify
from core.models import ModeloBase
from core.exceptions import StockInsuficiente


# ==============================================================================
# UTILERIAS Y MANAGERS
# ==============================================================================

def generar_slug_unico(instancia, campo_origen, campo_destino="slug"):
    """
    Genera un slug unico manejando colisiones automaticamente.
    Si 'nike-air-max' existe, genera 'nike-air-max-1', etc.
    """
    valor_origen = getattr(instancia, campo_origen)
    slug_base = slugify(valor_origen)
    Klass = instancia.__class__
    slug = slug_base
    contador = 1

    while (
        Klass.objects.filter(**{campo_destino: slug})
        .exclude(pk=instancia.pk)
        .exists()
    ):
        slug = f"{slug_base}-{contador}"
        contador += 1

    return slug


class ProductoQuerySet(models.QuerySet):
    """
    QuerySet personalizado para encapsular consultas logicas.
    Evita el problema N+1 en listados de productos.
    """
    def destacados(self):
        return self.filter(es_destacado=True, esta_activo=True)

    def con_detalles(self):
        """
        Trae todas las relaciones en un solo viaje a la base de datos.
        Sin esto, listar 100 productos haria 300 consultas.
        """
        return self.select_related("categoria").prefetch_related(
            "variantes", "imagenes"
        )


class ProductoManager(models.Manager):
    """Manager para hacer accesible el QuerySet desde Producto.objects."""

    def get_queryset(self):
        return ProductoQuerySet(self.model, using=self._db)

    def destacados(self):
        return self.get_queryset().destacados()

    def con_detalles(self):
        return self.get_queryset().con_detalles()


# ==============================================================================
# MODELOS
# ==============================================================================

class Categoria(ModeloBase):
    """
    Categorias de productos con soporte para jerarquia.
    Ejemplo: Ropa > Camisetas > Camisetas deportivas
    """
    nombre = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(unique=True, max_length=200)
    descripcion = models.TextField(blank=True)
    categoria_padre = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subcategorias",
    )

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def clean(self):
        """
        Evita ciclos infinitos en la jerarquia de categorias.
        Una categoria no puede ser su propio padre ni descendiente de si misma.
        """
        super().clean()
        if self.categoria_padre == self:
            raise ValidationError(
                "Una categoria no puede ser su propio padre."
            )
        padre = self.categoria_padre
        while padre is not None:
            if padre == self:
                raise ValidationError(
                    f"Ciclo detectado: '{self.nombre}' no puede ser descendiente de si misma."
                )
            padre = padre.categoria_padre

    def save(self, *args, **kwargs):
        """
        Genera el slug automaticamente.
        No llama full_clean() aqui para evitar problemas en migraciones.
        La validacion se hace desde el serializer.
        """
        if not self.slug:
            self.slug = generar_slug_unico(self, "nombre")
        super().save(*args, **kwargs)


class Producto(ModeloBase):
    """
    Producto principal del catalogo.
    El stock se maneja en Variante, no aqui.
    """
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        null=True,
        related_name="productos",
    )
    nombre = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(unique=True, max_length=255)
    descripcion = models.TextField(blank=True)
    precio_base = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(Decimal("0"))]
    )
    porcentaje_descuento = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00"))
        ],
    )
    es_destacado = models.BooleanField(default=False, db_index=True)

    objects = ProductoManager()

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["-fecha_creacion"]
        
        # ─── MODIFICACIÓN  ──────────────────────────────────────────
        # Evita que se dupliquen productos con el mismo nombre en la misma categoría
        constraints = [
            UniqueConstraint(
                fields=["nombre", "categoria"],
                name="unique_nombre_por_categoria",
                violation_error_message="Ya existe un producto con este nombre en esta categoría."
            )
        ]
        # ────────────────────────────────────────────────────────────────────


    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generar_slug_unico(self, "nombre")
        super().save(*args, **kwargs)

    @property
    def precio_con_descuento(self):
        """
        Calcula el precio final en guaranies.
        El Guarani no tiene decimales, se redondea al entero mas cercano.
        """
        factor = Decimal("1.00") - (
            self.porcentaje_descuento / Decimal("100.00")
        )
        return (self.precio_base * factor).quantize(Decimal("1"))


class Variante(ModeloBase):
    """
    Variante de un producto (talle, color, etc).
    Aqui se maneja el stock real del sistema.
    """
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="variantes"
    )
    nombre = models.CharField(max_length=200)
    sku = models.CharField(
        max_length=100,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Z0-9-]+$",
                message="El SKU solo permite letras mayusculas, numeros y guiones (-).",
            )
        ],
    )
    modificador_precio = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0
    )
    inventario = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=5)
    atributos = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Variante"
        verbose_name_plural = "Variantes"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.producto.nombre} - {self.nombre}"

    @property
    def precio_total(self):
        """Calcula el precio final de la variante en Guaranies."""
        return (
            self.producto.precio_con_descuento + self.modificador_precio
        ).quantize(Decimal("1"))

    @property
    def tiene_stock(self):
        """Retorna True si hay stock disponible."""
        return self.inventario > 0

    @property
    def requiere_reposicion(self):
        """Retorna True si el stock bajo del minimo configurado."""
        return self.inventario <= self.stock_minimo

    def incrementar_stock(self, cantidad):
        """
        Incrementa el stock de forma controlada.
        Usa update_fields para optimizar la consulta SQL.
        """
        if cantidad < 0:
            raise ValueError("La cantidad a incrementar debe ser positiva.")
        self.inventario += cantidad
        self.save(update_fields=[
            "inventario",
            "esta_activo",
            "fecha_actualizacion"
        ])

    def reducir_stock(self, cantidad):
        """
        Reduce el stock de forma controlada.
        Lanza StockInsuficiente de core si no hay stock suficiente.
        """
        if cantidad < 0:
            raise ValueError("La cantidad a reducir debe ser positiva.")
        if self.inventario - cantidad < 0:
            raise StockInsuficiente(
                producto=self.producto.nombre,
                disponible=self.inventario
            )
        self.inventario -= cantidad
        self.save(update_fields=[
            "inventario",
            "esta_activo",
            "fecha_actualizacion"
        ])


class ImagenProducto(ModeloBase):
    """
    Imagenes asociadas a un producto.
    Solo puede haber una imagen principal por producto.
    """
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="imagenes"
    )
    imagen = models.ImageField(upload_to="productos/")
    es_principal = models.BooleanField(default=False)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Imagen de Producto"
        verbose_name_plural = "Imagenes de Productos"
        ordering = ["orden"]
        constraints = [
            UniqueConstraint(
                fields=["producto", "es_principal"],
                condition=Q(es_principal=True),
                name="unique_principal_image_per_product",
            )
        ]

    def __str__(self):
        return f"Imagen de {self.producto.nombre}"

    def save(self, *args, **kwargs):
        """
        Si esta imagen se marca como principal,
        quita el flag de las demas imagenes del mismo producto.
        """
        if self.es_principal:
            ImagenProducto.objects.filter(
                producto=self.producto
            ).exclude(pk=self.pk).update(es_principal=False)
        super().save(*args, **kwargs)