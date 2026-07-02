from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Sum

from core.models import ModeloBase
from core.exceptions import StockInsuficiente


class Carrito(ModeloBase):
    """
    Carrito de compras del usuario.
    Cada usuario posee un unico carrito.
    Se crea automaticamente al primer acceso.
    """
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carrito"
    )

    class Meta:
        verbose_name = "Carrito"
        verbose_name_plural = "Carritos"

    def __str__(self):
        identificador = getattr(self.usuario, "email", None) or self.usuario.username
        return f"Carrito de {identificador}"

    def obtener_items_activos(self):
        """
        Centraliza la obtencion de items activos.
        Principio DRY - evita repetir el filtro en cada metodo.
        """
        return self.items.filter(esta_activo=True)

    @property
    def total(self):
        """
        Calcula el total del carrito en memoria.
        precio_total es una @property de Python, no un campo SQL,
        por lo que no puede usarse en aggregate directamente.
        Usa select_related para evitar N+1 queries.
        """
        items = self.obtener_items_activos().select_related(
            "variante__producto"
        )
        return sum(
            item.variante.precio_total * item.cantidad
            for item in items
        )

    @property
    def cantidad_items(self):
        """
        Retorna la cantidad total de unidades en el carrito.
        Usa aggregate porque cantidad SI es un campo SQL real.
        """
        resultado = self.obtener_items_activos().aggregate(
            total_unidades=Sum("cantidad")
        )
        return resultado["total_unidades"] or 0

    def vaciar(self):
        """Elimina fisicamente todos los items del carrito."""
        self.items.all().delete()

    def agregar_o_actualizar_item(self, variante, cantidad=1):
        """
        Agrega o actualiza un item dentro del carrito de manera segura.
        Si el item ya existe suma la cantidad.
        Si es nuevo lo crea con la cantidad indicada.
        La operacion bloquea la variante para reducir condiciones de carrera.
        """
        if cantidad <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero.")

        with transaction.atomic():
            variante_bloqueada = (
                variante.__class__.objects
                .select_for_update()
                .get(pk=variante.pk, esta_activo=True)
            )

            item = (
                ItemCarrito.objects
                .select_for_update()
                .filter(carrito=self, variante=variante_bloqueada)
                .first()
            )

            if item is None:
                try:
                    item = ItemCarrito.objects.create(
                        carrito=self,
                        variante=variante_bloqueada,
                        cantidad=0,
                    )
                except IntegrityError:
                    item = (
                        ItemCarrito.objects
                        .select_for_update()
                        .get(carrito=self, variante=variante_bloqueada)
                    )

            item.actualizar_cantidad(item.cantidad + cantidad)
            return item


class ItemCarrito(ModeloBase):
    """
    Item dentro del carrito de compras.
    Representa una variante con una cantidad determinada.
    La misma variante no puede aparecer dos veces en el mismo carrito.
    """
    carrito = models.ForeignKey(
        Carrito,
        on_delete=models.CASCADE,
        related_name="items"
    )
    variante = models.ForeignKey(
        "productos.Variante",
        on_delete=models.CASCADE,
        related_name="items_carrito"
    )
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Item de Carrito"
        verbose_name_plural = "Items de Carrito"
        ordering = ["-fecha_creacion"]
        constraints = [
            models.UniqueConstraint(
                fields=["carrito", "variante"],
                name="unique_variante_por_carrito"
            )
        ]
        indexes = [
            models.Index(
                fields=["carrito", "esta_activo"],
                name="idx_carrito_items_activos"
            )
        ]

    def __str__(self):
        identificador = (
            getattr(self.carrito.usuario, "email", None)
            or self.carrito.usuario.username
        )
        return f"{self.cantidad}x {self.variante.nombre} en carrito de {identificador}"

    def clean(self):
        """Valida reglas basicas del item antes de persistirlo."""
        super().clean()
        if self.cantidad <= 0:
            raise ValidationError({
                "cantidad": "La cantidad debe ser mayor a cero."
            })
        if self.variante_id and not self.variante.esta_activo:
            raise ValidationError({
                "variante": "La variante no esta disponible."
            })

    @property
    def subtotal(self):
        """Calcula el subtotal del item (precio x cantidad)."""
        return self.variante.precio_total * self.cantidad

    def obtener_variante_bloqueada(self):
        """
        Obtiene la variante bloqueando la fila en la base de datos.
        Evita condiciones de carrera cuando dos usuarios compran
        la misma variante al mismo tiempo.
        Solo funciona dentro de una transaccion atomica.
        """
        return (
            self.variante.__class__.objects
            .select_for_update()
            .get(pk=self.variante_id)
        )

    def validar_stock(self, cantidad):
        """
        Verifica disponibilidad de stock con bloqueo defensivo.
        Lanza StockInsuficiente si no hay suficiente stock.
        """
        variante = self.obtener_variante_bloqueada()
        if not variante.esta_activo:
            raise ValidationError("La variante no esta disponible.")
        if variante.inventario < cantidad:
            raise StockInsuficiente(
                producto=variante.nombre,
                disponible=variante.inventario
            )
        return variante

    def actualizar_cantidad(self, nueva_cantidad):
        """
        Actualiza la cantidad del item de manera atomica.
        Si la cantidad es 0 o menos elimina el item automaticamente.
        """
        if nueva_cantidad <= 0:
            self.delete()
            return

        with transaction.atomic():
            self.validar_stock(nueva_cantidad)
            self.cantidad = nueva_cantidad
            self.full_clean()
            self.save(update_fields=[
                "cantidad",
                "fecha_actualizacion"
            ])
