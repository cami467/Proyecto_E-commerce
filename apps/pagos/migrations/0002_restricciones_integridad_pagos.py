# Generated manually during pagos audit

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pagos", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="pago",
            index=models.Index(
                fields=["pasarela", "id_transaccion"],
                name="pagos_pago_pasarel_2e44f7_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="pago",
            constraint=models.CheckConstraint(
                condition=models.Q(("monto__gte", 1)),
                name="pago_monto_mayor_a_cero",
            ),
        ),
        migrations.AddConstraint(
            model_name="pago",
            constraint=models.UniqueConstraint(
                condition=models.Q(("estado", "approved")),
                fields=("orden",),
                name="un_pago_aprobado_por_orden",
            ),
        ),
        migrations.AddConstraint(
            model_name="pago",
            constraint=models.UniqueConstraint(
                condition=models.Q(("id_transaccion", ""), _negated=True),
                fields=("pasarela", "id_transaccion"),
                name="transaccion_unica_por_pasarela",
            ),
        ),
    ]
