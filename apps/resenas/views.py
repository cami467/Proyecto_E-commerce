from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db.models import Avg, Count

from core.permissions import IsOwnerOrReadOnly
from .models import Resena
from .serializers import (
    ResenaSerializer,
    ResenaListSerializer,
    CrearResenaSerializer,
)


# ==============================================================================
# VIEWSET DE RESEÑAS
# ==============================================================================

class ResenaViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo para reseñas de productos.

    Endpoints:
        GET    /api/resenas/              - Listar reseñas activas
        POST   /api/resenas/              - Crear reseña
        GET    /api/resenas/{id}/         - Detalle de reseña
        PATCH  /api/resenas/{id}/         - Editar mi reseña
        DELETE /api/resenas/{id}/         - Eliminar mi reseña

    Seguridad:
        - Cualquiera puede leer reseñas (AllowAny en list y retrieve).
        - Solo usuarios autenticados pueden crear reseñas.
        - Solo el dueño puede editar o eliminar su propia reseña.
        - Admins pueden ver y moderar todas las reseñas.

    Filtros disponibles:
        - ?producto={uuid}     → reseñas de un producto específico
        - ?calificacion={1-5}  → reseñas por calificación
        - ?es_verificada=true  → solo reseñas verificadas
        - ?ordering=-calificacion → ordenar por calificación
    """
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["^producto__nombre", "titulo", "comentario"]
    ordering_fields = ["calificacion", "fecha_creacion"]
    ordering = ["-fecha_creacion"]

    def get_queryset(self):
        """
        Usuarios normales ven solo reseñas activas.
        Admins ven todas las reseñas para moderación.
        Soporta filtrado por producto y calificación via query params.
        """
        if self.request.user.is_staff:
            queryset = Resena.objects.all()
        else:
            queryset = Resena.objects.filter(esta_activo=True)

        queryset = queryset.select_related(
            "usuario", "producto"
        )

        # Filtro por producto
        producto_id = self.request.query_params.get("producto")
        if producto_id:
            queryset = queryset.filter(producto__id=producto_id)

        # Filtro por calificación
        calificacion = self.request.query_params.get("calificacion")
        if calificacion and calificacion.isdigit():
            queryset = queryset.filter(calificacion=int(calificacion))

        # Filtro por verificada
        es_verificada = self.request.query_params.get("es_verificada")
        if es_verificada is not None:
            valor = es_verificada.lower() == "true"
            queryset = queryset.filter(es_verificada=valor)

        return queryset

    def get_permissions(self):
        """
        Permisos dinámicos según la acción:
        - list y retrieve: cualquiera puede leer.
        - create: solo usuarios autenticados.
        - update, partial_update, destroy: solo el dueño.
        """
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        if self.action == "create":
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsOwnerOrReadOnly()]

    def get_serializer_class(self):
        if self.action == "list":
            return ResenaListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return CrearResenaSerializer
        return ResenaSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def create(self, request, *args, **kwargs):
        """
        Crea una reseña y retorna el detalle completo.
        La verificación de compra se calcula automáticamente.
        """
        serializer = CrearResenaSerializer(
            data=request.data,
            context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        resena = serializer.save()

        response_serializer = ResenaSerializer(
            resena,
            context=self.get_serializer_context()
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        """
        Actualiza una reseña y recalcula la verificación de compra.
        """
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        serializer = CrearResenaSerializer(
            instance,
            data=request.data,
            partial=partial,
            context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        resena = serializer.save()

        response_serializer = ResenaSerializer(
            resena,
            context=self.get_serializer_context()
        )
        return Response(response_serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        Elimina una reseña y retorna mensaje de confirmación.
        """
        resena = self.get_object()
        resena.delete()
        return Response(
            {"mensaje": "Reseña eliminada exitosamente."},
            status=status.HTTP_200_OK
        )