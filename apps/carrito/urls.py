from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# ==============================================================================
# ROUTER - Genera las URLs automaticamente
# ==============================================================================

router = DefaultRouter()

router.register(
    r"items",
    views.ItemCarritoViewSet,
    basename="carrito-item"
)

router.register(
    r"",
    views.CarritoViewSet,
    basename="carrito"
)

urlpatterns = [
    path("", include(router.urls)),
]