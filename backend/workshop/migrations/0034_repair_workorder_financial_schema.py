# Generated manually to make local PostgreSQL upgrades resilient after the OS financial-status migration.

from django.db import migrations, models


def _table_columns(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        try:
            description = schema_editor.connection.introspection.get_table_description(cursor, table_name)
        except Exception:
            return set()
    return {column.name for column in description}


def ensure_missing_columns(apps, schema_editor):
    WorkOrder = apps.get_model("workshop", "WorkOrder")
    WorkshopProfile = apps.get_model("workshop", "WorkshopProfile")

    work_order_columns = _table_columns(schema_editor, WorkOrder._meta.db_table)
    if work_order_columns and "financial_status" not in work_order_columns:
        schema_editor.add_field(
            WorkOrder,
            models.CharField(
                max_length=20,
                choices=[
                    ("pending", "Pendente"),
                    ("partial", "Parcial"),
                    ("paid", "Pago"),
                    ("cancelled", "Cancelado"),
                ],
                default="pending",
                db_index=True,
            ),
        )

    profile_columns = _table_columns(schema_editor, WorkshopProfile._meta.db_table)
    if profile_columns and "delivery_with_pending_payment_allowed" not in profile_columns:
        schema_editor.add_field(
            WorkshopProfile,
            models.BooleanField(default=False, verbose_name="Permitir entrega de veículo com pagamento pendente"),
        )


def resync_financial_status(apps, schema_editor):
    WorkOrder = apps.get_model("workshop", "WorkOrder")
    if "financial_status" not in _table_columns(schema_editor, WorkOrder._meta.db_table):
        return
    for order in WorkOrder.objects.all().only("id", "status", "grand_total", "paid_total"):
        grand_total = order.grand_total or 0
        paid_total = order.paid_total or 0
        if order.status == "cancelled" and paid_total <= 0:
            status = "cancelled"
        elif grand_total > 0 and paid_total >= grand_total:
            status = "paid"
        elif paid_total > 0:
            status = "partial"
        else:
            status = "pending"
        WorkOrder.objects.filter(pk=order.pk).update(financial_status=status)


class Migration(migrations.Migration):
    dependencies = [
        ("workshop", "0033_workorder_financial_status_and_more"),
    ]

    operations = [
        migrations.RunPython(ensure_missing_columns, migrations.RunPython.noop),
        migrations.RunPython(resync_financial_status, migrations.RunPython.noop),
    ]
