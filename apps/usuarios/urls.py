from django.urls import path
from . import views
from .views import CambiarPasswordView
from .views import UsuarioAdminListView

urlpatterns = [
    path("registro/", views.RegistroView.as_view(), name="registro"),
    path("perfil/", views.PerfilView.as_view(), name="perfil"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("cambiar-password/", CambiarPasswordView.as_view(), name="cambiar-password"),
    path("dashboard/", views.DashboardClienteView.as_view(), name="dashboard-cliente"),
    path("", UsuarioAdminListView.as_view(), name="usuarios-admin-list"),
    
]