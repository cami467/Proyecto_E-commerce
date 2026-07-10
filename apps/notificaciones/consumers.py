import json
from channels.generic.websocket import AsyncWebsocketConsumer


class NotificacionesConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        usuario = self.scope["user"]

        # Si el JWTAuthMiddleware no pudo autenticar (token inválido, ausente
        # o expirado), scope["user"] queda como AnonymousUser -> se rechaza.
        if not usuario or not usuario.is_authenticated:
            await self.close(code=4001)
            return

        self.grupo = f"notificaciones_usuario_{usuario.id}"
        await self.channel_layer.group_add(self.grupo, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # group_discard es seguro de llamar aunque connect() nunca haya
        # llegado a hacer group_add (por ejemplo, si rechazamos la conexión).
        if hasattr(self, "grupo"):
            await self.channel_layer.group_discard(self.grupo, self.channel_name)

    async def notificacion_nueva(self, event):
        """
        Este método se llama automáticamente cuando alguien (Celery, más
        adelante) hace channel_layer.group_send(..., {"type": "notificacion_nueva", ...}).
        El nombre del método DEBE coincidir con el "type" del evento
        (Channels convierte guiones bajos según el "type" recibido).
        """
        await self.send(text_data=json.dumps(event["data"]))