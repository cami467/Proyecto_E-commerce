from django.conf import settings
from django.db import models
from core.models import ModeloBase


class Notificacion(ModeloBase):
    """
    Notificación dirigida a un usuario sobre un evento del sistema.

    Se crean de forma asíncrona mediante tareas de Celery para no
    bloquear el request que dispara el evento (ej: crear una orden
    no debe esperar a que se genere la notificación).
    """

    class Tipo(models.TextChoices):
        ORDEN_CONFIRMADA  = "orden_confirmada",  "Orden confirmada"
        ORDEN_CANCELADA   = "orden_cancelada",   "Orden cancelada"
        PAGO_APROBADO     = "pago_aprobado",     "Pago aprobado"
        PAGO_RECHAZADO    = "pago_rechazado",    "Pago rechazado"
        RESENA_RECIBIDA   = "resena_recibida",   "Reseña recibida"
        SISTEMA           = "sistema",           "Notificación del sistema"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificaciones",
        db_index=True
    )
    tipo = models.CharField(
        max_length=30,
        choices=Tipo.choices,
        default=Tipo.SISTEMA
    )
    titulo = models.CharField(
        max_length=200,
        help_text="Título corto de la notificación."
    )
    mensaje = models.TextField(
        help_text="Contenido detallado de la notificación."
    )
    leida = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True una vez que el usuario la marcó como leída."
    )
    fecha_leida = models.DateTimeField(
        null=True,
        blank=True
    )
    # Referencia genérica opcional al objeto relacionado (orden, pago, etc.)
    referencia_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="UUID del objeto relacionado (orden, pago, reseña)."
    )

    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ["-fecha_creacion"]
        indexes = [
            models.Index(fields=["usuario", "leida"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} → {self.usuario.username}: {self.titulo}"

    def marcar_leida(self) -> None:
        """Marca la notificación como leída y registra la fecha."""
        from django.utils import timezone
        if not self.leida:
            self.leida = True
            self.fecha_leida = timezone.now()
            self.save(update_fields=["leida", "fecha_leida", "fecha_actualizacion"])