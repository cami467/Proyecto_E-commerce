from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from core.models import ModeloBase
from core.exceptions import CarritoVacio, StockInsuficiente


# ==============================================================================
# EXCEPCIONES PROPIAS DE ORDENES
# ==============================================================================

class OrdenNoCancelable(Exception):
    """Se lanza cuando el estado actual impide la cancelacion."""
    pass


class OrdenNoConfirmable(Exception):
    """Se lanza cuando la orden no cumple requisitos para confirmarse."""
    pass


# ==============================================================================
# MANAGERS
# ==============================================================================

class OrdenManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related("usuario")


class ItemOrdenManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related(
            "variante",
            "variante__producto"
        )


# ==============================================================================
# MODELOS
# ==============================================================================

class Orden(ModeloBase):
    """
    Orden de compra confirmada.
    Una vez creada los precios quedan congelados.
    Incluye historial completo de cambios de estado.
    """
    class Estado(models.TextChoices):
        PENDING = "pending", "Pendiente"
        CONFIRMED = "confirmed", "Confirmada"
        PROCESSING = "processing", "En proceso"
        SHIPPED = "shipped", "Enviada"
        DELIVERED = "delivered", "Entregada"
        CANCELLED = "cancelled", "Cancelada"
        REFUNDED = "refunded", "Reembolsada"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ordenes",
        db_index=True
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDING,
        db_index=True
    )
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=0, default=0
    )
    monto_descuento = models.DecimalField(
        max_digits=12, decimal_places=0, default=0
    )
    costo_envio = models.DecimalField(
        max_digits=12, decimal_places=0, default=0
    )
    total = models.DecimalField(
        max_digits=12, decimal_places=0, default=0
    )
    codigo_cupon = models.CharField(max_length=50, blank=True, default="")
    notas = models.TextField(blank=True, default="")

    objects = OrdenManager()

    class Meta:
        verbose_name = "Orden"
        verbose_name_plural = "Ordenes"
        ordering = ["-fecha_creacion"]
        indexes = [
            models.Index(fields=["usuario", "estado"]),
        ]

    def __str__(self):
        identificador = str(self.id)[:8] if self.id else "Nueva"
        return f"Orden #{identificador} - {self.usuario.username} - {self.get_estado_display()}"

    @property
    def puede_cancelarse(self):
        return self.estado in [self.Estado.PENDING, self.Estado.CONFIRMED]

    @property
    def puede_confirmarse(self):
        return self.estado == self.Estado.PENDING
    
    @property
    def numero_orden_display(self) -> str:
        """
        Identificador legible de la orden para mostrar al usuario.
        Usa los primeros 8 caracteres del UUID en mayúsculas.
        Ejemplo: #A3F2B1C4
        """
        return f"#{str(self.id)[:8].upper()}" if self.id else "#NUEVA"
    

    def _cambiar_estado(self, nuevo_estado, usuario_accion=None, comentario=""):
        """
        Cambia el estado de la orden y registra el historial.
        Siempre usar este metodo para cambiar estados.
        """
        estado_anterior = self.estado
        self.estado = nuevo_estado
        self.fecha_actualizacion = timezone.now()
        self.save(update_fields=["estado", "fecha_actualizacion"])

        HistorialEstadoOrden.objects.create(
            orden=self,
            estado_anterior=estado_anterior,
            estado_nuevo=nuevo_estado,
            cambiado_por=usuario_accion or self.usuario,
            comentario=comentario
        )

    def cancelar(self, usuario_accion=None, comentario=""):
        """
        Cancela la orden y devuelve el stock.
        """
        if not self.puede_cancelarse:
            raise OrdenNoCancelable(
                f"No se puede cancelar una orden en estado "
                f"'{self.get_estado_display()}'."
            )
        with transaction.atomic():
            items = self.items.select_related(
                "variante"
            ).select_for_update(of=("variante",))

            for item in items:
                item.variante.incrementar_stock(item.cantidad)

            self._cambiar_estado(
                self.Estado.CANCELLED,
                usuario_accion,
                comentario or "Orden cancelada."
            )
            
        # Notificar al usuario de forma asincrona 
        from apps.notificaciones.tasks import notificar_orden_cancelada
        notificar_orden_cancelada.delay(
            usuario_id=self.usuario.pk,
            orden_id=str(self.id),
            numero_orden=self.numero_orden_display,
        )

    @classmethod
    def crear_desde_carrito(
        cls,
        carrito,
        usuario_accion=None,
        costo_envio=0,
        monto_descuento=0,
        codigo_cupon="",
        notas=""
    ):
        """
        Crea una orden desde el carrito del usuario.
        Usa bulk_create para insertar todos los items en una sola query.
        """
        with transaction.atomic():
            items_carrito = list(
                carrito.items
                .select_related("variante", "variante__producto")
                .select_for_update(of=("variante",))
                .filter(esta_activo=True)
            )

            if not items_carrito:
                raise CarritoVacio("El carrito no contiene productos.")

            # Validar stock de todos los items
            for item in items_carrito:
                if item.variante.inventario < item.cantidad:
                    raise StockInsuficiente(
                        producto=item.variante.nombre,
                        disponible=item.variante.inventario
                    )

            # Calcular subtotal
            subtotal = sum(
                item.variante.precio_total * item.cantidad
                for item in items_carrito
            )
            total = subtotal - Decimal(str(monto_descuento)) + Decimal(str(costo_envio))

            # Crear la orden
            orden = cls.objects.create(
                usuario=carrito.usuario,
                estado=cls.Estado.CONFIRMED,
                subtotal=subtotal,
                total=total,
                costo_envio=costo_envio,
                monto_descuento=monto_descuento,
                codigo_cupon=codigo_cupon,
                notas=notas, 
            )

            # Crear items y actualizar stock en lote
            items_orden = []
            variantes_a_actualizar = []

            for item in items_carrito:
                items_orden.append(
                    ItemOrden(
                        orden=orden,
                        variante=item.variante,
                        cantidad=item.cantidad,
                        precio_unitario=item.variante.precio_total,
                        nombre_producto=item.variante.producto.nombre,
                        nombre_variante=item.variante.nombre,
                    )
                )
                item.variante.inventario -= item.cantidad
                variantes_a_actualizar.append(item.variante)

            # Insercion masiva - una sola query
            ItemOrden.objects.bulk_create(items_orden)

            # Actualizacion masiva de stock - una sola query
            from apps.productos.models import Variante
            Variante.objects.bulk_update(
                variantes_a_actualizar,
                fields=["inventario"]
            )

            # Registrar en el historial
            HistorialEstadoOrden.objects.create(
                orden=orden,
                estado_anterior=cls.Estado.PENDING,
                estado_nuevo=cls.Estado.CONFIRMED,
                cambiado_por=usuario_accion or carrito.usuario,
                comentario="Orden creada desde el carrito."
            )
            # Limpiar el carrito
            carrito.items.all().delete()
            
             # Notificar al usuario de forma asincrona 
            from apps.notificaciones.tasks import notificar_orden_confirmada
            notificar_orden_confirmada.delay(
                usuario_id=orden.usuario.pk,
                orden_id=str(orden.id),
                numero_orden=orden.numero_orden_display,
                total=orden.total,
            )
            return orden


class ItemOrden(ModeloBase):
    """
    Item dentro de una orden con precio congelado.
    Guarda snapshot del nombre del producto y variante
    para preservar la historia aunque cambien despues.
    """
    orden = models.ForeignKey(
        Orden,
        on_delete=models.CASCADE,
        related_name="items"
    )
    variante = models.ForeignKey(
        "productos.Variante",
        on_delete=models.PROTECT,
        related_name="items_orden"
    )
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=0
    )
    nombre_producto = models.CharField(max_length=255)
    nombre_variante = models.CharField(max_length=255)

    objects = ItemOrdenManager()

    class Meta:
        verbose_name = "Item de Orden"
        verbose_name_plural = "Items de Orden"
        ordering = ["fecha_creacion"]

    def __str__(self):
        identificador = str(self.orden.id)[:8] if self.orden_id else "S/O"
        return f"{self.cantidad}x {self.nombre_variante} en Orden #{identificador}"

    @property
    def subtotal(self):
        return Decimal(str(self.precio_unitario)) * self.cantidad


class HistorialEstadoOrden(ModeloBase):
    """
    Registra cada cambio de estado de una orden.
    Permite saber quien cambio el estado, cuando y desde donde.
    """
    orden = models.ForeignKey(
        Orden,
        on_delete=models.CASCADE,
        related_name="historial_estados"
    )
    estado_anterior = models.CharField(
        max_length=20,
        choices=Orden.Estado.choices,
        null=True,
        blank=True
    )
    estado_nuevo = models.CharField(
        max_length=20,
        choices=Orden.Estado.choices
    )
    cambiado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )
    fecha = models.DateTimeField(default=timezone.now)
    comentario = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Historial de Estado"
        verbose_name_plural = "Historial de Estados"
        ordering = ["-fecha"]

    def __str__(self):
        return (
            f"Orden #{str(self.orden.id)[:8]} "
            f"{self.estado_anterior} → {self.estado_nuevo}"
        )