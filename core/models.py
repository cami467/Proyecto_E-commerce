import uuid
from django.db import models


class ActivosManager(models.Manager):
    """Manager que devuelve solo registros activos."""

    def get_queryset(self):
        return super().get_queryset().filter(esta_activo=True)


class ModeloBase(models.Model):
    """
    Clase abstracta que provee campos comunes:
    - UUID como clave primaria
    - Fechas de creación y actualización
    - Estado activo/inactivo
    - Manager para filtrar solo activos
    """

    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_index=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    esta_activo = models.BooleanField(default=True)

    # Managers personalizados
    objects = models.Manager()  # Manager por defecto (devuelve todo)
    activos = ActivosManager()  # Manager que devuelve solo activos

    class Meta:
        abstract = True
        ordering = ["-fecha_creacion"]  # Orden por defecto: más recientes primero
