from django.urls import path
from . import views
from .views import CambiarPasswordView

urlpatterns = [
    path("registro/", views.RegistroView.as_view(), name="registro"),
    path("perfil/", views.PerfilView.as_view(), name="perfil"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("cambiar-password/", CambiarPasswordView.as_view(), name="cambiar-password"),
]