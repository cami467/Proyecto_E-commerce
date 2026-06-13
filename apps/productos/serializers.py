from decimal import Decimal
from rest_framework import serializers
from rest_framework import serializers as drf_serializers
from drf_spectacular.utils import extend_schema_field
from .models import Categoria, Producto, Variante, ImagenProducto
from apps.productos.models import Categoria
from rest_framework.validators import UniqueTogetherValidator


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
        """Normaliza el nombre y verifica que no exista una categoria con el mismo nombre."""
        
        valor_normalizado = value.strip().title()
        categoria_padre = self.initial_data.get("categoria_padre")
        queryset = Categoria.objects.filter(
            nombre__iexact=valor_normalizado,
            categoria_padre=categoria_padre
        )
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                f"Ya existe una categoría llamada '{valor_normalizado}' "
                f"en este nivel. Usá un nombre diferente."
            )
        return valor_normalizado

    def validate(self, data):
        """Evita ciclos en la jerarquia con limite de profundidad."""
        categoria_padre = data.get("categoria_padre")
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

    def validate_sku(self, value):
        """Normaliza el SKU a mayusculas."""
        return value.strip().upper()

    def validate(self, data):
        """
        Validaciones de negocio con soporte PATCH.
        Usa valores existentes como respaldo si el campo no viene en el request.
        """
        inventario = data.get(
            "inventario",
            getattr(self.instance, "inventario", 0)
        )
        stock_minimo = data.get(
            "stock_minimo",
            getattr(self.instance, "stock_minimo", 0)
        )
        if stock_minimo > inventario:
            raise serializers.ValidationError({
                "stock_minimo": "El stock minimo no puede ser mayor al inventario."
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
            "imagen_principal",
            "es_destacado",
            "esta_activo",
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
            "fecha_creacion"
        ]
        
        # ─── MODIFICACIÓN ──────────────────────────────────────────
        # Captura el error de duplicados ANTES de ir a la base de datos
        validators = [
            UniqueTogetherValidator(
                queryset=Producto.objects.all(),
                fields=['nombre', 'categoria'],
                message="Ya existe un producto con este nombre en esta categoría."
            )
        ]
        # ──────────────────────────────────────────────────────────────────────

    def validate_nombre(self, value):
        """Normaliza el nombre a titulo."""
        return value.strip().title()

    def validate(self, data):
        """
        Validaciones de negocio adicionales.
        Compatible con POST, PUT y PATCH.
        """
        descuento = data.get(
            "porcentaje_descuento",
            getattr(self.instance, "porcentaje_descuento", 0)
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
            "nombre",
            "categoria",
            "descripcion",
            "precio_base",
            "porcentaje_descuento",
            "es_destacado",
            "esta_activo",
        ]

    def validate_nombre(self, value):
        """Normaliza el nombre a titulo."""
        return value.strip().title()

    def validate(self, data):
        """Validaciones de negocio para escritura."""
        descuento = data.get(
            "porcentaje_descuento",
            getattr(self.instance, "porcentaje_descuento", 0)
        )
        if descuento and descuento > 90:
            raise serializers.ValidationError({
                "porcentaje_descuento": "El descuento no puede superar el 90%."
            })
        return data