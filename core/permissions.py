from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwner(BasePermission):
    """
    Solo el dueño del objeto puede acceder.
    Usado en: carrito, perfil de usuario.
    """
    def has_permission(self, request, view):
        # Bloquea de inmediato si el usuario no está autenticado
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return obj.usuario == request.user


class IsOwnerOrReadOnly(BasePermission):
    """
    Cualquiera puede leer, solo el dueño puede modificar.
    Usado en: reseñas.
    """
    def has_permission(self, request, view):
        # Lectura libre, escritura solo para autenticados
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        # Para modificar debe estar autenticado y ser el dueño
        return bool(
            request.user and
            request.user.is_authenticated and
            obj.usuario == request.user
        )


class IsAdminOrReadOnly(BasePermission):
    """
    Cualquiera puede leer, solo el admin puede modificar.
    Usado en: productos, categorias.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        # Solo admins autenticados pueden modificar
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_staff
        )