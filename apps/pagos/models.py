from decimal import Decimal
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

    Estados posibles:
        pending   → El pago fue iniciado pero no procesado.
        approved  → La pasarela confirmo el cobro exitosamente.
        rejected  → La pasarela rechazo el intento de cobro.
        refunded  → El monto fue devuelto al comprador.
        cancelled → El pago fue cancelado antes de procesarse.
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

    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ["-fecha_creacion"]
        indexes = [
            models.Index(fields=["orden", "estado"]),
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
        """
        Helper interno para actualizar el estado de forma atomica.
        Centraliza la logica de guardado para todos los metodos
        de transicion de estado.
        """
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
        Marca el pago como aprobado y registra la respuesta
        de la pasarela para auditoria.

        Es idempotente: si ya esta aprobado o reembolsado
        no hace nada para evitar dobles procesamientos.
        """
        if self.estado in [self.Estado.APPROVED, self.Estado.REFUNDED]:
            return

        with transaction.atomic():
            self._actualizar_estado(
                self.Estado.APPROVED,
                campos_extra={
                    "id_transaccion": id_transaccion,
                    "respuesta_pasarela": respuesta or {},
                }
            )
            # TODO: Notificar a la orden cuando se implemente
            # self.orden.marcar_como_pagada()

    def marcar_rechazado(self, respuesta=None):
        """
        Marca el pago como rechazado.

        Solo puede rechazarse un pago pendiente.
        Si ya fue procesado (aprobado/rechazado) no hace nada.
        """
        if self.estado != self.Estado.PENDING:
            return

        with transaction.atomic():
            self._actualizar_estado(
                self.Estado.REJECTED,
                campos_extra={
                    "respuesta_pasarela": respuesta or {},
                }
            )

    def marcar_reembolsado(self, respuesta=None):
        """
        Marca el pago como reembolsado.

        Solo puede reembolsarse un pago previamente aprobado.
        Registra la respuesta de la pasarela para auditoria.
        """
        if self.estado != self.Estado.APPROVED:
            return

        with transaction.atomic():
            self._actualizar_estado(
                self.Estado.REFUNDED,
                campos_extra={
                    "respuesta_pasarela": respuesta or {},
                }
            )

    def cancelar(self):
        """
        Cancela un pago pendiente.

        Solo puede cancelarse un pago que no haya sido procesado.
        """
        if self.estado != self.Estado.PENDING:
            return

        with transaction.atomic():
            self._actualizar_estado(self.Estado.CANCELLED)