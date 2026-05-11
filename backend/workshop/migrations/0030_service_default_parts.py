# Generated for MotorMindV6 UX improvements: default parts per service.

from decimal import Decimal

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("workshop", "0029_workshopprofile_design_system"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceDefaultPart",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("quantity", models.DecimalField(decimal_places=2, default=Decimal("1.00"), max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal("0.01"))])),
                ("unit_price", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("discount_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("consume_inventory", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("part", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="default_service_links", to="workshop.part")),
                ("service", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="default_parts", to="workshop.workshopservice")),
            ],
            options={
                "verbose_name": "peça padrão do serviço",
                "verbose_name_plural": "peças padrão dos serviços",
                "ordering": ["position", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="servicedefaultpart",
            constraint=models.UniqueConstraint(fields=("service", "part"), name="service_default_part_unique"),
        ),
    ]
