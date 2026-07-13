from django.urls import path

from .admin_views import EstadisticasAdminView


urlpatterns = [
    path(
        "estadisticas/",
        EstadisticasAdminView.as_view(),
        name="estadisticas-admin",
    ),
]