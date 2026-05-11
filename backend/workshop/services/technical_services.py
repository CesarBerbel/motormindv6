from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.roles import ROLE_TECHNICIAN
from accounts.services import get_user_role, user_has_permission

from .events import _set_work_order_status, record_event
from .state_targets import TECHNICAL_COMPLETE_TARGETS, TECHNICAL_START_TARGETS
from ..models import WorkOrder, WorkOrderEvent, WorkOrderService, WorkshopProfile
from ..state_machine import SOURCE_TECHNICAL_COMPLETE, SOURCE_TECHNICAL_START


def _service_duration_minutes(service_line, finished_at):
    if not service_line.started_at:
        return service_line.actual_minutes or 0
    seconds = max((finished_at - service_line.started_at).total_seconds(), 0)
    return int(seconds // 60)
def _all_active_services_done(work_order):
    return not work_order.services.exclude(status__in=[WorkOrderService.Status.DONE, WorkOrderService.Status.CANCELLED]).exists()
def _technical_actor_allowed(service_line, actor):
    if not getattr(actor, "is_authenticated", False):
        return False
    from accounts.roles import ROLE_TECHNICIAN
    from accounts.services import get_user_role, user_has_permission

    if user_has_permission(actor, "*"):
        return True
    if user_has_permission(actor, "technical.execute") and get_user_role(actor) != ROLE_TECHNICIAN:
        return True
    if get_user_role(actor) != ROLE_TECHNICIAN:
        return False
    return service_line.technician_id in {None, actor.id} or service_line.work_order.assigned_to_id == actor.id
def start_work_order_service(service_line, actor=None, note=""):
    if not _technical_actor_allowed(service_line, actor):
        raise ValidationError({"permissao": "Você só pode iniciar serviços atribuídos a você ou à OS sob sua responsabilidade."})
    if service_line.status in {WorkOrderService.Status.DONE, WorkOrderService.Status.CANCELLED}:
        raise ValidationError({"status": "Serviço concluído ou cancelado não pode ser iniciado."})
    now = timezone.now()
    with transaction.atomic():
        locked = WorkOrderService.objects.select_for_update(of=("self",)).select_related("work_order", "technician").get(pk=service_line.pk)
        if not locked.technician_id and getattr(actor, "is_authenticated", False):
            locked.technician = actor
        if not locked.started_at:
            locked.started_at = now
        locked.status = WorkOrderService.Status.IN_PROGRESS
        if note:
            locked.notes = f"{locked.notes}\n{note}".strip() if locked.notes else note
        locked.save(update_fields=["technician", "started_at", "status", "notes", "updated_at"])
        order = locked.work_order
        previous_status = order.status
        start_target = TECHNICAL_START_TARGETS.get(order.status)
        if start_target and order.status != start_target:
            description = "OS colocada em execução pelo início de um serviço técnico."
            _set_work_order_status(order, start_target, actor=actor, note=description, source=SOURCE_TECHNICAL_START, save=True)
            record_event(order, WorkOrderEvent.EventType.STATUS_CHANGED, actor=actor, description=description, old_status=previous_status, new_status=order.status)
        record_event(order, WorkOrderEvent.EventType.SERVICE_STARTED, actor=actor, description=f"Serviço iniciado: {locked.description}.", data={"work_order_service_id": locked.id, "note": note})
    locked.refresh_from_db()
    return locked
def complete_work_order_service(service_line, actor=None, technical_diagnosis="", execution_notes="", checklist=None, mark_order_quality_check=True):
    if not _technical_actor_allowed(service_line, actor):
        raise ValidationError({"permissao": "Você só pode concluir serviços atribuídos a você ou à OS sob sua responsabilidade."})
    if service_line.status == WorkOrderService.Status.CANCELLED:
        raise ValidationError({"status": "Serviço cancelado não pode ser concluído."})
    if not execution_notes:
        raise ValidationError({"execution_notes": "Informe o que foi executado antes de concluir o serviço."})
    now = timezone.now()
    checklist = checklist or {}
    with transaction.atomic():
        locked = WorkOrderService.objects.select_for_update(of=("self",)).select_related("work_order", "technician").get(pk=service_line.pk)
        if not locked.technician_id and getattr(actor, "is_authenticated", False):
            locked.technician = actor
        if not locked.started_at:
            locked.started_at = now
        profile = WorkshopProfile.get_solo()
        if profile.technical_checklist_enabled:
            if not locked.checklist_items.exists():
                locked.create_checklist_from_template()
            pending_items = [item.description for item in locked.checklist_items.all() if item.is_blocking_pending]
            if pending_items:
                raise ValidationError({"checklist": "Conclua todos os itens obrigatórios do checklist técnico antes de finalizar o serviço: " + "; ".join(pending_items)})
        locked.finished_at = now
        locked.status = WorkOrderService.Status.DONE
        locked.technical_diagnosis = technical_diagnosis or locked.technical_diagnosis
        locked.execution_notes = execution_notes
        locked.checklist = checklist
        locked.actual_minutes = _service_duration_minutes(locked, now)
        locked.save(update_fields=["technician", "started_at", "finished_at", "status", "technical_diagnosis", "execution_notes", "checklist", "actual_minutes", "updated_at"])
        order = locked.work_order
        record_event(order, WorkOrderEvent.EventType.SERVICE_FINISHED, actor=actor, description=f"Serviço concluído: {locked.description}.", data={"work_order_service_id": locked.id, "actual_minutes": locked.actual_minutes, "checklist": checklist})
        if mark_order_quality_check and _all_active_services_done(order) and order.status != WorkOrder.Status.COMPLETED:
            old_status = order.status
            complete_target = TECHNICAL_COMPLETE_TARGETS.get(order.status)
            if complete_target:
                description = "Todos os serviços técnicos foram concluídos. OS concluída."
                _set_work_order_status(order, complete_target, actor=actor, note=description, source=SOURCE_TECHNICAL_COMPLETE, save=True)
                record_event(order, WorkOrderEvent.EventType.STATUS_CHANGED, actor=actor, description=description, old_status=old_status, new_status=order.status)
    locked.refresh_from_db()
    return locked
def quality_check_work_order_service(service_line, actor=None, approved=True, notes=""):
    from accounts.services import user_has_permission

    if not user_has_permission(actor, ["work_orders.edit", "technical.quality_check"]):
        raise ValidationError({"permissao": "Você não tem permissão para conferir serviços técnicos."})
    now = timezone.now()
    with transaction.atomic():
        locked = WorkOrderService.objects.select_for_update(of=("self",)).select_related("work_order").get(pk=service_line.pk)
        if approved:
            locked.quality_checked_at = now
            locked.quality_checked_by = actor if getattr(actor, "is_authenticated", False) else None
            locked.quality_check_notes = notes
            locked.save(update_fields=["quality_checked_at", "quality_checked_by", "quality_check_notes", "updated_at"])
            description = f"Serviço conferido e aprovado: {locked.description}."
        else:
            locked.status = WorkOrderService.Status.IN_PROGRESS
            locked.finished_at = None
            locked.quality_checked_at = None
            locked.quality_checked_by = None
            locked.quality_check_notes = notes
            locked.save(update_fields=["status", "finished_at", "quality_checked_at", "quality_checked_by", "quality_check_notes", "updated_at"])
            description = f"Serviço reprovado na conferência e devolvido ao técnico: {locked.description}."
            order = locked.work_order
            if order.status == WorkOrder.Status.COMPLETED:
                raise ValidationError({"status": "OS concluída não pode receber reprovação de conferência. Abra uma OS de retorno/garantia."})
        record_event(locked.work_order, WorkOrderEvent.EventType.SERVICE_QUALITY_CHECKED, actor=actor, description=description, data={"work_order_service_id": locked.id, "approved": approved, "notes": notes})
    locked.refresh_from_db()
    return locked
