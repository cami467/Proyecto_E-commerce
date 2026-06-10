from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from core.models import ModeloBase
from core.exceptions import CuponInvalido


class Cupon(ModeloBase):
    """
    Cupón de descuento aplicable a órdenes de compra.

    Soporta dos tipos de descuento:
        - PORCENTAJE: descuenta un % del subtotal de la orden.
        - MONTO_FIJO: descuenta un monto fijo en Guaraníes.

    Reglas de validación:
        - El cupón debe estar activo (esta_activo=True).
        - No debe haber superado su fecha de vencimiento.
        - No debe haber superado el límite de usos totales.
        - El subtotal de la orden debe superar el mínimo requerido.
        - Si tiene usuarios asignados, solo ellos pueden usarlo.
    """

    class TipoDescuento(models.TextChoices):
        PORCENTAJE  = "porcentaje",  "Porcentaje (%)"
        MONTO_FIJO  = "monto_fijo",  "Monto fijo (Gs.)"

    codigo = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Código único del cupón. Se normaliza a mayúsculas."
    )
    descripcion = models.TextField(
        blank=True,
        default="",
        help_text="Descripción interna del cupón para el equipo."
    )
    tipo = models.CharField(
        max_length=20,
        choices=TipoDescuento.choices,
        default=TipoDescuento.PORCENTAJE,
        help_text="Tipo de descuento: porcentaje o monto fijo."
    )
    valor = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=(
            "Valor del descuento. "
            "Si tipo=PORCENTAJE: valor entre 0 y 100. "
            "Si tipo=MONTO_FIJO: monto en Guaraníes."
        )
    )
    monto_minimo = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=Decimal("0"),
        help_text="Monto mínimo de la orden para aplicar el cupón en Gs."
    )
    limite_usos = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Cantidad máxima de usos. Null = sin límite."
    )
    usos_actuales = models.PositiveIntegerField(
        default=0,
        help_text="Cantidad de veces que fue usado. Se incrementa automáticamente."
    )
    fecha_inicio = models.DateTimeField(
        default=timezone.now,
        help_text="Fecha desde la que el cupón es válido."
    )
    fecha_vencimiento = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha de vencimiento. Null = no vence."
    )
    usuarios_permitidos = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="cupones_asignados",
        help_text="Usuarios que pueden usar este cupón. Vacío = todos."
    )

    class Meta:
        verbose_name = "Cupón"
        verbose_name_plural = "Cupones"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"{self.codigo} — {self.get_tipo_display()} {self.valor}"

    def save(self, *args, **kwargs):
        """Normaliza el código a mayúsculas antes de guardar."""
        self.codigo = self.codigo.strip().upper()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # PROPIEDADES DE ESTADO
    # ------------------------------------------------------------------

    @property
    def esta_vigente(self) -> bool:
        """True si el cupón está dentro de su período de validez."""
        ahora = timezone.now()
        if ahora < self.fecha_inicio:
            return False
        if self.fecha_vencimiento and ahora > self.fecha_vencimiento:
            return False
        return True

    @property
    def tiene_usos_disponibles(self) -> bool:
        """True si el cupón no alcanzó su límite de usos."""
        if self.limite_usos is None:
            return True
        return self.usos_actuales < self.limite_usos

    @property
    def usos_restantes(self) -> int | None:
        """Retorna los usos restantes o None si no tiene límite."""
        if self.limite_usos is None:
            return None
        return max(0, self.limite_usos - self.usos_actuales)

    # ------------------------------------------------------------------
    # LÓGICA DE NEGOCIO
    # ------------------------------------------------------------------

    def calcular_descuento(self, subtotal: Decimal) -> Decimal:
        """
        Calcula el monto de descuento según el tipo del cupón.

        Para porcentaje: nunca supera el subtotal.
        Para monto fijo: nunca supera el subtotal.
        Siempre retorna un valor positivo en Guaraníes.
        """
        if self.tipo == self.TipoDescuento.PORCENTAJE:
            descuento = subtotal * (self.valor / Decimal("100"))
        else:
            descuento = self.valor

        return min(descuento, subtotal).quantize(Decimal("1"))

    def validar(self, usuario, subtotal: Decimal) -> None:
        """
        Valida que el cupón sea aplicable para el usuario y subtotal dados.

        Lanza CuponInvalido con mensaje descriptivo si alguna
        regla de negocio no se cumple.

        Args:
            usuario: instancia del usuario que intenta usar el cupón.
            subtotal: monto de la orden antes del descuento en Gs.

        Raises:
            CuponInvalido: si el cupón no es aplicable.
        """
        if not self.esta_activo:
            raise CuponInvalido("El cupón no está activo.")

        if not self.esta_vigente:
            raise CuponInvalido("El cupón está vencido o aún no es válido.")

        if not self.tiene_usos_disponibles:
            raise CuponInvalido("El cupón alcanzó su límite de usos.")

        if subtotal < self.monto_minimo:
            raise CuponInvalido(
                f"El monto mínimo para usar este cupón es "
                f"Gs. {int(self.monto_minimo):,.0f}. "
                f"Tu orden es de Gs. {int(subtotal):,.0f}."
            )

        permitidos = self.usuarios_permitidos.all()
        if permitidos.exists() and usuario not in permitidos:
            raise CuponInvalido(
                "Este cupón no está disponible para tu cuenta."
            )

    def incrementar_uso(self) -> None:
        """
        Incrementa el contador de usos de forma segura.
        Usa update_fields para optimizar la query.
        """
        self.usos_actuales += 1
        self.save(update_fields=["usos_actuales", "fecha_actualizacion"])