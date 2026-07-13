from decimal import Decimal
from django.db.models import Sum
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import get_user_model
from apps.ordenes.models import Orden
from apps.pagos.models import Pago

from .serializers import (
    EmailTokenObtainPairSerializer,
    LogoutSerializer,
    RegistroSerializer,
    UsuarioSerializer,
    UsuarioAdminSerializer,
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

    Usa throttling para limitar intentos repetidos desde la misma IP.
    Esto reduce el riesgo de ataques de fuerza bruta sobre contraseñas.
    """
    serializer_class = EmailTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

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
        

class CambiarPasswordView(APIView):
    """
    Endpoint para cambiar la contraseña del usuario autenticado.
    Requiere autenticación.
    POST /api/usuarios/cambiar-password/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        usuario = request.user
        password_actual = request.data.get("password_actual")
        password_nueva = request.data.get("password_nueva")

        if not usuario.check_password(password_actual):
            return Response(
                {"error": "La contraseña actual es incorrecta"},
                status=status.HTTP_400_BAD_REQUEST
            )

        usuario.set_password(password_nueva)
        usuario.save()
        return Response(
            {"mensaje": "Contraseña cambiada correctamente"},
            status=status.HTTP_200_OK
        )


class UsuarioAdminListView(generics.ListAPIView):
    """
    Lista los usuarios registrados.

    Solo puede acceder un usuario administrador.
    GET /api/usuarios/
    """

    serializer_class = UsuarioAdminSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return (
            Usuario.objects
            .all()
            .order_by("-date_joined")
        )
        
class DashboardClienteView(APIView):
    """
    Devuelve el resumen personal del usuario autenticado.

    GET /api/usuarios/dashboard/
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        usuario = request.user

        ordenes = (
            Orden.objects
            .filter(usuario=usuario)
            .order_by("-fecha_creacion")
        )

        pagos = (
            Pago.objects
            .filter(orden__usuario=usuario)
            .order_by("-fecha_creacion")
        )

        pagos_aprobados = pagos.filter(
            estado=Pago.Estado.APPROVED
        )

        dinero_gastado = (
            pagos_aprobados.aggregate(
                total=Sum("monto")
            )["total"]
            or Decimal("0")
        )

        ultima_orden = ordenes.first()
        ultimo_pago = pagos.first()

        ultima_compra_data = None

        if ultima_orden:
            ultima_compra_data = {
                "id": str(ultima_orden.id),
                "numero_orden": ultima_orden.numero_orden_display,
                "estado": ultima_orden.estado,
                "estado_display": ultima_orden.get_estado_display(),
                "total": ultima_orden.total,
                "fecha_creacion": ultima_orden.fecha_creacion,
            }

        ultimo_pago_data = None

        if ultimo_pago:
            ultimo_pago_data = {
                "id": str(ultimo_pago.id),
                "orden_id": str(ultimo_pago.orden_id),
                "pasarela": ultimo_pago.pasarela,
                "pasarela_display": ultimo_pago.get_pasarela_display(),
                "estado": ultimo_pago.estado,
                "estado_display": ultimo_pago.get_estado_display(),
                "monto": ultimo_pago.monto,
                "fecha_creacion": ultimo_pago.fecha_creacion,
                "fecha_procesado": ultimo_pago.fecha_procesado,
            }

        return Response(
            {
                "pedidos_realizados": ordenes.count(),
                "dinero_gastado": dinero_gastado,
                "productos_favoritos": 0,
                "ultima_compra": ultima_compra_data,
                "ultimo_pago": ultimo_pago_data,
            }
        )