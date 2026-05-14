from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from accounts.url_utils import get_frontend_base_url

from finance.models import AccountReceivable
from messaging.models import MessageLog, MessageTemplate
from messaging.services import create_and_send
from workshop.models import PartStockMovement, WorkOrder, WorkOrderMessage, WorkOrderNotificationRule, WorkOrderPart, WorkOrderService, WorkshopProfile
from workshop.services import record_event, reserve_parts_for_work_order
from workshop.models import WorkOrderEvent

from .models import CounterSale, CounterSalePayment, Estimate, EstimateCustomerApproval, EstimateStatusHistory

ZERO = Decimal("0.00")
ESTIMATE_EDITABLE_STATUSES = {Estimate.Status.DRAFT}
ESTIMATE_APPROVAL_REQUEST_STATUSES = {Estimate.Status.DRAFT, Estimate.Status.SENT}


def _actor_or_none(actor):
    return actor if getattr(actor, "is_authenticated", False) else None


def _actor_display(actor):
    if not getattr(actor, "is_authenticated", False):
        return ""
    return (actor.get_full_name() or actor.get_username() or str(actor)).strip()


def record_estimate_status_history(estimate, old_status, new_status, actor=None, description="", data=None):
    if old_status == new_status:
        return None
    return EstimateStatusHistory.objects.create(
        estimate=estimate,
        old_status=old_status or "",
        new_status=new_status,
        actor=_actor_or_none(actor),
        description=description or f"Status alterado de {old_status or 'novo'} para {new_status}.",
        data=data or {},
    )


@transaction.atomic
def ensure_receivable_for_counter_sale(counter_sale, actor=None):
    sale = CounterSale.objects.select_for_update(of=("self",)).select_related("customer").prefetch_related("payments", "items").get(pk=counter_sale.pk)
    if sale.status != CounterSale.Status.FINALIZED:
        raise ValidationError("A conta a receber só pode ser gerada para venda avulsa finalizada.")
    sale.recalculate_totals(save=True)
    receivable, created = AccountReceivable.objects.select_for_update(of=("self",)).get_or_create(
        counter_sale=sale,
        defaults={
            "origin": AccountReceivable.Origin.COUNTER_SALE,
            "customer": sale.customer,
            "description": f"Conta a receber da venda avulsa {sale.number}",
            "issue_date": timezone.localdate(),
            "due_date": sale.due_date or timezone.localdate(),
            "amount": sale.total_amount or ZERO,
            "discount_amount": sale.discount_amount or ZERO,
            "paid_amount": sale.paid_amount or ZERO,
            "created_by": _actor_or_none(actor),
            "updated_by": _actor_or_none(actor),
        },
    )
    receivable.origin = AccountReceivable.Origin.COUNTER_SALE
    receivable.customer = sale.customer
    receivable.description = f"Conta a receber da venda avulsa {sale.number}"
    receivable.due_date = sale.due_date or timezone.localdate()
    receivable.updated_by = _actor_or_none(actor) or receivable.updated_by
    receivable.recalculate(save=True)
    return receivable, created


@transaction.atomic
def register_counter_sale_payment(counter_sale, amount, method, paid_at=None, reference="", notes="", actor=None):
    sale = CounterSale.objects.select_for_update(of=("self",)).get(pk=counter_sale.pk)
    if sale.status == CounterSale.Status.CANCELLED:
        raise ValidationError("Venda cancelada não pode receber pagamento.")
    sale.recalculate_totals(save=True)
    amount = Decimal(str(amount))
    if amount <= ZERO:
        raise ValidationError("O valor recebido precisa ser maior que zero.")
    if amount > sale.balance_amount:
        raise ValidationError("O valor recebido não pode ser maior que o saldo da venda.")
    payment = CounterSalePayment.objects.create(
        counter_sale=sale,
        method=method,
        amount=amount,
        paid_at=paid_at or timezone.now(),
        reference=reference,
        notes=notes,
        created_by=_actor_or_none(actor),
    )
    sale.refresh_from_db()
    sale.recalculate_totals(save=True)
    if sale.status == CounterSale.Status.FINALIZED:
        ensure_receivable_for_counter_sale(sale, actor=actor)
    return payment, sale


@transaction.atomic
def finalize_counter_sale(counter_sale, actor=None, payment_amount=None, payment_method=None, payment_reference="", payment_notes=""):
    sale = CounterSale.objects.select_for_update(of=("self",)).prefetch_related("items__part").get(pk=counter_sale.pk)
    if sale.status != CounterSale.Status.DRAFT:
        raise ValidationError("Somente venda em rascunho pode ser finalizada.")
    items = list(sale.items.select_related("part"))
    if not items:
        raise ValidationError("Inclua pelo menos uma peça na venda avulsa.")
    sale.recalculate_totals(save=True)
    if sale.total_amount <= ZERO:
        raise ValidationError("Venda avulsa precisa ter valor final maior que zero.")

    for item in items:
        if not item.part_id:
            continue
        part = item.part
        if part.stock_quantity < item.quantity:
            raise ValidationError(f"Estoque insuficiente para {part.name}. Disponível: {part.stock_quantity}; solicitado: {item.quantity}.")
        part.stock_quantity = (part.stock_quantity or ZERO) - (item.quantity or ZERO)
        part.save(update_fields=["stock_quantity", "updated_at"])
        movement = PartStockMovement.objects.create(
            part=part,
            movement_type=PartStockMovement.MovementType.CONSUMPTION,
            quantity=-(item.quantity or ZERO),
            unit_cost=item.cost_price or part.cost_price or ZERO,
            notes=f"Baixa por venda avulsa {sale.number}",
            actor=_actor_or_none(actor),
        )
        item.stock_movement = movement
        item.save(update_fields=["stock_movement", "updated_at"])

    sale.status = CounterSale.Status.FINALIZED
    sale.sold_at = timezone.now()
    sale.updated_by = _actor_or_none(actor) or sale.updated_by
    sale.save(update_fields=["status", "sold_at", "updated_by", "updated_at"])

    if payment_amount and Decimal(str(payment_amount)) > ZERO:
        register_counter_sale_payment(
            sale,
            amount=payment_amount,
            method=payment_method or CounterSalePayment.Method.CASH,
            reference=payment_reference,
            notes=payment_notes,
            actor=actor,
        )
    sale.refresh_from_db()
    sale.recalculate_totals(save=True)
    ensure_receivable_for_counter_sale(sale, actor=actor)
    return sale


@transaction.atomic
def cancel_counter_sale(counter_sale, actor=None, reason=""):
    sale = CounterSale.objects.select_for_update(of=("self",)).prefetch_related("items__part", "items__stock_movement").get(pk=counter_sale.pk)
    if sale.status == CounterSale.Status.CANCELLED:
        return sale
    if sale.payments.exists():
        raise ValidationError("Venda com pagamento registrado não pode ser cancelada por segurança. Estorne o recebimento antes.")
    if sale.status == CounterSale.Status.FINALIZED:
        for item in sale.items.select_related("part", "stock_movement"):
            if item.part_id and item.stock_movement_id:
                part = item.part
                part.stock_quantity = (part.stock_quantity or ZERO) + (item.quantity or ZERO)
                part.save(update_fields=["stock_quantity", "updated_at"])
                PartStockMovement.objects.create(
                    part=part,
                    movement_type=PartStockMovement.MovementType.REVERSAL,
                    quantity=item.quantity or ZERO,
                    unit_cost=item.cost_price or part.cost_price or ZERO,
                    notes=f"Estorno da venda avulsa {sale.number}. {reason}".strip(),
                    actor=_actor_or_none(actor),
                )
    sale.status = CounterSale.Status.CANCELLED
    sale.notes = (sale.notes + "\n" if sale.notes else "") + (reason or "Venda avulsa cancelada.")
    sale.updated_by = _actor_or_none(actor) or sale.updated_by
    sale.save(update_fields=["status", "notes", "updated_by", "updated_at"])
    receivable = getattr(sale, "account_receivable", None)
    if receivable:
        receivable.status = AccountReceivable.Status.CANCELLED
        receivable.updated_by = _actor_or_none(actor) or receivable.updated_by
        receivable.save(update_fields=["status", "updated_by", "updated_at"])
    return sale


@transaction.atomic
def manually_approve_estimate(estimate, actor=None, approval_type="total", selected_service_ids=None, selected_part_ids=None, notes="", signature_name="", signature_document=""):
    obj = Estimate.objects.select_for_update(of=("self",)).select_related("customer", "vehicle").prefetch_related("services", "parts").get(pk=estimate.pk)
    if obj.status not in ESTIMATE_APPROVAL_REQUEST_STATUSES:
        raise ValidationError("Somente orçamento em rascunho ou enviado pode receber aprovação manual.")
    if not obj.customer_id:
        raise ValidationError({"customer_id": "Orçamento precisa estar vinculado a um cliente."})
    if not obj.vehicle_id:
        raise ValidationError({"vehicle_id": "Orçamento precisa estar vinculado a um veículo."})
    notes = (notes or "").strip()
    if not notes:
        raise ValidationError({"notes": "Informe uma observação para registrar a aprovação manual."})
    services = list(obj.services.all())
    parts = list(obj.parts.all())
    all_service_ids = {item.id for item in services}
    all_part_ids = {item.id for item in parts}
    if not all_service_ids:
        raise ValidationError("Inclua pelo menos um serviço no orçamento antes de aprovar manualmente.")

    if approval_type == "partial":
        selected_service_ids = {int(item_id) for item_id in (selected_service_ids or [])}
        selected_part_ids = {int(item_id) for item_id in (selected_part_ids or [])}
        if not selected_service_ids:
            raise ValidationError({"selected_service_ids": "Selecione pelo menos um serviço para aprovação parcial."})
    else:
        selected_service_ids = set(all_service_ids)
        selected_part_ids = set(all_part_ids)

    invalid_services = selected_service_ids - all_service_ids
    invalid_parts = selected_part_ids - all_part_ids
    if invalid_services or invalid_parts:
        raise ValidationError("A seleção contém itens que não pertencem a este orçamento.")

    linked_parts = {item.id for item in parts if item.service_item_id and item.service_item_id in selected_service_ids}
    orphan_parts = {item.id for item in parts if not item.service_item_id}
    selected_part_ids = selected_part_ids & (linked_parts | orphan_parts)
    is_partial = selected_service_ids != all_service_ids or selected_part_ids != all_part_ids
    now = timezone.now()
    actor_name = _actor_display(actor)
    decision_name = (signature_name or actor_name or "Aprovação manual").strip()[:180]
    audit_note = f"Aprovação manual {'parcial' if is_partial else 'total'} registrada"
    if actor_name:
        audit_note += f" por {actor_name} em {timezone.localtime(now).strftime('%d/%m/%Y %H:%M')}"
    if signature_name:
        audit_note += f" com assinatura/confirmação do cliente {signature_name.strip()}"
    full_notes = f"{notes}\n{audit_note}".strip()

    approval = EstimateCustomerApproval.objects.create(
        estimate=obj,
        requested_by=_actor_or_none(actor),
        expires_at=now,
    )
    approval.status = EstimateCustomerApproval.Status.PARTIALLY_APPROVED if is_partial else EstimateCustomerApproval.Status.APPROVED
    approval.decision_selected_services = sorted(selected_service_ids)
    approval.decision_selected_parts = sorted(selected_part_ids)
    approval.decision_name = decision_name
    approval.decision_document = (signature_document or "")[:30]
    approval.decision_notes = full_notes
    approval.decided_at = now
    approval.save(update_fields=["status", "decision_selected_services", "decision_selected_parts", "decision_name", "decision_document", "decision_notes", "decided_at", "updated_at"])

    old_status = obj.status
    obj.status = Estimate.Status.APPROVED
    obj.approved_at = now
    obj.approved_by = decision_name
    obj.approval_method = "manual"
    obj.updated_by = _actor_or_none(actor) or obj.updated_by
    obj.services.update(approved_by_customer=False, customer_decided_at=now)
    obj.parts.update(approved_by_customer=False, customer_decided_at=now)
    obj.services.filter(id__in=selected_service_ids).update(approved_by_customer=True, customer_decided_at=now)
    obj.parts.filter(id__in=selected_part_ids).update(approved_by_customer=True, customer_decided_at=now)
    obj.save(update_fields=["status", "approved_at", "approved_by", "approval_method", "updated_by", "updated_at"])
    record_estimate_status_history(obj, old_status, obj.status, actor=actor, description="Orçamento aprovado manualmente.", data={"approval_id": approval.id, "partial": is_partial})
    work_order = convert_estimate_to_work_order(obj, actor=actor, selected_service_ids=selected_service_ids, selected_part_ids=selected_part_ids, approval=approval)
    return approval, work_order


@transaction.atomic
def change_estimate_status(estimate, status, actor=None, note="", send_notifications=True):
    obj = Estimate.objects.select_for_update(of=("self",)).get(pk=estimate.pk)
    old_status = obj.status
    status = status or old_status
    valid_transitions = {
        Estimate.Status.DRAFT: {Estimate.Status.SENT, Estimate.Status.CANCELLED},
        Estimate.Status.SENT: {Estimate.Status.APPROVED, Estimate.Status.REJECTED, Estimate.Status.EXPIRED, Estimate.Status.CANCELLED},
        Estimate.Status.APPROVED: {Estimate.Status.CANCELLED},
        Estimate.Status.REJECTED: set(),
        Estimate.Status.EXPIRED: set(),
        Estimate.Status.CANCELLED: set(),
        Estimate.Status.CONVERTED: set(),
    }
    if status == old_status:
        return obj
    if status not in valid_transitions.get(old_status, set()):
        raise ValidationError(f"Transição de orçamento não permitida: {obj.status_label} → {dict(Estimate.Status.choices).get(status, status)}.")
    now = timezone.now()
    note = (note or "").strip()
    if status == Estimate.Status.CANCELLED and len(note) < 5:
        raise ValidationError({"reason": "Informe motivo de cancelamento com pelo menos 5 caracteres."})
    if status == Estimate.Status.REJECTED and len(note) < 5:
        raise ValidationError({"reason": "Informe motivo da recusa com pelo menos 5 caracteres."})
    if status == Estimate.Status.EXPIRED and (not obj.valid_until or obj.valid_until >= timezone.localdate()):
        raise ValidationError({"valid_until": "Orçamento só pode expirar quando a data de validade estiver vencida."})
    if status == Estimate.Status.APPROVED:
        if not obj.customer_id:
            raise ValidationError({"customer_id": "Orçamento precisa estar vinculado a um cliente."})
        if not obj.vehicle_id:
            raise ValidationError({"vehicle_id": "Orçamento precisa estar vinculado a um veículo."})
        obj.approved_at = obj.approved_at or now
        obj.approval_method = obj.approval_method or "manual"
        obj.approved_by = obj.approved_by or _actor_display(actor) or "Aprovação interna"
    if status == Estimate.Status.SENT:
        obj.sent_at = obj.sent_at or now
    if status == Estimate.Status.REJECTED:
        obj.rejected_at = obj.rejected_at or now
        obj.rejection_reason = note
    if status == Estimate.Status.CANCELLED:
        obj.cancelled_at = obj.cancelled_at or now
        obj.cancelled_by = _actor_or_none(actor) or obj.cancelled_by
        obj.cancellation_reason = note
    if note:
        obj.internal_notes = (obj.internal_notes + "\n" if obj.internal_notes else "") + note
    obj.status = status
    obj.updated_by = _actor_or_none(actor) or obj.updated_by
    obj.save(update_fields=["status", "sent_at", "approved_at", "approved_by", "approval_method", "rejected_at", "rejection_reason", "cancelled_at", "cancelled_by", "cancellation_reason", "internal_notes", "updated_by", "updated_at"])
    record_estimate_status_history(obj, old_status, obj.status, actor=actor, description=note or f"Status alterado para {obj.status_label}.")
    if send_notifications and old_status != obj.status:
        transaction.on_commit(lambda: trigger_estimate_status_notifications(Estimate.objects.select_related("customer", "vehicle").get(pk=obj.pk), actor=actor))
    return obj


@transaction.atomic
def cancel_estimate(estimate, actor=None, reason="", send_notifications=True):
    obj = Estimate.objects.select_for_update(of=("self",)).get(pk=estimate.pk)
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationError({"reason": "Informe uma justificativa com pelo menos 5 caracteres para cancelar o orçamento."})
    if obj.status in {Estimate.Status.REJECTED, Estimate.Status.EXPIRED, Estimate.Status.CANCELLED, Estimate.Status.CONVERTED}:
        raise ValidationError("Orçamento em estado terminal não pode ser cancelado ou reaberto.")
    old_status = obj.status
    now = timezone.now()
    actor_name = _actor_display(actor)
    audit_line = f"Cancelado em {timezone.localtime(now).strftime('%d/%m/%Y %H:%M')}"
    if actor_name:
        audit_line += f" por {actor_name}"
    audit_line += f". Justificativa: {reason}"
    obj.status = Estimate.Status.CANCELLED
    obj.cancelled_at = now
    obj.cancelled_by = _actor_or_none(actor)
    obj.cancellation_reason = reason
    obj.internal_notes = (obj.internal_notes + "\n" if obj.internal_notes else "") + audit_line
    obj.updated_by = _actor_or_none(actor) or obj.updated_by
    obj.save(update_fields=["status", "cancelled_at", "cancelled_by", "cancellation_reason", "internal_notes", "updated_by", "updated_at"])
    EstimateCustomerApproval.objects.filter(estimate=obj, status=EstimateCustomerApproval.Status.PENDING, is_active=True).update(is_active=False, updated_at=now)
    record_estimate_status_history(obj, old_status, obj.status, actor=actor, description=audit_line)
    if send_notifications and old_status != obj.status:
        transaction.on_commit(lambda: trigger_estimate_status_notifications(Estimate.objects.select_related("customer", "vehicle").get(pk=obj.pk), actor=actor))
    return obj


def build_estimate_approval_url(approval):
    base_url = get_frontend_base_url().rstrip("/")
    return f"{base_url}{approval.public_url_path}"


def send_estimate_approval_email(approval, public_url):
    estimate = approval.estimate
    customer = estimate.customer
    recipient = (approval.customer_email_snapshot or getattr(customer, "email", "") or "").strip()
    customer_name = approval.customer_name_snapshot or customer.full_name or "cliente"
    vehicle_display = estimate.vehicle.display_name if estimate.vehicle_id else "veículo não informado"
    subject = f"Aprovação digital - Orçamento {estimate.number}"
    message = (
        f"Olá {customer_name},\n\n"
        "A oficina gerou um orçamento para sua análise e aprovação digital.\n\n"
        f"Orçamento: {estimate.number}\n"
        f"Veículo: {vehicle_display}\n"
        f"Total: R$ {estimate.total_amount:.2f}\n"
        f"Validade: {approval.expires_at.strftime('%d/%m/%Y %H:%M') if approval.expires_at else 'sem validade definida'}\n\n"
        "No link abaixo você pode aprovar todos os serviços e peças ou escolher apenas os itens que deseja autorizar.\n"
        f"{public_url}\n\n"
        "Caso você não tenha solicitado este atendimento, ignore esta mensagem.\n"
    )
    if not recipient:
        return {
            "email_sent": False,
            "email_to": "",
            "email_backend": settings.EMAIL_BACKEND,
            "email_error": "Cliente sem e-mail cadastrado. O link foi gerado, mas não foi enviado.",
        }
    sent_count = send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
    return {"email_sent": bool(sent_count), "email_to": recipient, "email_backend": settings.EMAIL_BACKEND, "email_error": ""}


@transaction.atomic
def ensure_pending_estimate_approval(estimate, actor=None, expires_days=7):
    obj = Estimate.objects.select_for_update(of=("self",)).select_related("customer", "vehicle").prefetch_related("services", "parts").get(pk=estimate.pk)
    if obj.status not in ESTIMATE_APPROVAL_REQUEST_STATUSES:
        raise ValidationError("Somente orçamento em rascunho ou enviado pode gerar link de aprovação.")
    if not obj.customer_id:
        raise ValidationError({"customer_id": "Orçamento precisa estar vinculado a um cliente."})
    if not obj.vehicle_id:
        raise ValidationError({"vehicle_id": "Orçamento precisa estar vinculado a um veículo."})
    if not obj.services.exists():
        raise ValidationError("Inclua pelo menos um serviço no orçamento antes de enviar para aprovação.")
    obj.recalculate_totals(save=True)
    if obj.total_amount <= ZERO:
        raise ValidationError("Orçamento precisa ter valor maior que zero para aprovação digital.")
    approval = (
        EstimateCustomerApproval.objects
        .filter(estimate=obj, status=EstimateCustomerApproval.Status.PENDING, is_active=True)
        .order_by("-requested_at", "-id")
        .first()
    )
    if not approval:
        approval = EstimateCustomerApproval.objects.create(
            estimate=obj,
            requested_by=_actor_or_none(actor),
            expires_at=timezone.now() + timezone.timedelta(days=expires_days),
        )
    status_changed = obj.status != Estimate.Status.SENT
    if status_changed:
        old_status = obj.status
        obj.status = Estimate.Status.SENT
        obj.sent_at = obj.sent_at or timezone.now()
        obj.updated_by = _actor_or_none(actor) or obj.updated_by
        obj.save(update_fields=["status", "sent_at", "updated_by", "updated_at"])
        record_estimate_status_history(obj, old_status, obj.status, actor=actor, description="Orçamento enviado para aprovação do cliente.", data={"approval_id": approval.id})
        transaction.on_commit(lambda: trigger_estimate_status_notifications(Estimate.objects.select_related("customer", "vehicle").get(pk=obj.pk), actor=actor))
    return approval


def estimate_notification_context(estimate, actor=None, approval=None, work_order=None):
    profile = WorkshopProfile.get_solo()
    vehicle_display = estimate.vehicle.display_name if estimate.vehicle_id else ""
    customer = estimate.customer
    base = _estimate_extra_context(estimate, approval=approval, work_order=work_order)
    base.update(
        {
            "numero_orcamento": estimate.number,
            "status_orcamento": estimate.status_label,
            "total_orcamento": f"{estimate.total_amount:.2f}",
            "titulo_orcamento": estimate.title,
            "diagnostico_orcamento": estimate.diagnosis,
            "nome_cliente": customer.full_name,
            "email_cliente": customer.email,
            "telefone_cliente": customer.phone_e164,
            "veiculo_descricao": vehicle_display,
            "placa_veiculo": estimate.vehicle.plate if estimate.vehicle_id else "",
            "modelo_veiculo": estimate.vehicle.model if estimate.vehicle_id else "",
            "nome_oficina": profile.display_name,
            "email_oficina": profile.email,
            "telefone_oficina": profile.phone_e164,
            "oficina": {
                "nome": profile.display_name,
                "email": profile.email,
                "telefone": profile.phone_e164,
                "endereco": profile.address_display,
            },
            "customer": base.get("cliente", {}),
            "vehicle": base.get("veiculo", {}),
            "usuario_logado": {
                "full_name": actor.get_full_name() if getattr(actor, "is_authenticated", False) else "",
                "username": getattr(actor, "username", ""),
                "email": getattr(actor, "email", ""),
            },
        }
    )
    return base


def _estimate_notification_targets(rule):
    target = getattr(rule, "recipient_target", WorkOrderNotificationRule.RecipientTarget.CUSTOMER) if rule else WorkOrderNotificationRule.RecipientTarget.CUSTOMER
    if target == WorkOrderNotificationRule.RecipientTarget.BOTH:
        return [WorkOrderNotificationRule.RecipientTarget.CUSTOMER, WorkOrderNotificationRule.RecipientTarget.WORKSHOP]
    return [target]


def _recipient_kwargs_for_estimate(estimate, template, target):
    if target == WorkOrderNotificationRule.RecipientTarget.WORKSHOP:
        profile = WorkshopProfile.get_solo()
        if template.channel == MessageTemplate.Channel.EMAIL:
            if not profile.email:
                raise ValidationError({"oficina": "Oficina sem e-mail cadastrado no admin."})
            return {"contact": None, "raw_email": profile.email, "raw_phone": ""}
        if not profile.phone_e164:
            raise ValidationError({"oficina": "Oficina sem WhatsApp cadastrado no admin."})
        return {"contact": None, "raw_email": "", "raw_phone": profile.phone_e164}

    if template.channel == MessageTemplate.Channel.EMAIL:
        if not estimate.customer.email:
            raise ValidationError({"cliente": "Cliente sem email cadastrado."})
        return {"contact": estimate.customer, "raw_email": "", "raw_phone": ""}
    if not estimate.customer.phone_e164:
        raise ValidationError({"cliente": "Cliente sem WhatsApp em formato E.164."})
    return {"contact": estimate.customer, "raw_email": "", "raw_phone": ""}


def _create_failed_estimate_message(estimate, rule, actor, error_message):
    return WorkOrderMessage.objects.create(
        estimate=estimate,
        trigger_type=WorkOrderMessage.TriggerType.STATUS_AUTO,
        trigger_status=estimate.status,
        channel=getattr(rule, "channel", "") or getattr(getattr(rule, "template", None), "channel", ""),
        recipient_target=getattr(rule, "recipient_target", "") or "",
        template=getattr(rule, "template", None),
        notification_rule=rule,
        status=MessageLog.Status.FAILED,
        error_message=str(error_message),
        created_by=_actor_or_none(actor),
    )


def send_estimate_message(estimate, template, actor=None, notification_rule=None, recipient_target=None):
    targets = [recipient_target] if recipient_target else _estimate_notification_targets(notification_rule)
    created_relations = []
    for target in targets:
        kwargs = _recipient_kwargs_for_estimate(estimate, template, target)
        log = create_and_send(
            template=template,
            actor=actor,
            extra=estimate_notification_context(estimate, actor=actor),
            send_now=True,
            **kwargs,
        )
        relation = WorkOrderMessage.objects.create(
            estimate=estimate,
            trigger_type=WorkOrderMessage.TriggerType.STATUS_AUTO,
            trigger_status=estimate.status,
            channel=template.channel,
            recipient_target=target or "",
            template=template,
            notification_rule=notification_rule,
            message_log=log,
            status=log.status,
            error_message=log.error_message,
            created_by=_actor_or_none(actor),
        )
        created_relations.append(relation)
    return created_relations[0] if len(created_relations) == 1 else created_relations


def trigger_estimate_status_notifications(estimate, actor=None, status_value=None):
    sent = []
    original_status = estimate.status
    if status_value:
        estimate.status = status_value
    rules = list(
        WorkOrderNotificationRule.objects.select_related("template").filter(
            is_active=True,
            entity_type=WorkOrderNotificationRule.EntityType.ESTIMATE,
            trigger_status=estimate.status,
        )
    )
    for rule in rules:
        template = getattr(rule, "template", None)
        if not template:
            sent.append(_create_failed_estimate_message(estimate, rule, actor, "Template removido ou não encontrado.").id)
            continue
        if not template.is_active:
            sent.append(_create_failed_estimate_message(estimate, rule, actor, "Template inativo.").id)
            continue
        if rule.send_once_per_status:
            already_sent = WorkOrderMessage.objects.filter(
                estimate=estimate,
                notification_rule=rule,
                trigger_status=estimate.status,
                message_log__status=MessageLog.Status.SENT,
            ).exists()
            if already_sent:
                continue
        try:
            relation = send_estimate_message(estimate, template, actor=actor, notification_rule=rule)
            relations = relation if isinstance(relation, list) else [relation]
            sent.extend(item.id for item in relations)
        except Exception as exc:
            sent.append(_create_failed_estimate_message(estimate, rule, actor, exc).id)
    estimate.status = original_status
    return sent


def _estimate_extra_context(estimate, approval=None, work_order=None):
    return {
        "orcamento": {
            "id": estimate.id,
            "numero": estimate.number,
            "titulo": estimate.title,
            "status": estimate.status,
            "status_label": estimate.status_label,
            "total": estimate.total_amount,
            "aprovado_em": estimate.approved_at,
        },
        "estimate": {
            "id": estimate.id,
            "number": estimate.number,
            "title": estimate.title,
            "status": estimate.status,
            "status_label": estimate.status_label,
            "total_amount": estimate.total_amount,
            "approved_at": estimate.approved_at,
        },
        "cliente": {
            "nome": estimate.customer.full_name,
            "email": estimate.customer.email,
            "telefone": estimate.customer.phone_e164,
        },
        "veiculo": {
            "descricao": estimate.vehicle.display_name if estimate.vehicle_id else "",
        },
        "aprovacao": {
            "status": getattr(approval, "status", ""),
            "status_label": getattr(approval, "status_label", ""),
            "nome": getattr(approval, "decision_name", ""),
            "observacoes": getattr(approval, "decision_notes", ""),
        },
        "os": {
            "id": getattr(work_order, "id", ""),
            "numero": getattr(work_order, "number", ""),
            "status": getattr(work_order, "status", ""),
            "status_label": getattr(work_order, "status_label", ""),
        },
    }


def send_estimate_approval_whatsapp_to_workshop(estimate, approval, work_order=None, actor=None):
    profile = WorkshopProfile.get_solo()
    if not profile.phone_e164:
        return None
    template, _ = MessageTemplate.objects.get_or_create(
        slug="orcamento-aprovado-oficina-whatsapp",
        defaults={
            "name": "Orçamento aprovado - aviso para oficina",
            "channel": MessageTemplate.Channel.WHATSAPP,
            "description": "Aviso interno para a oficina quando cliente aprova total ou parcialmente um orçamento.",
            "whatsapp_body": (
                "✅ Orçamento {{ estimate.number }} aprovado por {{ aprovacao.nome }}.\n"
                "Status: {{ aprovacao.status_label }}\n"
                "Cliente: {{ cliente.nome }}\n"
                "Veículo: {{ veiculo.descricao }}\n"
                "Total aprovado registrado na OS {{ os.numero }}.\n"
                "Observações: {{ aprovacao.observacoes }}"
            ),
            "is_active": True,
        },
    )
    if template.channel != MessageTemplate.Channel.WHATSAPP:
        raise ValidationError("O template interno orcamento-aprovado-oficina-whatsapp precisa ser do canal WhatsApp.")
    return create_and_send(
        template=template,
        actor=actor,
        raw_phone=profile.phone_e164,
        extra=_estimate_extra_context(estimate, approval=approval, work_order=work_order),
        send_now=True,
    )




def _date_from_datetime(value):
    if not value:
        return None
    if hasattr(value, "date"):
        return value.date()
    if isinstance(value, str):
        parsed_dt = parse_datetime(value)
        if parsed_dt:
            return parsed_dt.date()
        parsed_date = parse_date(value)
        if parsed_date:
            return parsed_date
    return None


@transaction.atomic
def create_revision_estimate_from_work_order(work_order, payload=None, actor=None):
    """Cria um novo orçamento de revisão para uma OS já aprovada.

    A OS aprovada não é alterada diretamente. O orçamento gerado passa pelo
    mesmo fluxo de aprovação do atendimento; quando aprovado, ele atualiza a OS
    existente e a recoloca como aberta.
    """
    payload = payload or {}
    order = (
        WorkOrder.objects.select_for_update(of=("self",))
        .select_related("customer", "vehicle")
        .prefetch_related("services__service", "services__source_package", "parts__part", "parts__linked_service")
        .get(pk=work_order.pk)
    )
    editable_statuses = {WorkOrder.Status.OPEN, WorkOrder.Status.IN_PROGRESS, WorkOrder.Status.WAITING_PARTS, WorkOrder.Status.AWAITING_APPROVAL, WorkOrder.Status.PAUSED}
    if order.status not in editable_statuses:
        raise ValidationError("Somente OS aberta, em execução ou aguardando peças pode gerar orçamento de revisão.")
    if not order.approved_at:
        raise ValidationError("Esta OS ainda não está aprovada. Edite a OS diretamente enquanto ela estiver aberta, em execução ou aguardando peças.")

    title = payload.get("title", order.title) or f"Revisão da OS {order.number}"
    complaint = payload.get("complaint", order.complaint) or ""
    diagnosis = payload.get("diagnosis", order.diagnosis) or ""
    internal_notes = payload.get("internal_notes", order.internal_notes) or ""
    customer_notes = payload.get("customer_notes", order.customer_notes) or ""
    promised_at = payload.get("promised_at") or order.promised_at
    valid_until = _date_from_datetime(promised_at) or (timezone.localdate() + timezone.timedelta(days=7))
    manual_discount = payload.get("manual_discount_amount", order.manual_discount_amount or ZERO) or ZERO

    estimate = Estimate.objects.create(
        customer=order.customer,
        vehicle=order.vehicle,
        title=title,
        complaint=complaint,
        diagnosis=diagnosis,
        internal_notes=(
            f"Orçamento de revisão gerado a partir da OS aprovada {order.number}.\n"
            f"{internal_notes}"
        ).strip(),
        customer_notes=customer_notes,
        status=Estimate.Status.DRAFT,
        valid_until=valid_until,
        discount_amount=manual_discount,
        revision_work_order=order,
        created_by=_actor_or_none(actor),
        updated_by=_actor_or_none(actor),
    )

    initial_services = payload.get("initial_service_items") or []
    if initial_services:
        for item in initial_services:
            service = item.get("service") or item.get("service_id")
            source_package = item.get("source_package") or item.get("source_package_id")
            estimate.services.create(
                service=service if hasattr(service, "pk") else None,
                source_package=source_package if hasattr(source_package, "pk") else None,
                description=item.get("description") or "Serviço",
                quantity=item.get("quantity") or Decimal("1.00"),
                unit_price=item.get("unit_price") or ZERO,
                discount_amount=item.get("discount_amount") or ZERO,
                notes=item.get("notes") or "",
            )
    else:
        service_map = {}
        for line in order.services.all():
            new_line = estimate.services.create(
                service=line.service,
                source_package=line.source_package,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount_amount=line.discount_amount,
                notes=line.notes,
            )
            service_map[line.id] = new_line
        for line in order.parts.all():
            estimate.parts.create(
                service_item=service_map.get(line.linked_service_id),
                part=line.part,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                cost_price=line.cost_price,
                discount_amount=line.discount_amount,
                notes=line.notes,
            )

    estimate.recalculate_totals(save=True)
    record_event(
        order,
        WorkOrderEvent.EventType.UPDATED,
        actor=actor,
        description=f"Gerado orçamento de revisão {estimate.number} para nova aprovação da OS aprovada.",
        data={"estimate_id": estimate.id, "estimate_number": estimate.number},
    )
    return estimate




@transaction.atomic
def apply_approved_estimate_to_existing_work_order(estimate, actor=None, selected_service_ids=None, selected_part_ids=None, approval=None):
    obj = (
        Estimate.objects.select_for_update(of=("self",))
        .select_related("customer", "vehicle", "revision_work_order")
        .prefetch_related("services", "parts")
        .get(pk=estimate.pk)
    )
    if not obj.revision_work_order_id:
        raise ValidationError("Este orçamento não está vinculado a uma OS existente.")
    work_order = WorkOrder.objects.select_for_update(of=("self",)).get(pk=obj.revision_work_order_id)
    services = list(obj.services.select_related("service", "source_package"))
    parts = list(obj.parts.select_related("part", "service_item"))
    if selected_service_ids is None:
        selected_service_ids = [item.id for item in services]
    if selected_part_ids is None:
        selected_part_ids = [item.id for item in parts]
    selected_service_ids = {int(item_id) for item_id in selected_service_ids}
    selected_part_ids = {int(item_id) for item_id in selected_part_ids}
    selected_services = [item for item in services if item.id in selected_service_ids]
    if not selected_services:
        raise ValidationError("A aprovação precisa conter pelo menos um serviço para atualizar a OS.")
    selected_service_id_set = {item.id for item in selected_services}
    selected_parts = [
        item for item in parts
        if item.id in selected_part_ids and (not item.service_item_id or item.service_item_id in selected_service_id_set)
    ]

    work_order.customer = obj.customer
    work_order.vehicle = obj.vehicle
    work_order.title = obj.title
    work_order.complaint = obj.complaint
    work_order.diagnosis = obj.diagnosis
    work_order.customer_notes = obj.customer_notes
    work_order.internal_notes = (
        f"OS atualizada pelo orçamento de revisão aprovado {obj.number}.\n"
        f"{obj.internal_notes}"
    ).strip()
    work_order.manual_discount_amount = obj.discount_amount or ZERO
    work_order.status = WorkOrder.Status.OPEN
    work_order.source_estimate_id = obj.id
    work_order.source_estimate_number = obj.number
    work_order.updated_by = _actor_or_none(actor) or work_order.updated_by
    work_order.save(update_fields=[
        "customer", "vehicle", "title", "complaint", "diagnosis", "customer_notes",
        "internal_notes", "manual_discount_amount", "status", "source_estimate_id",
        "source_estimate_number", "updated_by", "updated_at",
    ])

    work_order.services.all().delete()
    work_order.parts.all().delete()
    service_map = {}
    for item in selected_services:
        line = WorkOrderService.objects.create(
            work_order=work_order,
            service=item.service,
            source_package=item.source_package,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_amount=item.discount_amount,
            notes=item.notes,
            status=WorkOrderService.Status.PENDING,
        )
        service_map[item.id] = line
    for item in selected_parts:
        WorkOrderPart.objects.create(
            work_order=work_order,
            linked_service=service_map.get(item.service_item_id),
            part=item.part,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            cost_price=item.cost_price,
            discount_amount=item.discount_amount,
            notes=item.notes,
        )
    work_order.recalculate_totals(save=True)
    reservation_summary = reserve_parts_for_work_order(work_order, actor=actor, source_estimate=obj)
    from purchasing.services import ensure_purchases_for_work_order_shortages
    purchase_summary = ensure_purchases_for_work_order_shortages(work_order, actor=actor)
    record_event(
        work_order,
        WorkOrderEvent.EventType.UPDATED,
        actor=actor,
        description=f"OS reaberta e atualizada pelo orçamento aprovado {obj.number}.",
        old_status="",
        new_status=work_order.status,
        data={
            "estimate_id": obj.id,
            "estimate_number": obj.number,
            "approved_service_ids": sorted(selected_service_ids),
            "approved_part_ids": sorted(selected_part_ids),
            "approval_id": getattr(approval, "id", None),
            "reservation_summary": reservation_summary,
            "purchase_summary": purchase_summary,
        },
    )
    old_status = obj.status
    obj.status = Estimate.Status.CONVERTED
    obj.converted_at = timezone.now()
    obj.updated_by = _actor_or_none(actor) or obj.updated_by
    obj.save(update_fields=["status", "converted_at", "updated_by", "updated_at"])
    record_estimate_status_history(obj, old_status, obj.status, actor=actor, description=f"Orçamento de revisão aplicado na OS {work_order.number}.", data={"work_order_id": work_order.id})
    if approval and not EstimateCustomerApproval.objects.filter(generated_work_order=work_order).exclude(pk=approval.pk).exists():
        approval.generated_work_order = work_order
        approval.save(update_fields=["generated_work_order", "updated_at"])
    return work_order


@transaction.atomic
def convert_estimate_to_work_order(estimate, actor=None, selected_service_ids=None, selected_part_ids=None, approval=None):
    obj = Estimate.objects.select_for_update(of=("self",)).select_related("customer", "vehicle").prefetch_related("services", "parts").get(pk=estimate.pk)
    if obj.status != Estimate.Status.APPROVED:
        raise ValidationError("Somente orçamento aprovado pode ser convertido em OS.")
    if not obj.customer_id:
        raise ValidationError({"customer_id": "Orçamento precisa estar vinculado a um cliente para gerar OS."})
    if not obj.vehicle_id:
        raise ValidationError({"vehicle_id": "Orçamento precisa estar vinculado a um veículo para gerar OS."})
    if obj.converted_work_order_id:
        raise ValidationError("Este orçamento já gerou uma ordem de serviço e não pode gerar outra.")
    if obj.revision_work_order_id:
        return apply_approved_estimate_to_existing_work_order(obj, actor=actor, selected_service_ids=selected_service_ids, selected_part_ids=selected_part_ids, approval=approval)

    services = list(obj.services.select_related("service", "source_package"))
    parts = list(obj.parts.select_related("part", "service_item"))
    if selected_service_ids is None:
        selected_service_ids = [item.id for item in services if item.approved_by_customer]
    if selected_part_ids is None:
        selected_part_ids = [item.id for item in parts if item.approved_by_customer]
    selected_service_ids = {int(item_id) for item_id in selected_service_ids}
    selected_part_ids = {int(item_id) for item_id in selected_part_ids}
    selected_services = [item for item in services if item.id in selected_service_ids]
    if not selected_services:
        raise ValidationError("A aprovação precisa conter pelo menos um serviço para gerar OS.")
    selected_service_id_set = {item.id for item in selected_services}
    selected_parts = [
        item for item in parts
        if item.id in selected_part_ids and (not item.service_item_id or item.service_item_id in selected_service_id_set)
    ]

    obj.recalculate_totals(save=True)
    work_order = WorkOrder.objects.create(
        customer=obj.customer,
        vehicle=obj.vehicle,
        title=obj.title,
        complaint=obj.complaint,
        diagnosis=obj.diagnosis,
        customer_notes=obj.customer_notes,
        internal_notes=f"OS aberta automaticamente a partir do orçamento aprovado {obj.number}.\n{obj.internal_notes}".strip(),
        status=WorkOrder.Status.OPEN,
        financial_status=WorkOrder.FinancialStatus.PENDING,
        promised_at=None,
        manual_discount_amount=obj.discount_amount or ZERO,
        source_estimate_id=obj.id,
        source_estimate_number=obj.number,
        created_by=_actor_or_none(actor),
        updated_by=_actor_or_none(actor),
    )
    service_map = {}
    for item in selected_services:
        line = WorkOrderService.objects.create(
            work_order=work_order,
            service=item.service,
            source_package=item.source_package,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_amount=item.discount_amount,
            notes=item.notes,
            status=WorkOrderService.Status.PENDING,
        )
        service_map[item.id] = line
    for item in selected_parts:
        WorkOrderPart.objects.create(
            work_order=work_order,
            linked_service=service_map.get(item.service_item_id),
            part=item.part,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            cost_price=item.cost_price,
            discount_amount=item.discount_amount,
            notes=item.notes,
        )
    work_order.recalculate_totals(save=True)
    reservation_summary = reserve_parts_for_work_order(work_order, actor=actor, source_estimate=obj)
    from purchasing.services import ensure_purchases_for_work_order_shortages
    purchase_summary = ensure_purchases_for_work_order_shortages(work_order, actor=actor)
    work_order.refresh_from_db()
    record_event(
        work_order,
        WorkOrderEvent.EventType.CREATED,
        actor=actor,
        description=f"OS aberta a partir do orçamento {obj.number} com itens aprovados pelo cliente.",
        new_status=work_order.status,
        data={
            "estimate_id": obj.id,
            "estimate_number": obj.number,
            "approved_service_ids": sorted(selected_service_ids),
            "approved_part_ids": sorted(selected_part_ids),
            "approval_id": getattr(approval, "id", None),
            "reservation_summary": reservation_summary,
            "purchase_summary": purchase_summary,
        },
    )
    old_status = obj.status
    obj.status = Estimate.Status.CONVERTED
    obj.converted_work_order = work_order
    obj.converted_at = timezone.now()
    obj.updated_by = _actor_or_none(actor) or obj.updated_by
    obj.save(update_fields=["status", "converted_work_order", "converted_at", "updated_by", "updated_at"])
    record_estimate_status_history(obj, old_status, obj.status, actor=actor, description=f"Orçamento convertido na OS {work_order.number}.", data={"work_order_id": work_order.id})
    transaction.on_commit(lambda: trigger_estimate_status_notifications(Estimate.objects.select_related("customer", "vehicle").get(pk=obj.pk), actor=actor))
    if approval:
        approval.generated_work_order = work_order
        approval.save(update_fields=["generated_work_order", "updated_at"])
    return work_order


@transaction.atomic
def decide_estimate_approval(approval, decision, selected_service_ids, selected_part_ids, name="", document="", notes="", confirm_partial=False, ip_address=None, user_agent="", actor=None):
    obj = EstimateCustomerApproval.objects.select_for_update(of=("self",)).select_related("estimate__customer", "estimate__vehicle").get(pk=approval.pk)
    if not obj.can_decide:
        raise ValidationError({"status": "Este link não está mais disponível para decisão."})
    estimate = Estimate.objects.select_for_update(of=("self",)).prefetch_related("services", "parts").get(pk=obj.estimate_id)
    document = (document or "").strip()
    digits = "".join(ch for ch in document if ch.isdigit())
    if len(digits) not in (11, 14):
        raise ValidationError({"document": "Informe um CPF com 11 dígitos ou CNPJ com 14 dígitos."})
    if not (notes or "").strip():
        raise ValidationError({"notes": "Informe uma observação para registrar a decisão."})
    old_estimate_status = estimate.status
    if decision == EstimateCustomerApproval.Status.REJECTED:
        obj.status = EstimateCustomerApproval.Status.REJECTED
        estimate.status = Estimate.Status.REJECTED
        estimate.rejected_at = timezone.now()
        estimate.rejection_reason = notes
        work_order = None
    elif decision in {EstimateCustomerApproval.Status.APPROVED, "approved"}:
        services = list(estimate.services.all())
        parts = list(estimate.parts.all())
        all_service_ids = {item.id for item in services}
        all_part_ids = {item.id for item in parts}
        selected_service_ids = {int(item_id) for item_id in selected_service_ids}
        selected_part_ids = {int(item_id) for item_id in selected_part_ids}
        invalid_services = selected_service_ids - all_service_ids
        invalid_parts = selected_part_ids - all_part_ids
        if invalid_services or invalid_parts:
            raise ValidationError("A seleção contém itens que não pertencem a este orçamento.")
        if not selected_service_ids:
            raise ValidationError({"selected_service_ids": "Selecione pelo menos um serviço para aprovar o orçamento."})
        linked_parts = {item.id for item in parts if item.service_item_id and item.service_item_id in selected_service_ids}
        orphan_parts = {item.id for item in parts if not item.service_item_id}
        valid_part_ids = linked_parts | orphan_parts
        selected_part_ids = selected_part_ids & valid_part_ids
        is_partial = selected_service_ids != all_service_ids or selected_part_ids != all_part_ids
        if is_partial and not confirm_partial:
            raise ValidationError({"confirm_partial": "Você desmarcou um ou mais itens. Confirme que deseja aprovar parcialmente este orçamento."})
        obj.status = EstimateCustomerApproval.Status.PARTIALLY_APPROVED if is_partial else EstimateCustomerApproval.Status.APPROVED
        estimate.status = Estimate.Status.APPROVED
        estimate.approved_at = timezone.now()
        estimate.approved_by = (name or obj.customer_name_snapshot or "Cliente").strip()[:180]
        estimate.approval_method = "public_link"
        now = timezone.now()
        estimate.services.update(approved_by_customer=False, customer_decided_at=now)
        estimate.parts.update(approved_by_customer=False, customer_decided_at=now)
        estimate.services.filter(id__in=selected_service_ids).update(approved_by_customer=True, customer_decided_at=now)
        estimate.parts.filter(id__in=selected_part_ids).update(approved_by_customer=True, customer_decided_at=now)
        estimate.save(update_fields=["status", "approved_at", "approved_by", "approval_method", "updated_at"])
        record_estimate_status_history(estimate, old_estimate_status, estimate.status, actor=actor, description="Orçamento aprovado pelo link público.", data={"approval_id": obj.id, "partial": is_partial})
        obj.decision_selected_services = sorted(selected_service_ids)
        obj.decision_selected_parts = sorted(selected_part_ids)
        obj.decision_name = (name or "").strip()[:180]
        obj.decision_document = document[:30]
        obj.decision_notes = notes
        obj.decision_ip = ip_address
        obj.decision_user_agent = (user_agent or "")[:2000]
        obj.decided_at = timezone.now()
        obj.save(update_fields=["status", "decision_selected_services", "decision_selected_parts", "decision_name", "decision_document", "decision_notes", "decision_ip", "decision_user_agent", "decided_at", "updated_at"])
        approved_status_for_notifications = estimate.status
        transaction.on_commit(
            lambda: trigger_estimate_status_notifications(
                Estimate.objects.select_related("customer", "vehicle").get(pk=estimate.pk),
                actor=actor,
                status_value=approved_status_for_notifications,
            )
        )
        work_order = convert_estimate_to_work_order(estimate, actor=actor, selected_service_ids=selected_service_ids, selected_part_ids=selected_part_ids, approval=obj)

        def notify_workshop_after_commit():
            try:
                send_estimate_approval_whatsapp_to_workshop(
                    Estimate.objects.get(pk=estimate.pk),
                    EstimateCustomerApproval.objects.get(pk=obj.pk),
                    work_order=work_order,
                    actor=actor,
                )
            except Exception as exc:
                record_event(
                    work_order,
                    WorkOrderEvent.EventType.ERROR,
                    actor=actor,
                    description=f"Falha ao enviar WhatsApp interno de aprovação do orçamento: {exc}",
                    data={"estimate_id": estimate.id, "approval_id": obj.id, "error": str(exc)},
                )

        transaction.on_commit(notify_workshop_after_commit)
        return obj, work_order
    else:
        raise ValidationError({"decision": "Decisão inválida."})

    obj.decision_name = (name or "").strip()[:180]
    obj.decision_document = document[:30]
    obj.decision_notes = notes
    obj.decision_ip = ip_address
    obj.decision_user_agent = (user_agent or "")[:2000]
    obj.decided_at = timezone.now()
    obj.save(update_fields=["status", "decision_name", "decision_document", "decision_notes", "decision_ip", "decision_user_agent", "decided_at", "updated_at"])
    estimate.save(update_fields=["status", "rejected_at", "rejection_reason", "updated_at"])
    record_estimate_status_history(estimate, old_estimate_status, estimate.status, actor=actor, description="Orçamento recusado pelo link público.", data={"approval_id": obj.id})
    return obj, work_order
