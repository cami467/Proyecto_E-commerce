from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .webhooks import StripeWebhookView

router = DefaultRouter()

router.register(
    r"",
    views.PagoViewSet,
    basename="pago"
)

urlpatterns = [
    # Vive fuera del router a propósito: es una vista Django plana,
    # sin JWT, protegida por verificación de firma de Stripe.
    path("webhook/stripe/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("", include(router.urls)),
]