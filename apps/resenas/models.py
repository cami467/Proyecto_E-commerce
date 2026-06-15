from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from core.models import ModeloBase


class Resena(ModeloBase):
    """
    Reseña de un producto dejada por un usuario.

    Reglas de negocio:
        - Un usuario solo puede dejar una reseña por producto.
        - La calificacion debe ser entre 1 y 5 estrellas.
        - es_verificada indica si el usuario realmente compro el producto.
          Se calcula automaticamente al guardar.
    """
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="resenas"
    )
    producto = models.ForeignKey(
        "productos.Producto",
        on_delete=models.CASCADE,
        related_name="resenas"
    )
    calificacion = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5)
        ],
        help_text="Calificacion de 1 a 5 estrellas."
    )
    titulo = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Titulo opcional de la reseña."
    )
    comentario = models.TextField(
        blank=True,
        default="",
        help_text="Comentario detallado del producto."
    )
    es_verificada = models.BooleanField(
        default=False,
        help_text="True si el usuario compro el producto antes de reseñar."
    )

    class Meta:
        verbose_name = "Reseña"
        verbose_name_plural = "Reseñas"
        ordering = ["-fecha_creacion"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "producto"],
                name="unique_resena_por_usuario_producto"
            )
        ]
        indexes = [
            models.Index(
                fields=["producto", "esta_activo"],
                name="idx_resenas_producto_activo"
            )
        ]

    def __str__(self):
        return (
            f"{self.usuario.username} → "
            f"{self.producto.nombre} "
            f"({'⭐' * self.calificacion})"
        )

    def save(self, *args, **kwargs):
        """
        Calcula automaticamente si la resena es verificada.
        Verifica si el usuario tiene alguna orden confirmada
        que contenga el producto.
        """
        self.es_verificada = self._calcular_verificacion()
        super().save(*args, **kwargs)

    def _calcular_verificacion(self) -> bool:
        """
        Retorna True si el usuario compro el producto en
        alguna orden confirmada, enviada o entregada.
        """
        from apps.ordenes.models import Orden
        estados_validos = [
            Orden.Estado.CONFIRMED,
            Orden.Estado.PROCESSING,
            Orden.Estado.SHIPPED,
            Orden.Estado.DELIVERED,
        ]
        return Orden.objects.filter(
            usuario=self.usuario,
            estado__in=estados_validos,
            items__variante__producto=self.producto
        ).exists()

    @property
    def estrellas(self) -> str:
        """Retorna la calificacion como estrellas visuales."""
        return "⭐" * self.calificacion + "☆" * (5 - self.calificacion)