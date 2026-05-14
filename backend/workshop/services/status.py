from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.audit import audit_financial_event, model_snapshot
from accounts.models import AuditLog
from accounts.roles import ROLE_TECHNICIAN
from accounts.services import get_user_role, user_has_permission

from .events import _set_work_order_status, record_event
from .inventory import consume_parts_inventory, release_work_order_part_reservations
from .notifications import trigger_status_notifications
from .state_targets import TECHNICAL_COMPLETE_TARGETS, TECHNICAL_START_TARGETS
from ..models import WorkOrder, WorkOrderEvent
from ..state_machine import SOURCE_MANUAL, SOURCE_TECHNICAL_COMPLETE, SOURCE_TECHNICAL_START, SOURCE_TECHNICAL_WAITING_PARTS


def _technical_order_actor_allowed(work_order, actor):
    if not getattr(actor, "is_authenticated", False):
        return False
    if user_has_permission(actor, "work_orders.edit") or user_has_permission(actor, "technical.execute") and get_user_role(actor) != ROLE_TECHNICIAN:
        return True
    if work_order.assigned_to_id == actor.id:
        return True
    return work_order.services.filter(technician=actor).exists()


def technical_move_work_order(work_order, action, actor=None, note="", send_notifications=True, diagnosis_description=""):
    """Executa atalhos operacionais da Bancada Técnica no nível da OS."""
    action = (action or "").strip()
    if action not in {"start", "complete", "wait_parts"}:
        raise ValidationError({"action": "Ação técnica inválida."})
    if not _technical_order_actor_allowed(work_order, actor):
        raise ValidationError({"permissao": "Você só pode movimentar OS atribuídas a você ou a serviços sob sua responsabilidade."})

    current = work_order.status
    if action == "start":
        target = TECHNICAL_START_TARGETS.get(current)
        if not target:
            raise ValidationError({"status": "Esta OS não pode ser iniciada pela Bancada Técnica a partir do status atual."})
        default_note = "OS iniciada pela Bancada Técnica."
        source = SOURCE_TECHNICAL_START
    elif action == "complete":
        target = TECHNICAL_COMPLETE_TARGETS.get(current)
        if not target:
            raise ValidationError({"status": "Esta OS não pode ser concluída pela Bancada Técnica a partir do status atual."})
        default_note = "OS concluída pela Bancada Técnica."
        source = SOURCE_TECHNICAL_COMPLETE
    else:
        if current not in {WorkOrder.Status.OPEN, WorkOrder.Status.IN_PROGRESS, WorkOrder.Status.PAUSED}:
            raise ValidationError({"status": "Somente OS aberta, em execução ou pausada pode ir para Aguardando peças."})
        target = WorkOrder.Status.WAITING_PARTS
        default_note = "OS movida para Aguardando peças pela Bancada Técnica."
        source = SOURCE_TECHNICAL_WAITING_PARTS

    updated, message_ids = change_work_order_status(
        work_order,
        target,
        actor=actor,
        note=note or default_note,
        send_notifications=send_notifications,
        source=source,
    )
    return updated, message_ids


def change_work_order_status(work_order, new_status, actor=None, note="", send_notifications=True, source=SOURCE_MANUAL):
    old_status = work_order.status
    if old_status == new_status:
        return work_order, []
    with transaction.atomic():
        locked = WorkOrder.objects.select_for_update(of=("self",)).get(pk=work_order.pk)
        old_status = locked.status
        before = model_snapshot(
            locked,
            ["number", "status", "financial_status", "manual_discount_amount", "discount_total", "grand_total", "paid_total", "balance_due", "started_at", "completed_at", "delivered_at", "cancelled_at", "cancellation_reason"],
        )
        _set_work_order_status(locked, new_status, actor=actor, note=note, source=source, save=True)
        if locked.status in {WorkOrder.Status.IN_PROGRESS, WorkOrder.Status.COMPLETED}:
            consume_parts_inventory(locked, actor=actor)
        locked.refresh_from_db()
        audit_financial_event(
            event_type=AuditLog.Action.FINANCIAL_STATUS,
            instance=locked,
            user=actor,
            description=note or f"Status da OS alterado para {locked.status_label}.",
            before=before,
            after=model_snapshot(locked, ["number", "status", "financial_status", "manual_discount_amount", "discount_total", "grand_total", "paid_total", "balance_due", "started_at", "completed_at", "delivered_at", "cancelled_at", "cancellation_reason"]),
            metadata={"old_status": old_status, "new_status": locked.status, "source": source},
            reason=note,
        )
        record_event(locked, WorkOrderEvent.EventType.STATUS_CHANGED, actor=actor, description=note or f"Status alterado para {locked.status_label}.", old_status=old_status, new_status=locked.status)
    locked.refresh_from_db()
    if locked.status == WorkOrder.Status.COMPLETED:
        from finance.services import ensure_receivable_for_work_order

        ensure_receivable_for_work_order(locked, actor=actor)
        locked.refresh_from_db()
    sent = []
    if send_notifications:
        fresh = WorkOrder.objects.select_related("customer", "vehicle", "assigned_to").get(pk=locked.pk)
        sent = trigger_status_notifications(fresh, actor=actor)
    return locked, sent


def cancel_work_order(work_order, actor=None, reason="", send_notifications=True):
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationError({"reason": "Informe uma justificativa com pelo menos 5 caracteres para cancelar a OS."})
    updated, message_ids = change_work_order_status(
        work_order,
        WorkOrder.Status.CANCELLED,
        actor=actor,
        note=reason,
        send_notifications=send_notifications,
        source=SOURCE_MANUAL,
    )
    release_work_order_part_reservations(updated, actor=actor, reason=f"Cancelamento da OS. {reason}")
    updated.refresh_from_db()
    return updated, message_ids
