import uuid
from django.db import models

class ActivosQuerySet(models.QuerySet):
    """QuerySet personalizado para permitir acciones en lote (bulk actions)."""
    
    def desactivar(self):
        """Desactiva todos los registros del queryset actual en una sola consulta."""
        return self.update(esta_activo=False)
    
    def activar(self):
        """Activa todos los registros del queryset actual en una sola consulta."""
        return self.update(esta_activo=True)
    
class ActivosManager(models.Manager):
    """Manager que devuelve solo registros activos."""
    
    def get_queryset(self):
        # Usamos nuestro QuerySet personalizado
        return ActivosQuerySet(self.model, using=self._db).filter(esta_activo=True)
class ModeloBase(models.Model):
    """
    Clase abstracta que provee campos comunes y soporte para borrado lógico.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_index=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    esta_activo = models.BooleanField(default=True)
    # Managers
    objects = models.Manager()        # Acceso a absolutamente todos los registros
    activos = ActivosManager()        # Acceso simplificado a registros activos
    class Meta:
        abstract = True
        ordering = ["-fecha_creacion"]
    # --- MEJORA: Métodos directos en la instancia ---
    
    def desactivar(self):
        """Desactiva esta instancia en particular."""
        self.esta_activo = False
        self.save(update_fields=['esta_activo', 'fecha_actualizacion'])
        
    def activar(self):
        """Activa esta instancia en particular."""
        self.esta_activo = True
        self.save(update_fields=['esta_activo', 'fecha_actualizacion']) 