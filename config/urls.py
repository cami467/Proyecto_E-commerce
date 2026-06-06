from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from rest_framework_simplejwt.views import (
    TokenObtainPairView,   # Vista para obtener access y refresh token (login)
    TokenRefreshView,      # Vista para renovar el access token
)
from drf_spectacular.views import (
    SpectacularAPIView,        #  Genera el esquema OpenAPI en formato JSON/YAML
    SpectacularSwaggerView,    #  Documentación interactiva con Swagger UI
    SpectacularRedocView,      #  Documentación alternativa con Redoc
)


urlpatterns = [
    #  Panel de administración de Django
    path("admin/", admin.site.urls),

     # JWT - Login y refresh de token
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),   # Login: devuelve access y refresh token
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),  # Refresca el access token

    #  Documentación automática de la API con drf-spectacular
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),              # Esquema OpenAPI (JSON/YAML)
    path("api/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),  # Swagger UI interactivo
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),           # Redoc UI alternativa

    #  Rutas de la app "usuarios"
    path("api/usuarios/", include("apps.usuarios.urls")),  # Incluye las rutas definidas en apps/usuarios/urls.py
    path("api/productos/", include("apps.productos.urls")),  # Incluye las rutas definidas en apps/productos/urls.py
    path("api/carrito/", include("apps.carrito.urls")),  # Incluye las rutas definidas en apps/carrito/urls.py
    path("api/ordenes/", include("apps.ordenes.urls")),  # Incluye las rutas definidas en apps/ordenes/urls.py
]

# En desarrollo, sirve archivos estáticos y de medios desde sus directorios configurados
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
