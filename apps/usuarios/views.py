from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .serializers import RegistroSerializer, UsuarioSerializer

Usuario = get_user_model()


class RegistroView(generics.CreateAPIView):
    """
    Endpoint para registrar un nuevo usuario.
    No requiere autenticacion.
    POST /api/usuarios/registro/
    """
    serializer_class = RegistroSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.save()
        return Response(
            {
                "mensaje": "Usuario registrado exitosamente.",
                "usuario": UsuarioSerializer(
                    usuario,
                    context={"request": request}
                ).data
            },
            status=status.HTTP_201_CREATED
        )


class PerfilView(generics.RetrieveUpdateAPIView):
    """
    Endpoint para ver y actualizar el perfil del usuario autenticado.
    Requiere autenticacion.
    GET   /api/usuarios/perfil/
    PUT   /api/usuarios/perfil/
    PATCH /api/usuarios/perfil/
    """
    serializer_class = UsuarioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Retorna el usuario que hace la peticion directamente."""
        return self.request.user

    def update(self, request, *args, **kwargs):
        """Sobrescribe la respuesta para mantener consistencia."""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(
            {
                "mensaje": "Perfil actualizado exitosamente.",
                "usuario": serializer.data
            },
            status=status.HTTP_200_OK
        )