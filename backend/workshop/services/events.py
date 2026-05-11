from django.utils import timezone

from ..models import WorkOrder, WorkOrderEvent
from ..state_machine import SOURCE_MANUAL, validate_work_order_transition


def record_event(work_order, event_type, actor=None, description="", old_status="", new_status="", data=None):
    return WorkOrderEvent.objects.create(
        work_order=work_order,
        event_type=event_type,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        description=description,
        old_status=old_status or "",
        new_status=new_status or "",
        data=data or {},
    )
def apply_status_timestamps(work_order):
    now = timezone.now()
    if work_order.status == WorkOrder.Status.OPEN and not work_order.opened_at:
        work_order.opened_at = now
    if work_order.status == WorkOrder.Status.IN_PROGRESS and not work_order.started_at:
        work_order.started_at = now
    if work_order.status == WorkOrder.Status.COMPLETED:
        if not work_order.completed_at:
            work_order.completed_at = now
        if not work_order.delivered_at:
            work_order.delivered_at = now
def _set_work_order_status(locked_order, new_status, actor=None, note="", source=SOURCE_MANUAL, save=True):
    old_status = locked_order.status
    if old_status == new_status:
        return old_status, None
    rule = validate_work_order_transition(locked_order, new_status, actor=actor, note=note, source=source)
    locked_order.status = new_status
    locked_order.updated_by = actor if getattr(actor, "is_authenticated", False) else None
    apply_status_timestamps(locked_order)
    if save:
        locked_order.save()
    return old_status, rule
