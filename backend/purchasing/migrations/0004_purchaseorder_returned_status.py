# Generated manually for purchase order return workflow.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("purchasing", "0003_repair_supplier_schema"),
    ]

    operations = [
        migrations.AlterField(
            model_name="purchaseorder",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Rascunho"),
                    ("requested", "Solicitado"),
                    ("approved", "Aprovado"),
                    ("ordered", "Pedido enviado"),
                    ("partially_received", "Recebido parcial"),
                    ("received", "Recebido"),
                    ("returned", "Devolvido"),
                    ("cancelled", "Cancelado"),
                ],
                db_index=True,
                default="draft",
                max_length=30,
            ),
        ),
    ]
