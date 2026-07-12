import re
from decimal import Decimal
from rest_framework import serializers
from rest_framework import serializers as drf_serializers
from drf_spectacular.utils import extend_schema_field
from .models import Categoria, Producto, Variante, ImagenProducto



NOMBRE_CATALOGO_REGEX = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 .,'&()/-]*$")


def normalizar_texto_catalogo(valor: str) -> str:
    """Limpia espacios repetidos sin alterar marcas como iPhone o JBL."""
    return re.sub(r"\s+", " ", valor or "").strip()


def validar_nombre_catalogo(valor: str, campo: str = "nombre") -> str:
    """Valida nombres de categorias, productos y variantes."""
    valor = normalizar_texto_catalogo(valor)
    if len(valor) < 2:
        raise serializers.ValidationError(
            f"El {campo} debe tener al menos 2 caracteres."
        )
    if not NOMBRE_CATALOGO_REGEX.match(valor):
        raise serializers.ValidationError(
            f"El {campo} contiene caracteres no permitidos."
        )
    return valor


# ==============================================================================
# SERIALIZERS DE CATEGORIA
# ==============================================================================

class CategoriaListSerializer(serializers.ModelSerializer):
    """Serializer para listados de categorias."""

    class Meta:
        model = Categoria
        fields = ["id", "nombre", "slug", "esta_activo"]
        read_only_fields = ["id", "slug"]


class CategoriaSerializer(serializers.ModelSerializer):
    """
    Serializer completo de Categoria.
    Incluye subcategorias activas con control de profundidad
    para evitar recursiones infinitas.
    """
    subcategorias = serializers.SerializerMethodField()
    cantidad_productos = serializers.SerializerMethodField()

    class Meta:
        model = Categoria
        fields = [
            "id",
            "nombre",
            "slug",
            "descripcion",
            "categoria_padre",
            "subcategorias",
            "cantidad_productos",
            "esta_activo",
        ]
        read_only_fields = ["id", "slug"]

    @extend_schema_field(drf_serializers.ListField())
    def get_subcategorias(self, obj):
        """Retorna subcategorias activas limitando profundidad a 3 niveles."""
        depth = self.context.get("depth", 0)
        if depth >= 3:
            return []
        subcategorias = obj.subcategorias.filter(esta_activo=True)
        return CategoriaListSerializer(
            subcategorias,
            many=True,
            context={**self.context, "depth": depth + 1},
        ).data

    @extend_schema_field(drf_serializers.IntegerField())
    def get_cantidad_productos(self, obj):
        """
        Usa anotacion SQL si existe, sino hace consulta directa.
        Compatible con admin y vistas normales.
        """
        if hasattr(obj, "_prod_activos_count"):
            return obj._prod_activos_count
        return obj.productos.filter(esta_activo=True).count()

    def validate_nombre(self, value: str) -> str:
        """Normaliza y valida el nombre de categoria."""
        return validar_nombre_catalogo(value, "nombre de la categoria")

    def validate(self, data):
        """Evita duplicados por nivel y ciclos en la jerarquia."""
        nombre = data.get("nombre", getattr(self.instance, "nombre", None))
        categoria_padre = data.get(
            "categoria_padre",
            getattr(self.instance, "categoria_padre", None),
        )

        if nombre:
            queryset = Categoria.objects.filter(
                nombre__iexact=nombre,
                categoria_padre=categoria_padre,
            )
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({
                    "nombre": "Ya existe una categoria con este nombre en este nivel."
                })

        if self.instance and categoria_padre:
            if categoria_padre == self.instance:
                raise serializers.ValidationError({
                    "categoria_padre": "Una categoria no puede ser su propio padre."
                })
            padre_actual = categoria_padre
            limite = 0
            while padre_actual:
                if limite > 10:
                    raise serializers.ValidationError({
                        "categoria_padre": "Estructura de categorias demasiado profunda."
                    })
                if padre_actual == self.instance:
                    raise serializers.ValidationError({
                        "categoria_padre": "No se permiten ciclos en categorias."
                    })
                padre_actual = padre_actual.categoria_padre
                limite += 1
        return data


# ==============================================================================
# SERIALIZERS DE IMAGENES
# ==============================================================================

class ImagenProductoSerializer(serializers.ModelSerializer):
    """
    Serializer de imagenes de productos.
    Genera URL absoluta segura para el frontend.
    """
    url = serializers.SerializerMethodField()

    class Meta:
        model = ImagenProducto
        fields = ["id", "producto", "imagen", "url", "es_principal", "orden"]
        read_only_fields = ["id", "url"]
        extra_kwargs = {
            "imagen": {"write_only": True},
        }

    @extend_schema_field(drf_serializers.URLField(allow_null=True))
    def get_url(self, obj):
        """Retorna URL absoluta protegida contra archivos inexistentes."""
        request = self.context.get("request")
        if obj.imagen and hasattr(obj.imagen, "url") and request:
            try:
                return request.build_absolute_uri(obj.imagen.url)
            except ValueError:
                pass
        return None

    def validate_imagen(self, value):
        """Limita imagenes demasiado pesadas para proteger almacenamiento."""
        max_size_mb = 5
        if value.size > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError(
                f"La imagen no puede superar {max_size_mb} MB."
            )
        return value


# ==============================================================================
# SERIALIZERS DE VARIANTE
# ==============================================================================

class VarianteListSerializer(serializers.ModelSerializer):
    """Serializer resumido de Variante para listados."""

    precio_total = serializers.DecimalField(
        max_digits=12,
        decimal_places=0,
        read_only=True
    )
    tiene_stock = serializers.BooleanField(read_only=True) 
    
    class Meta:
        model = Variante
        fields = [
            "id",
            "nombre",
            "sku",
            "precio_total",
            "inventario",
            "tiene_stock",
            "esta_activo",
        ]
        read_only_fields = ["id"]


class VarianteSerializer(serializers.ModelSerializer):
    """Serializer completo de Variante."""
 
    sku = serializers.CharField(max_length=100)
    producto_nombre = serializers.CharField(
        source="producto.nombre",
        read_only=True
    )
    precio_total = serializers.DecimalField(
        max_digits=12,
        decimal_places=0,
        read_only=True
    )
    tiene_stock = serializers.BooleanField(read_only=True)
    requiere_reposicion = serializers.BooleanField(read_only=True)

    class Meta:
        model = Variante
        fields = [
            "id",
            "producto",
            "producto_nombre",
            "nombre",
            "sku",
            "modificador_precio",
            "inventario",
            "stock_minimo",
            "atributos",
            "precio_total",
            "tiene_stock",
            "requiere_reposicion",
            "esta_activo",
        ]
        read_only_fields = [
            "id",
            "precio_total",
            "tiene_stock",
            "requiere_reposicion"
        ]

    def validate_nombre(self, value):
        """Valida el nombre visible de la variante."""
        return validar_nombre_catalogo(value, "nombre de la variante")

    def validate_sku(self, value):
        """Normaliza el SKU y valida unicidad antes de llegar a la base."""
        valor = value.strip().upper()
        if not re.match(r"^[A-Z0-9-]+$", valor):
            raise serializers.ValidationError(
                "El SKU solo permite letras, numeros y guiones (-)."
            )
        queryset = Variante.objects.filter(sku__iexact=valor)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Ya existe una variante con este SKU.")
        return valor

    def validate_atributos(self, value):
        """Asegura que atributos sea un objeto JSON y no una lista/texto."""
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Los atributos deben enviarse como objeto JSON."
            )
        return value

    def validate(self, data):
        """Validaciones de negocio con soporte POST, PUT y PATCH."""
        producto = data.get("producto", getattr(self.instance, "producto", None))
        modificador = data.get(
            "modificador_precio",
            getattr(self.instance, "modificador_precio", Decimal("0")),
        )
        if producto and producto.precio_con_descuento + modificador <= 0:
            raise serializers.ValidationError({
                "modificador_precio": "El precio final de la variante debe ser mayor a cero."
            })
        return data


# ==============================================================================
# SERIALIZERS DE PRODUCTO
# ==============================================================================

class ProductoListSerializer(serializers.ModelSerializer):
    """
    Serializer resumido para listado de productos.
    Optimizado para mostrar solo lo necesario en el catalogo.
    """
    categoria_nombre = serializers.CharField(
        source="categoria.nombre",
        read_only=True
    )
    precio_con_descuento = serializers.DecimalField(
        max_digits=12,
        decimal_places=0,
        read_only=True
    )
    imagen_principal = serializers.SerializerMethodField()
    monto_iva_incluido = serializers.DecimalField(
        max_digits=12,
        decimal_places=0,
        read_only=True,
    )
    variante_unica_id = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = [
            "id",
            "nombre",
            "slug",
            "categoria_nombre",
            "precio_base",
            "porcentaje_descuento",
            "precio_con_descuento",
            "tasa_iva",
            "monto_iva_incluido",
            "imagen_principal",
            "es_destacado",
            "esta_activo",
            "variante_unica_id",
        ]
        read_only_fields = ["id", "slug"]

    @extend_schema_field(drf_serializers.URLField(allow_null=True))
    def get_imagen_principal(self, obj):
        """
        Obtiene la imagen principal del producto.
        Si no hay principal definida usa la primera disponible.
        Optimizado para funcionar con Prefetch desde la vista.
        """
        imagenes = obj.imagenes.all()
        principal = next(
            (img for img in imagenes if img.es_principal),
            imagenes[0] if imagenes else None
        )
        if principal and principal.imagen and hasattr(principal.imagen, "url"):
            request = self.context.get("request")
            if request:
                try:
                    return request.build_absolute_uri(principal.imagen.url)
                except ValueError:
                    pass
        return None
    
    @extend_schema_field(drf_serializers.CharField(allow_null=True))
    def get_variante_unica_id(self, obj):
        """
        Devuelve el id (como string) de la variante si el producto
        tiene exactamente una variante activa. Si tiene 0 o mas de una,
        devuelve None y el frontend debe llevar al detalle para elegir.
        """
        variantes_activas = [v for v in obj.variantes.all() if v.esta_activo]
        if len(variantes_activas) == 1:
            return str(variantes_activas[0].id)
        return None


class ProductoSerializer(serializers.ModelSerializer):
    """
    Serializer completo de Producto para detalle.
    Incluye variantes e imagenes anidadas.
    """
    categoria_detalle = CategoriaListSerializer(
        source="categoria",
        read_only=True
    )
    variantes = VarianteSerializer(many=True, read_only=True)
    imagenes = ImagenProductoSerializer(many=True, read_only=True)
    precio_con_descuento = serializers.DecimalField(
        max_digits=12,
        decimal_places=0,
        read_only=True
    )
    monto_iva_incluido = serializers.DecimalField(
        max_digits=12,
        decimal_places=0,
        read_only=True,
    )

    class Meta:
        model = Producto
        fields = [
            "id",
            "nombre",
            "slug",
            "categoria",
            "categoria_detalle",
            "descripcion",
            "precio_base",
            "porcentaje_descuento",
            "precio_con_descuento",
            "tasa_iva",
            "monto_iva_incluido",
            "es_destacado",
            "variantes",
            "imagenes",
            "esta_activo",
            "fecha_creacion",
        ]
        read_only_fields = [
            "id",
            "slug",
            "precio_con_descuento",
            "monto_iva_incluido",
            "fecha_creacion"
        ]

    def validate_nombre(self, value):
        """Normaliza y valida el nombre del producto."""
        return validar_nombre_catalogo(value, "nombre del producto")

    def validate(self, data):
        """Validaciones de negocio adicionales compatibles con PATCH."""
        descuento = data.get(
            "porcentaje_descuento",
            getattr(self.instance, "porcentaje_descuento", Decimal("0"))
        )
        if descuento and descuento > 90:
            raise serializers.ValidationError({
                "porcentaje_descuento": "El descuento no puede superar el 90%."
            })
        return data


# ==============================================================================
# SERIALIZER DE ESCRITURA
# ==============================================================================

class ProductoWriteSerializer(serializers.ModelSerializer):
    """
    Serializer optimizado para escritura de Producto.
    Acepta el slug de categoria en lugar del UUID.
    Usado en POST, PUT y PATCH.
    """
    categoria = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=Categoria.objects.filter(esta_activo=True),
    )

    class Meta:
        model = Producto
        fields = [
            "id",
            "nombre",
            "categoria",
            "descripcion",
            "precio_base",
            "porcentaje_descuento",
            "tasa_iva",
            "es_destacado",
            "esta_activo",
            "slug",
        ]
        read_only_fields = ["id", "slug"]

    def validate_nombre(self, value):
        """Normaliza y valida el nombre del producto."""
        return validar_nombre_catalogo(value, "nombre del producto")

    def validate_precio_base(self, value):
        """En catalogo no se permiten productos con precio cero."""
        if value <= 0:
            raise serializers.ValidationError(
                "El precio base debe ser mayor a cero."
            )
        return value

    def validate(self, data):
        """Validaciones de negocio para escritura."""
        nombre = data.get("nombre", getattr(self.instance, "nombre", None))
        categoria = data.get("categoria", getattr(self.instance, "categoria", None))
        descuento = data.get(
            "porcentaje_descuento",
            getattr(self.instance, "porcentaje_descuento", Decimal("0"))
        )

        if descuento and descuento > 90:
            raise serializers.ValidationError({
                "porcentaje_descuento": "El descuento no puede superar el 90%."
            })

        if nombre and categoria:
            queryset = Producto.objects.filter(
                nombre__iexact=nombre,
                categoria=categoria,
            )
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({
                    "nombre": "Ya existe un producto con este nombre en esta categoria."
                })
        return data
    
    
    
