"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from decouple import config

from django.core.asgi import get_asgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    config("DJANGO_SETTINGS_MODULE", default="config.settings.prod"),
)

# Se inicializa Django ANTES de importar routing/consumers/middleware propios
# (que a su vez importan modelos). Si se importa antes de esta línea, Django
# todavía no registró las apps y explota con AppRegistryNotReady.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

import apps.notificaciones.routing
from apps.notificaciones.middleware import JWTAuthMiddleware

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddleware(
            URLRouter(apps.notificaciones.routing.websocket_urlpatterns)
        )
    ),
})