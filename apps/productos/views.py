from rest_framework import viewsets, filters, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters import rest_framework as django_filters
from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema

from core.permissions import IsAdminOrReadOnly
from .models import Categoria, Producto, Variante, ImagenProducto
from .serializers import (
    CategoriaSerializer,
    CategoriaListSerializer,
    ProductoSerializer,
    ProductoListSerializer,
    ProductoWriteSerializer,
    VarianteSerializer,
    VarianteListSerializer,
    ImagenProductoSerializer,
)


# ==============================================================================
# FILTROS AVANZADOS
# ==============================================================================

class ProductoFilter(django_filters.FilterSet):
    """
    Filtro personalizado para Productos.
    Abstrae la logica de rangos de precio fuera del QuerySet.
    """
    precio_min = django_filters.NumberFilter(
        field_name="precio_base",
        lookup_expr="gte"
    )
    precio_max = django_filters.NumberFilter(
        field_name="precio_base",
        lookup_expr="lte"
    )
    categoria = django_filters.CharFilter(
        field_name="categoria__slug"
    )

    class Meta:
        model = Producto
        fields = [
            "categoria",
            "es_destacado",
            "esta_activo",
            "precio_min",
            "precio_max"
        ]


# ==============================================================================
# MIXIN REUTILIZABLE PARA CONTEXTO
# ==============================================================================

class SerializerContextMixin:
    """
    Mixin que agrega el request al contexto del serializer.
    Necesario para generar URLs absolutas de imagenes.
    Reutilizable en todos los ViewSets.
    """
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


# ==============================================================================
# VIEWSET DE CATEGORIA
# ==============================================================================

class CategoriaViewSet(SerializerContextMixin, viewsets.ModelViewSet):
    """
    Endpoints de Categorias.
    Lectura publica, escritura solo admins.

    GET    /api/productos/categorias/        - Listar categorias
    POST   /api/productos/categorias/        - Crear categoria (admin)
    GET    /api/productos/categorias/{slug}/ - Detalle de categoria
    PUT    /api/productos/categorias/{slug}/ - Actualizar (admin)
    DELETE /api/productos/categorias/{slug}/ - Eliminar (admin)
    """
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [
        django_filters.DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter
    ]
    search_fields = ["^nombre", "descripcion"]
    ordering_fields = ["nombre", "fecha_creacion"]
    ordering = ["nombre"]
    lookup_field = "slug"

    def get_queryset(self):
        """
        Retorna categorias optimizadas con Prefetch.
        Admins ven todas, usuarios solo activas.
        Evita repeticion usando una sola variable de manager.
        """
        manager = Categoria.objects if self.request.user.is_staff else Categoria.activos
        return manager.all().prefetch_related(
            Prefetch("subcategorias", queryset=manager.all())
        )

    def get_serializer_class(self):
        """Usa serializer resumido para listados y completo para detalle."""
        if self.action == "list":
            return CategoriaListSerializer
        return CategoriaSerializer


# ==============================================================================
# VIEWSET DE PRODUCTO
# ==============================================================================

class ProductoViewSet(SerializerContextMixin, viewsets.ModelViewSet):
    """
    Endpoints de Productos.
    Lectura publica, escritura solo admins.

    GET    /api/productos/               - Listar productos
    POST   /api/productos/               - Crear producto (admin)
    GET    /api/productos/{slug}/        - Detalle de producto
    PUT    /api/productos/{slug}/        - Actualizar (admin)
    PATCH  /api/productos/{slug}/        - Actualizar parcial (admin)
    DELETE /api/productos/{slug}/        - Eliminar (admin)
    GET    /api/productos/destacados/    - Productos destacados
    GET    /api/productos/{slug}/variantes/ - Variantes del producto
    """
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [
        django_filters.DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter
    ]
    filterset_class = ProductoFilter
    search_fields = ["^nombre", "descripcion"]
    ordering_fields = ["precio_base", "fecha_creacion", "nombre"]
    ordering = ["-fecha_creacion"]
    lookup_field = "slug"

    def get_queryset(self):
        """
        Usa manager personalizado con_detalles() para optimizar joins.
        Segrega visibilidad segun rol del usuario.
        """
        queryset = Producto.objects.con_detalles()
        if not self.request.user.is_staff:
            queryset = queryset.filter(esta_activo=True)
        return queryset

    def get_serializer_class(self):
        """
        Serializer distinto segun la accion:
        - list           → resumido
        - create/update  → escritura
        - retrieve       → completo con variantes e imagenes
        """
        if self.action == "list":
            return ProductoListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return ProductoWriteSerializer
        return ProductoSerializer

    @action(detail=False, methods=["get"], url_path="destacados")
    def destacados(self, request):
        """
        Productos destacados con paginacion.
        Hereda filtros de staff/no-staff del queryset base.
        GET /api/productos/destacados/
        """
        productos = self.get_queryset().filter(es_destacado=True)
        page = self.paginate_queryset(productos)
        if page is not None:
            serializer = ProductoListSerializer(
                page,
                many=True,
                context=self.get_serializer_context()
            )
            return self.get_paginated_response(serializer.data)
        serializer = ProductoListSerializer(
            productos,
            many=True,
            context=self.get_serializer_context()
        )
        return Response(serializer.data)

    @extend_schema(operation_id="producto_variantes_list")
    @action(detail=True, methods=["get"], url_path="variantes", url_name="variantes-por-producto")
    def variantes(self, request, slug=None):
        """
        Lista variantes activas de un producto con paginacion.
        GET /api/productos/{slug}/variantes/
        """
        producto = self.get_object()
        variantes = producto.variantes.select_related("producto").filter(
            esta_activo=True
        )
        page = self.paginate_queryset(variantes)
        if page is not None:
            serializer = VarianteListSerializer(
                page,
                many=True,
                context=self.get_serializer_context()
            )
            return self.get_paginated_response(serializer.data)
        serializer = VarianteListSerializer(
            variantes,
            many=True,
            context=self.get_serializer_context()
        )
        return Response(serializer.data)


# ==============================================================================
# VIEWSET DE VARIANTE
# ==============================================================================

class VarianteViewSet(SerializerContextMixin, viewsets.ModelViewSet):
    """
    Endpoints de Variantes de producto.

    GET    /api/productos/variantes/       - Listar variantes
    POST   /api/productos/variantes/       - Crear variante (admin)
    GET    /api/productos/variantes/{id}/  - Detalle de variante
    PUT    /api/productos/variantes/{id}/  - Actualizar (admin)
    PATCH  /api/productos/variantes/{id}/  - Actualizar parcial (admin)
    """
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [
        django_filters.DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter
    ]
    filterset_fields = ["producto__slug", "esta_activo"]
    search_fields = ["=sku", "^nombre"]
    ordering_fields = ["nombre", "inventario"]
    ordering = ["nombre"]

    def get_queryset(self):
        queryset = Variante.objects.select_related("producto")
        if not self.request.user.is_staff:
            queryset = queryset.filter(esta_activo=True)
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return VarianteListSerializer
        return VarianteSerializer


# ==============================================================================
# VIEWSET DE IMAGEN
# ==============================================================================

class ImagenProductoViewSet(
    SerializerContextMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet
):
    """
    ViewSet restrictivo para imagenes.
    Solo permite subir, listar y borrar.
    No permite editar porque las imagenes se suben o se borran.

    POST   /api/productos/imagenes/              - Subir imagen (admin)
    GET    /api/productos/imagenes/              - Listar imagenes
    DELETE /api/productos/imagenes/{id}/         - Eliminar imagen (admin)
    PATCH  /api/productos/imagenes/{id}/marcar-principal/ - Marcar como principal
    """
    serializer_class = ImagenProductoSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [django_filters.DjangoFilterBackend]
    filterset_fields = ["producto__slug", "es_principal"]

    def get_queryset(self):
        queryset = ImagenProducto.objects.select_related("producto")
        if not self.request.user.is_staff:
            queryset = queryset.filter(esta_activo=True)
        return queryset

    @action(detail=True, methods=["patch"], url_path="marcar-principal")
    def marcar_principal(self, request, pk=None):
        """
        Marca una imagen como principal del producto.
        Automaticamente desmarca la imagen principal anterior.
        PATCH /api/productos/imagenes/{id}/marcar-principal/
        """
        imagen = self.get_object()
        imagen.es_principal = True
        imagen.save()
        return Response({
            "mensaje": f"Imagen marcada como principal del producto '{imagen.producto.nombre}'."
        })
