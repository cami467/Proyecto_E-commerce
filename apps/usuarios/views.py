from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import get_user_model

from .serializers import (
    EmailTokenObtainPairSerializer,
    LogoutSerializer,
    RegistroSerializer,
    UsuarioSerializer,
)

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

class LoginEmailView(TokenObtainPairView):
    """
    Endpoint para iniciar sesión con email y password.
    No requiere autenticación.
    POST /api/token/
    """
    serializer_class = EmailTokenObtainPairSerializer

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
        
class LogoutView(APIView):
    """
    Endpoint para cerrar sesion invalidando el refresh token.
    Requiere autenticacion (access token valido) para evitar
    que cualquiera blacklistee tokens ajenos sin estar logueado.
    POST /api/usuarios/logout/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
        except TokenError:
            return Response(
                {"detail": "El refresh token es invalido o ya fue invalidado."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"mensaje": "Sesion cerrada exitosamente."},
            status=status.HTTP_200_OK
        )