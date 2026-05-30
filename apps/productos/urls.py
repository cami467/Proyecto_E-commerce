from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# ==============================================================================
# ROUTER - Genera las URLs automaticamente para cada ViewSet
# ==============================================================================

router = DefaultRouter()

# Rutas para categorias: /categorias/
router.register(
    r"categorias",              # prefijo de la URL
    views.CategoriaViewSet,     # ViewSet asociado
    basename="categoria"        # nombre base para las rutas
)

# Rutas para variantes: /variantes/
router.register(
    r"variantes",
    views.VarianteViewSet,
    basename="variante"
)

# Rutas para imagenes: /imagenes/
router.register(
    r"imagenes",
    views.ImagenProductoViewSet,
    basename="imagen-producto"
)

# Rutas para productos: / (raíz del router)
router.register(
    r"",
    views.ProductoViewSet,
    basename="producto"
)

# ==============================================================================
# URLS FINALES
# ==============================================================================

urlpatterns = [
    # Incluye todas las rutas generadas por el router
    path("", include(router.urls)),
]
