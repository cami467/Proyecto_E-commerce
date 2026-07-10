from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from urllib.parse import parse_qs


@database_sync_to_async
def obtener_usuario_desde_token(token_str):
    """
    Valida el access token de SimpleJWT y devuelve el usuario correspondiente.
    Si el token es inválido, expiró, o el usuario no existe, devuelve AnonymousUser.
    """
    try:
        token = AccessToken(token_str)
        User = get_user_model()
        return User.objects.get(id=token["user_id"])
    except Exception:
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    Middleware ASGI que autentica conexiones WebSocket usando un JWT
    pasado como query param: ws://.../ws/notificaciones/?token=<access_token>

    Se ubica "delante" del AuthMiddlewareStack de Channels en asgi.py,
    y le agrega scope["user"] antes de que la conexión llegue al Consumer.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token_list = params.get("token")

        if token_list:
            scope["user"] = await obtener_usuario_desde_token(token_list[0])
        else:
            scope["user"] = AnonymousUser()

        return await self.app(scope, receive, send)