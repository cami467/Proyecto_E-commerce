# Generated manually during catalog audit.
from django.db import migrations, models
from django.db.models import Q
from django.db.models.functions import Lower


class Migration(migrations.Migration):

    dependencies = [
        ("productos", "0006_agregar_tasa_iva_producto"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="categoria",
            name="unique_nombre_por_categoria_padre",
        ),
        migrations.RemoveConstraint(
            model_name="producto",
            name="unique_nombre_por_categoria",
        ),
        migrations.AddConstraint(
            model_name="categoria",
            constraint=models.UniqueConstraint(
                Lower("nombre"),
                name="unique_nombre_categoria_raiz_ci",
                condition=Q(categoria_padre__isnull=True),
            ),
        ),
        migrations.AddConstraint(
            model_name="categoria",
            constraint=models.UniqueConstraint(
                Lower("nombre"),
                "categoria_padre",
                name="unique_nombre_por_categoria_padre_ci",
                condition=Q(categoria_padre__isnull=False),
            ),
        ),
        migrations.AddConstraint(
            model_name="producto",
            constraint=models.UniqueConstraint(
                Lower("nombre"),
                "categoria",
                name="unique_nombre_por_categoria_ci",
                condition=Q(categoria__isnull=False),
                violation_error_message="Ya existe un producto con este nombre en esta categoría.",
            ),
        ),
    ]
