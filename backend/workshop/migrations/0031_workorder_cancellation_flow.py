# Generated manually for cancellation flow.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("workshop", "0030_service_default_parts"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="workorder",
            name="cancellation_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="workorder",
            name="cancelled_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cancelled_work_orders", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="workorder",
            name="status",
            field=models.CharField(choices=[("open", "Aberta"), ("in_progress", "Em execucao"), ("waiting_parts", "Aguardando pecas"), ("completed", "Concluida"), ("cancelled", "Cancelada")], db_index=True, default="open", max_length=30),
        ),
        migrations.AlterField(
            model_name="workorderevent",
            name="event_type",
            field=models.CharField(choices=[("created", "Criada"), ("updated", "Atualizada"), ("status_changed", "Status alterado"), ("message_sent", "Mensagem enviada"), ("payment_added", "Pagamento registrado"), ("inventory_reserved", "Estoque reservado"), ("inventory_reservation_released", "Reserva liberada"), ("inventory_consumed", "Estoque consumido"), ("purchase_needed", "Necessidade de compra"), ("photo_added", "Foto adicionada"), ("service_started", "Servico iniciado"), ("service_finished", "Servico concluido"), ("service_quality_checked", "Servico conferido"), ("checklist_updated", "Checklist atualizado"), ("delivery_signed", "Entrega assinada"), ("note", "Nota"), ("cancelled", "Cancelada"), ("error", "Erro")], max_length=40),
        ),
    ]
