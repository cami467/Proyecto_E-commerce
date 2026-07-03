from decimal import Decimal
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q
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

    CODIGO_REGEX = re.compile(r"^[A-Z0-9_-]{3,50}$")

    class TipoDescuento(models.TextChoices):
        PORCENTAJE = "porcentaje", "Porcentaje (%)"
        MONTO_FIJO = "monto_fijo", "Monto fijo (Gs.)"

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
        constraints = [
            models.CheckConstraint(
                condition=Q(valor__gt=0),
                name="cupon_valor_positivo",
            ),
            models.CheckConstraint(
                condition=Q(monto_minimo__gte=0),
                name="cupon_monto_minimo_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(limite_usos__isnull=True) | Q(limite_usos__gt=0),
                name="cupon_limite_usos_positivo_o_nulo",
            ),
            models.CheckConstraint(
                condition=Q(tipo="monto_fijo") | Q(valor__lte=100),
                name="cupon_porcentaje_maximo_100",
            ),
            models.CheckConstraint(
                condition=Q(fecha_vencimiento__isnull=True) | Q(fecha_vencimiento__gt=F("fecha_inicio")),
                name="cupon_vencimiento_posterior_inicio",
            ),
        ]

    def __str__(self):
        return f"{self.codigo} — {self.get_tipo_display()} {self.valor}"

    def clean(self):
        """Valida reglas de negocio que no dependen de la base de datos."""
        super().clean()
        self.codigo = self.normalizar_codigo(self.codigo)

        errores = {}

        if not self.CODIGO_REGEX.match(self.codigo):
            errores["codigo"] = (
                "El código debe tener entre 3 y 50 caracteres y solo puede "
                "contener letras, números, guion medio o guion bajo."
            )

        if self.valor <= 0:
            errores["valor"] = "El valor del descuento debe ser mayor a cero."

        if self.tipo == self.TipoDescuento.PORCENTAJE and self.valor > 100:
            errores["valor"] = "El descuento porcentual no puede superar el 100%."

        if self.monto_minimo < 0:
            errores["monto_minimo"] = "El monto mínimo no puede ser negativo."

        if self.limite_usos is not None and self.limite_usos <= 0:
            errores["limite_usos"] = "El límite de usos debe ser mayor a cero o quedar vacío."

        if self.limite_usos is not None and self.usos_actuales > self.limite_usos:
            errores["usos_actuales"] = "Los usos actuales no pueden superar el límite de usos."

        if self.fecha_vencimiento and self.fecha_vencimiento <= self.fecha_inicio:
            errores["fecha_vencimiento"] = "La fecha de vencimiento debe ser posterior a la fecha de inicio."

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        """Normaliza y valida el cupón antes de guardar."""
        self.codigo = self.normalizar_codigo(self.codigo)
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def normalizar_codigo(cls, codigo: str) -> str:
        """Normaliza el código del cupón para búsquedas consistentes."""
        return (codigo or "").strip().upper()

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
        subtotal = Decimal(subtotal)
        if subtotal <= 0:
            return Decimal("0")

        if self.tipo == self.TipoDescuento.PORCENTAJE:
            descuento = subtotal * (self.valor / Decimal("100"))
        else:
            descuento = self.valor

        return min(descuento, subtotal).quantize(Decimal("1"))

    def validar(self, usuario, subtotal: Decimal) -> None:
        """
        Valida que el cupón sea aplicable para el usuario y subtotal dados.
        """
        subtotal = Decimal(subtotal)

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

        if self.usuarios_permitidos.exists() and not self.usuarios_permitidos.filter(pk=usuario.pk).exists():
            raise CuponInvalido("Este cupón no está disponible para tu cuenta.")

    def incrementar_uso(self) -> None:
        """
        Incrementa el contador de usos de forma atómica.

        Este método evita condiciones de carrera cuando varias órdenes intentan
        consumir el mismo cupón al mismo tiempo.
        """
        with transaction.atomic():
            cupon = Cupon.objects.select_for_update().get(pk=self.pk)

            if cupon.limite_usos is not None and cupon.usos_actuales >= cupon.limite_usos:
                raise CuponInvalido("El cupón alcanzó su límite de usos.")

            Cupon.objects.filter(pk=cupon.pk).update(
                usos_actuales=F("usos_actuales") + 1,
                fecha_actualizacion=timezone.now(),
            )

        self.refresh_from_db(fields=["usos_actuales", "fecha_actualizacion"])
