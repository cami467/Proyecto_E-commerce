from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.utils import timezone

from core.models import ModeloBase


class Pago(ModeloBase):
    """
    Registro de cada intento de pago asociado a una orden.

    Un pago representa un intento de cobro con una pasarela especifica.
    Una orden puede tener multiples pagos si los anteriores fueron rechazados.
    Solo puede haber un pago aprobado por orden.
    """

    class Pasarela(models.TextChoices):
        STRIPE = "stripe", "Stripe"
        MERCADO_PAGO = "mercado_pago", "Mercado Pago"
        EFECTIVO = "efectivo", "Efectivo"
        TRANSFERENCIA = "transferencia", "Transferencia Bancaria"

    class Estado(models.TextChoices):
        PENDING = "pending", "Pendiente"
        APPROVED = "approved", "Aprobado"
        REJECTED = "rejected", "Rechazado"
        REFUNDED = "refunded", "Reembolsado"
        CANCELLED = "cancelled", "Cancelado"

    orden = models.ForeignKey(
        "ordenes.Orden",
        on_delete=models.PROTECT,
        related_name="pagos"
    )
    pasarela = models.CharField(
        max_length=20,
        choices=Pasarela.choices,
        db_index=True
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDING,
        db_index=True
    )
    monto = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        help_text="Monto del pago en Guaranies."
    )
    id_transaccion = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="ID de la transaccion en la pasarela de pago."
    )
    respuesta_pasarela = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="Respuesta completa de la pasarela para auditoria."
    )
    fecha_procesado = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha en que la pasarela proceso el pago."
    )
    comprobante = models.FileField(
        upload_to="comprobantes/",
        null=True,
        blank=True,
        help_text=(
            "Comprobante de transferencia subido por el cliente "
            "(imagen o PDF). Se usa FileField en lugar de ImageField "
            "porque tambien debe aceptar PDF, que ImageField rechazaria."
        ),
    )
    referencia_cliente = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Numero de referencia u operacion que el cliente indica al transferir.",
    )
    observacion_cliente = models.TextField(
        blank=True,
        default="",
        help_text="Comentario opcional del cliente sobre la transferencia realizada.",
    )

    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ["-fecha_creacion"]
        indexes = [
            models.Index(fields=["orden", "estado"]),
            models.Index(fields=["pasarela", "id_transaccion"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(monto__gte=1),
                name="pago_monto_mayor_a_cero",
            ),
            models.UniqueConstraint(
                fields=["orden"],
                condition=models.Q(estado="approved"),
                name="un_pago_aprobado_por_orden",
            ),
            models.UniqueConstraint(
                fields=["pasarela", "id_transaccion"],
                condition=~models.Q(id_transaccion=""),
                name="transaccion_unica_por_pasarela",
            ),
        ]

    def __str__(self):
        return (
            f"Pago {self.get_pasarela_display()} - "
            f"{self.get_estado_display()} - "
            f"Gs. {self.monto:,.0f}"
        )

    def clean(self):
        """Validaciones de negocio a nivel de modelo."""
        super().clean()
        if self.monto is not None and self.monto <= 0:
            raise ValidationError({
                "monto": "El monto del pago debe ser mayor a cero."
            })

        if self.orden_id and self.monto is not None and self.monto != self.orden.total:
            raise ValidationError({
                "monto": "El monto del pago debe coincidir con el total de la orden."
            })

        if self.id_transaccion:
            self.id_transaccion = self.id_transaccion.strip().upper()

    def save(self, *args, **kwargs):
        """
        Ejecuta validaciones de modelo antes de guardar.
        En pagos conviene no permitir registros inconsistentes ni siquiera
        cuando se creen desde código interno.
        """
        self.full_clean()
        return super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # PROPIEDADES
    # ------------------------------------------------------------------

    @property
    def es_exitoso(self):
        """Retorna True si el pago fue aprobado."""
        return self.estado == self.Estado.APPROVED

    @property
    def esta_pendiente(self):
        """Retorna True si el pago esta esperando ser procesado."""
        return self.estado == self.Estado.PENDING

    @property
    def es_reembolsable(self):
        """Retorna True si el pago puede ser reembolsado."""
        return self.estado == self.Estado.APPROVED

    # ------------------------------------------------------------------
    # METODOS DE TRANSICION DE ESTADO
    # ------------------------------------------------------------------

    def _actualizar_estado(self, nuevo_estado, campos_extra=None):
        """Actualiza el estado y datos de auditoria."""
        ahora = timezone.now()
        self.estado = nuevo_estado
        self.fecha_procesado = ahora
        self.fecha_actualizacion = ahora

        campos = ["estado", "fecha_procesado", "fecha_actualizacion"]
        if campos_extra:
            for campo, valor in campos_extra.items():
                setattr(self, campo, valor)
                campos.append(campo)

        self.save(update_fields=campos)

    def marcar_aprobado(self, id_transaccion="", respuesta=None):
        """
        Marca el pago como aprobado de forma atomica e idempotente.
        Bloquea los pagos de la orden para evitar dos aprobaciones simultaneas.
        """
        with transaction.atomic():
            pago = (
                type(self).objects
                .select_related("orden__usuario")
                .select_for_update()
                .get(pk=self.pk)
            )

            if pago.estado in [pago.Estado.APPROVED, pago.Estado.REFUNDED]:
                return
            if pago.estado != pago.Estado.PENDING:
                return

            if type(self).objects.filter(
                orden=pago.orden,
                estado=pago.Estado.APPROVED,
            ).exclude(pk=pago.pk).exists():
                raise ValidationError(
                    "La orden ya tiene un pago aprobado."
                )

            pago._actualizar_estado(
                pago.Estado.APPROVED,
                campos_extra={
                    "id_transaccion": id_transaccion,
                    "respuesta_pasarela": respuesta or {},
                }
            )

            self.estado = pago.estado
            self.id_transaccion = pago.id_transaccion
            self.respuesta_pasarela = pago.respuesta_pasarela
            self.fecha_procesado = pago.fecha_procesado

            from apps.notificaciones.tasks import notificar_pago_aprobado
            transaction.on_commit(
                lambda: notificar_pago_aprobado.delay(
                    usuario_id=pago.orden.usuario.pk,
                    pago_id=str(pago.id),
                    monto=pago.monto,
                )
            )

    def marcar_rechazado(self, respuesta=None):
        """Marca el pago como rechazado solo si sigue pendiente."""
        with transaction.atomic():
            pago = type(self).objects.select_for_update().get(pk=self.pk)
            if pago.estado != pago.Estado.PENDING:
                return

            pago._actualizar_estado(
                pago.Estado.REJECTED,
                campos_extra={
                    "respuesta_pasarela": respuesta or {},
                }
            )
            self.estado = pago.estado
            self.respuesta_pasarela = pago.respuesta_pasarela
            self.fecha_procesado = pago.fecha_procesado

            from apps.notificaciones.tasks import notificar_pago_rechazado
            transaction.on_commit(
                lambda: notificar_pago_rechazado.delay(
                    usuario_id=pago.orden.usuario.pk,
                    pago_id=str(pago.id),
                )
            )

    def marcar_reembolsado(self, respuesta=None):
        """Marca el pago como reembolsado solo si fue aprobado."""
        with transaction.atomic():
            pago = type(self).objects.select_for_update().get(pk=self.pk)
            if pago.estado != pago.Estado.APPROVED:
                return

            pago._actualizar_estado(
                pago.Estado.REFUNDED,
                campos_extra={
                    "respuesta_pasarela": respuesta or {},
                }
            )
            self.estado = pago.estado
            self.respuesta_pasarela = pago.respuesta_pasarela
            self.fecha_procesado = pago.fecha_procesado

    def cancelar(self):
        """Cancela un pago pendiente."""
        with transaction.atomic():
            pago = type(self).objects.select_for_update().get(pk=self.pk)
            if pago.estado != pago.Estado.PENDING:
                return

            pago._actualizar_estado(pago.Estado.CANCELLED)
            self.estado = pago.estado
            self.fecha_procesado = pago.fecha_procesado