from calendar import monthrange
from decimal import Decimal
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.audit import audit_financial_event, model_snapshot, require_audit_reason
from accounts.models import AuditLog
from purchasing.models import PurchaseOrder
from workshop.models import WorkOrder, WorkOrderEvent, WorkOrderPayment
from workshop.services import record_event

from .ledger import record_ledger_entry
from .models import AccountPayable, AccountPayablePayment, AccountReceivable, AccountReceivablePayment, FinancialLedgerEntry

ZERO = Decimal("0.00")

WORK_ORDER_FINANCIAL_FIELDS = [
    "number",
    "status",
    "manual_discount_amount",
    "discount_total",
    "grand_total",
    "paid_total",
    "balance_due",
]
RECEIVABLE_AUDIT_FIELDS = [
    "number",
    "origin",
    "description",
    "issue_date",
    "due_date",
    "amount",
    "discount_amount",
    "paid_amount",
    "balance_amount",
    "status",
]
PAYABLE_AUDIT_FIELDS = [
    "number",
    "origin",
    "recurrence_type",
    "category",
    "description",
    "issue_date",
    "due_date",
    "amount",
    "paid_amount",
    "balance_amount",
    "status",
]
PAYMENT_AUDIT_FIELDS = [
    "method",
    "amount",
    "paid_at",
    "reference",
    "notes",
    "reversed_at",
    "reversal_reason",
]
LEDGER_AUDIT_FIELDS = [
    "entry_type",
    "origin",
    "origin_model",
    "origin_id",
    "description",
    "amount",
    "competence_date",
    "occurred_at",
    "payment_method",
    "reference",
    "notes",
]


def default_due_date_for_work_order(work_order):
    if work_order.delivered_at:
        return timezone.localtime(work_order.delivered_at).date()
    if work_order.promised_at:
        return timezone.localtime(work_order.promised_at).date()
    return timezone.localdate()


def add_months(value, months=1):
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _ledger_entry_for_payment(payment):
    return (
        FinancialLedgerEntry.objects.filter(
            origin_model=payment._meta.label_lower,
            origin_id=str(payment.pk),
            reversal_of__isnull=True,
        )
        .exclude(entry_type=FinancialLedgerEntry.EntryType.REVERSAL)
        .order_by("-occurred_at", "-id")
        .first()
    )


def _audit_ledger_entry(entry, *, actor=None, description="Lançamento financeiro registrado."):
    if not entry:
        return None
    return audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_PAYMENT if entry.entry_type != FinancialLedgerEntry.EntryType.REVERSAL else AuditLog.Action.FINANCIAL_REVERSAL,
        instance=entry,
        user=actor,
        description=description,
        before={},
        after=model_snapshot(entry, LEDGER_AUDIT_FIELDS),
        metadata={"ledger_entry_id": entry.id, "origin_model": entry.origin_model, "origin_id": entry.origin_id},
    )


def _record_reversal_ledger_for_payment(payment, *, actor=None, reason=""):
    original_entry = _ledger_entry_for_payment(payment)
    reversal = record_ledger_entry(
        entry_type=FinancialLedgerEntry.EntryType.REVERSAL,
        origin=original_entry.origin if original_entry else FinancialLedgerEntry.Origin.SYSTEM,
        origin_instance=payment,
        description=f"Estorno: {original_entry.description if original_entry else str(payment)}",
        amount=payment.amount,
        occurred_at=timezone.now(),
        competence_date=timezone.localdate(),
        payment_method=getattr(payment, "method", ""),
        reference=getattr(payment, "reference", ""),
        notes=reason,
        actor=actor,
        reversal_of=original_entry,
    )
    _audit_ledger_entry(reversal, actor=actor, description="Lançamento de estorno registrado.")
    return reversal


@transaction.atomic
def ensure_receivable_for_work_order(work_order, actor=None):
    locked_order = WorkOrder.objects.select_for_update(of=("self",)).select_related("customer", "vehicle").get(pk=work_order.pk)
    locked_order.recalculate_totals(save=True)
    receivable, created = AccountReceivable.objects.select_for_update(of=("self",)).get_or_create(
        work_order=locked_order,
        defaults={
            "origin": AccountReceivable.Origin.WORK_ORDER,
            "customer": locked_order.customer,
            "description": f"Conta a receber da {locked_order.number}",
            "issue_date": timezone.localdate(),
            "due_date": default_due_date_for_work_order(locked_order),
            "amount": locked_order.grand_total or ZERO,
            "discount_amount": locked_order.discount_total or ZERO,
            "paid_amount": locked_order.paid_total or ZERO,
            "created_by": actor if getattr(actor, "is_authenticated", False) else None,
            "updated_by": actor if getattr(actor, "is_authenticated", False) else None,
        },
    )
    before = {} if created else model_snapshot(receivable, RECEIVABLE_AUDIT_FIELDS)
    receivable.customer = locked_order.customer
    receivable.description = f"Conta a receber da {locked_order.number}"
    receivable.due_date = default_due_date_for_work_order(locked_order)
    receivable.updated_by = actor if getattr(actor, "is_authenticated", False) else receivable.updated_by
    receivable.recalculate(save=True)
    receivable.refresh_from_db()
    audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_CREATE if created else AuditLog.Action.FINANCIAL_UPDATE,
        instance=receivable,
        user=actor,
        description="Conta a receber da OS gerada." if created else "Conta a receber da OS atualizada.",
        before=before,
        after=model_snapshot(receivable, RECEIVABLE_AUDIT_FIELDS),
        metadata={"work_order_id": locked_order.id, "work_order_number": locked_order.number},
    )
    record_event(
        locked_order,
        WorkOrderEvent.EventType.PAYMENT_ADDED,
        actor=actor,
        description=("Conta a receber gerada." if created else "Conta a receber atualizada."),
        data={"account_receivable_id": receivable.id, "account_receivable_number": receivable.number, "amount": str(receivable.amount)},
    )
    return receivable


def refresh_receivable_for_work_order(work_order):
    receivable = getattr(work_order, "account_receivable", None)
    if receivable:
        receivable.recalculate(save=True)
    return receivable


@transaction.atomic
def create_manual_receivable(*, customer=None, description, issue_date=None, due_date, amount, discount_amount=ZERO, notes="", actor=None):
    amount = Decimal(str(amount))
    discount_amount = Decimal(str(discount_amount or ZERO))
    if amount <= ZERO:
        raise ValidationError("O valor da conta a receber precisa ser maior que zero.")
    if discount_amount < ZERO:
        raise ValidationError("O desconto não pode ser negativo.")
    if discount_amount > amount:
        raise ValidationError("O desconto não pode ser maior que o valor da conta.")
    receivable = AccountReceivable.objects.create(
        origin=AccountReceivable.Origin.MANUAL,
        customer=customer,
        description=description,
        issue_date=issue_date or timezone.localdate(),
        due_date=due_date,
        amount=amount,
        discount_amount=discount_amount,
        notes=notes,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
        updated_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    receivable.recalculate(save=True)
    receivable.refresh_from_db()
    audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_CREATE,
        instance=receivable,
        user=actor,
        description="Conta a receber manual criada.",
        before={},
        after=model_snapshot(receivable, RECEIVABLE_AUDIT_FIELDS),
        metadata={"customer_id": customer.id if customer else None},
    )
    if discount_amount > ZERO:
        audit_financial_event(
            event_type=AuditLog.Action.FINANCIAL_DISCOUNT,
            instance=receivable,
            user=actor,
            description="Desconto financeiro aplicado na criação da conta a receber.",
            before={"discount_amount": "0.00"},
            after={"discount_amount": str(discount_amount)},
            metadata={"customer_id": customer.id if customer else None},
        )
    return receivable


@transaction.atomic
def register_receivable_payment(receivable, amount, method, paid_at=None, reference="", notes="", actor=None):
    amount = Decimal(str(amount))
    if receivable.work_order_id:
        work_order = WorkOrder.objects.select_for_update(of=("self",)).get(pk=receivable.work_order_id)
        before_order = model_snapshot(work_order, WORK_ORDER_FINANCIAL_FIELDS)
        work_order.recalculate_totals(save=True)
        if amount <= ZERO:
            raise ValidationError("O valor recebido precisa ser maior que zero.")
        if amount > work_order.balance_due:
            raise ValidationError("O valor recebido não pode ser maior que o saldo da OS.")
        payment = WorkOrderPayment.objects.create(
            work_order=work_order,
            method=method,
            amount=amount,
            paid_at=paid_at or timezone.now(),
            reference=reference,
            notes=notes,
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
        receivable.refresh_from_db()
        receivable_before = model_snapshot(receivable, RECEIVABLE_AUDIT_FIELDS)
        receivable.recalculate(save=True)
        receivable.refresh_from_db()
        work_order.refresh_from_db()
        ledger_entry = record_ledger_entry(
            entry_type=FinancialLedgerEntry.EntryType.CREDIT,
            origin=FinancialLedgerEntry.Origin.WORK_ORDER,
            origin_instance=payment,
            description=f"Recebimento da {receivable.work_order.number}",
            amount=payment.amount,
            occurred_at=payment.paid_at,
            competence_date=payment.paid_at.date(),
            payment_method=payment.method,
            reference=payment.reference,
            notes=payment.notes,
            actor=actor,
        )
        audit_financial_event(
            event_type=AuditLog.Action.FINANCIAL_PAYMENT,
            instance=payment,
            user=actor,
            description=f"Recebimento de OS registrado: {payment.amount}.",
            before={},
            after=model_snapshot(payment, PAYMENT_AUDIT_FIELDS),
            metadata={"work_order_id": work_order.id, "work_order_number": work_order.number, "account_receivable_id": receivable.id, "ledger_entry_id": ledger_entry.id if ledger_entry else None},
        )
        audit_financial_event(
            event_type=AuditLog.Action.FINANCIAL_UPDATE,
            instance=receivable,
            user=actor,
            description="Conta a receber atualizada por recebimento de OS.",
            before=receivable_before,
            after=model_snapshot(receivable, RECEIVABLE_AUDIT_FIELDS),
            metadata={"payment_id": payment.id, "ledger_entry_id": ledger_entry.id if ledger_entry else None},
        )
        audit_financial_event(
            event_type=AuditLog.Action.FINANCIAL_PAYMENT,
            instance=work_order,
            user=actor,
            description="Totais financeiros da OS atualizados por recebimento.",
            before=before_order,
            after=model_snapshot(work_order, WORK_ORDER_FINANCIAL_FIELDS),
            metadata={"payment_id": payment.id, "account_receivable_id": receivable.id, "ledger_entry_id": ledger_entry.id if ledger_entry else None},
        )
        _audit_ledger_entry(ledger_entry, actor=actor)
        record_event(
            receivable.work_order,
            WorkOrderEvent.EventType.PAYMENT_ADDED,
            actor=actor,
            description=f"Recebimento financeiro registrado: {payment.amount}.",
            data={"payment_id": payment.id, "account_receivable_id": receivable.id, "method": payment.method, "amount": str(payment.amount), "ledger_entry_id": ledger_entry.id if ledger_entry else None},
        )
        return payment, receivable
    if receivable.counter_sale_id:
        from attendance.services import register_counter_sale_payment

        payment, _sale = register_counter_sale_payment(
            receivable.counter_sale,
            amount=amount,
            method=method,
            paid_at=paid_at or timezone.now(),
            reference=reference,
            notes=notes,
            actor=actor,
        )
        before_receivable = model_snapshot(receivable, RECEIVABLE_AUDIT_FIELDS)
        receivable.refresh_from_db()
        receivable.recalculate(save=True)
        receivable.refresh_from_db()
        ledger_entry = record_ledger_entry(
            entry_type=FinancialLedgerEntry.EntryType.CREDIT,
            origin=FinancialLedgerEntry.Origin.COUNTER_SALE,
            origin_instance=payment,
            description=f"Recebimento da venda balcão {receivable.counter_sale.number}",
            amount=payment.amount,
            occurred_at=payment.paid_at,
            competence_date=payment.paid_at.date(),
            payment_method=payment.method,
            reference=payment.reference,
            notes=payment.notes,
            actor=actor,
        )
        audit_financial_event(
            event_type=AuditLog.Action.FINANCIAL_PAYMENT,
            instance=receivable,
            user=actor,
            description="Conta a receber atualizada por recebimento de venda avulsa.",
            before=before_receivable,
            after=model_snapshot(receivable, RECEIVABLE_AUDIT_FIELDS),
            metadata={"payment_id": payment.id, "counter_sale_id": receivable.counter_sale_id, "ledger_entry_id": ledger_entry.id if ledger_entry else None},
        )
        _audit_ledger_entry(ledger_entry, actor=actor)
        return payment, receivable
    locked_receivable = AccountReceivable.objects.select_for_update(of=("self",)).get(pk=receivable.pk)
    if locked_receivable.status == AccountReceivable.Status.CANCELLED:
        raise ValidationError("Conta a receber cancelada não pode receber pagamento.")
    if locked_receivable.origin != AccountReceivable.Origin.MANUAL:
        raise ValidationError("Esta conta a receber não aceita recebimento manual direto.")
    locked_receivable.recalculate(save=True)
    if amount <= ZERO:
        raise ValidationError("O valor recebido precisa ser maior que zero.")
    if amount > locked_receivable.balance_amount:
        raise ValidationError("O valor recebido não pode ser maior que o saldo da conta.")
    before_receivable = model_snapshot(locked_receivable, RECEIVABLE_AUDIT_FIELDS)
    payment = AccountReceivablePayment.objects.create(
        account_receivable=locked_receivable,
        method=method,
        amount=amount,
        paid_at=paid_at or timezone.now(),
        reference=reference,
        notes=notes,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    locked_receivable.refresh_from_db()
    locked_receivable.recalculate(save=True)
    locked_receivable.refresh_from_db()
    ledger_entry = record_ledger_entry(
        entry_type=FinancialLedgerEntry.EntryType.CREDIT,
        origin=FinancialLedgerEntry.Origin.RECEIVABLE,
        origin_instance=payment,
        description=f"Recebimento da conta {locked_receivable.number}",
        amount=payment.amount,
        occurred_at=payment.paid_at,
        competence_date=payment.paid_at.date(),
        payment_method=payment.method,
        reference=payment.reference,
        notes=payment.notes,
        actor=actor,
    )
    audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_PAYMENT,
        instance=payment,
        user=actor,
        description=f"Recebimento manual registrado: {payment.amount}.",
        before={},
        after=model_snapshot(payment, PAYMENT_AUDIT_FIELDS),
        metadata={"account_receivable_id": locked_receivable.id, "ledger_entry_id": ledger_entry.id if ledger_entry else None},
    )
    audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_UPDATE,
        instance=locked_receivable,
        user=actor,
        description="Conta a receber atualizada por recebimento manual.",
        before=before_receivable,
        after=model_snapshot(locked_receivable, RECEIVABLE_AUDIT_FIELDS),
        metadata={"payment_id": payment.id, "ledger_entry_id": ledger_entry.id if ledger_entry else None},
    )
    _audit_ledger_entry(ledger_entry, actor=actor)
    return payment, locked_receivable


@transaction.atomic
def reverse_receivable_payment(payment, *, reason, actor=None):
    reason = require_audit_reason(reason)
    locked_payment = AccountReceivablePayment.objects.select_for_update(of=("self",)).select_related("account_receivable").get(pk=payment.pk)
    if locked_payment.reversed_at:
        raise ValidationError("Este recebimento já foi estornado.")
    account = AccountReceivable.objects.select_for_update(of=("self",)).get(pk=locked_payment.account_receivable_id)
    before_payment = model_snapshot(locked_payment, PAYMENT_AUDIT_FIELDS)
    before_account = model_snapshot(account, RECEIVABLE_AUDIT_FIELDS)
    locked_payment.reversed_at = timezone.now()
    locked_payment.reversed_by = actor if getattr(actor, "is_authenticated", False) else None
    locked_payment.reversal_reason = reason
    locked_payment.save(update_fields=["reversed_at", "reversed_by", "reversal_reason", "updated_at"])
    account.refresh_from_db()
    account.recalculate(save=True)
    account.refresh_from_db()
    reversal = _record_reversal_ledger_for_payment(locked_payment, actor=actor, reason=reason)
    audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_REVERSAL,
        instance=locked_payment,
        user=actor,
        description=f"Recebimento estornado: {locked_payment.amount}.",
        before=before_payment,
        after=model_snapshot(locked_payment, PAYMENT_AUDIT_FIELDS),
        metadata={"account_receivable_id": account.id, "reversal_ledger_entry_id": reversal.id if reversal else None},
        reason=reason,
    )
    audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_UPDATE,
        instance=account,
        user=actor,
        description="Conta a receber atualizada por estorno.",
        before=before_account,
        after=model_snapshot(account, RECEIVABLE_AUDIT_FIELDS),
        metadata={"payment_id": locked_payment.id, "reversal_ledger_entry_id": reversal.id if reversal else None},
        reason=reason,
    )
    return locked_payment, account


@transaction.atomic
def ensure_payable_for_purchase_order(purchase_order, actor=None):
    locked_order = PurchaseOrder.objects.select_for_update(of=("self",)).select_related("supplier").prefetch_related("items").get(pk=purchase_order.pk)
    if locked_order.status not in {
        PurchaseOrder.Status.APPROVED,
        PurchaseOrder.Status.ORDERED,
        PurchaseOrder.Status.PARTIALLY_RECEIVED,
        PurchaseOrder.Status.RECEIVED,
    }:
        raise ValidationError("A conta a pagar só pode ser gerada para pedido aprovado ou posterior.")
    if not locked_order.supplier_id:
        raise ValidationError("Informe o fornecedor antes de aprovar o pedido de compra.")
    locked_order.recalculate_totals()
    if locked_order.total_amount <= ZERO:
        raise ValidationError("Pedido de compra aprovado precisa ter valor maior que zero.")
    due_date = locked_order.expected_at or timezone.localdate()
    payable, created = AccountPayable.objects.select_for_update(of=("self",)).get_or_create(
        purchase_order=locked_order,
        defaults={
            "origin": AccountPayable.Origin.PURCHASE_ORDER,
            "recurrence_type": AccountPayable.RecurrenceType.CASH,
            "supplier": locked_order.supplier,
            "category": "fornecedor",
            "description": f"Conta a pagar do pedido {locked_order.number}",
            "issue_date": timezone.localdate(),
            "due_date": due_date,
            "amount": locked_order.total_amount or ZERO,
            "created_by": actor if getattr(actor, "is_authenticated", False) else None,
            "updated_by": actor if getattr(actor, "is_authenticated", False) else None,
        },
    )
    before = {} if created else model_snapshot(payable, PAYABLE_AUDIT_FIELDS)
    payable.origin = AccountPayable.Origin.PURCHASE_ORDER
    payable.recurrence_type = AccountPayable.RecurrenceType.CASH
    payable.supplier = locked_order.supplier
    payable.category = payable.category or "fornecedor"
    payable.description = f"Conta a pagar do pedido {locked_order.number}"
    payable.due_date = due_date
    payable.amount = locked_order.total_amount or ZERO
    payable.updated_by = actor if getattr(actor, "is_authenticated", False) else payable.updated_by
    payable.recalculate(save=True)
    payable.refresh_from_db()
    audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_CREATE if created else AuditLog.Action.FINANCIAL_UPDATE,
        instance=payable,
        user=actor,
        description="Conta a pagar do pedido criada." if created else "Conta a pagar do pedido atualizada.",
        before=before,
        after=model_snapshot(payable, PAYABLE_AUDIT_FIELDS),
        metadata={"purchase_order_id": locked_order.id, "purchase_order_number": locked_order.number},
    )
    return payable, created


@transaction.atomic
def register_payable_payment(payable, amount, method, paid_at=None, reference="", notes="", actor=None):
    locked_payable = AccountPayable.objects.select_for_update(of=("self",)).get(pk=payable.pk)
    if locked_payable.status == AccountPayable.Status.CANCELLED:
        raise ValidationError("Conta a pagar cancelada não pode receber pagamento.")
    amount = Decimal(str(amount))
    locked_payable.recalculate(save=True)
    if amount <= ZERO:
        raise ValidationError("O valor pago precisa ser maior que zero.")
    if amount > locked_payable.balance_amount:
        raise ValidationError("O valor pago não pode ser maior que o saldo da conta.")
    before_payable = model_snapshot(locked_payable, PAYABLE_AUDIT_FIELDS)
    payment = AccountPayablePayment.objects.create(
        account_payable=locked_payable,
        method=method,
        amount=amount,
        paid_at=paid_at or timezone.now(),
        reference=reference,
        notes=notes,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    locked_payable.refresh_from_db()
    locked_payable.recalculate(save=True)
    locked_payable.refresh_from_db()
    ledger_entry = record_ledger_entry(
        entry_type=FinancialLedgerEntry.EntryType.DEBIT,
        origin=FinancialLedgerEntry.Origin.PAYABLE,
        origin_instance=payment,
        description=f"Pagamento da conta {locked_payable.number}",
        amount=payment.amount,
        occurred_at=payment.paid_at,
        competence_date=payment.paid_at.date(),
        payment_method=payment.method,
        reference=payment.reference,
        notes=payment.notes,
        actor=actor,
    )
    audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_PAYMENT,
        instance=payment,
        user=actor,
        description=f"Pagamento de conta a pagar registrado: {payment.amount}.",
        before={},
        after=model_snapshot(payment, PAYMENT_AUDIT_FIELDS),
        metadata={"account_payable_id": locked_payable.id, "ledger_entry_id": ledger_entry.id if ledger_entry else None},
    )
    audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_UPDATE,
        instance=locked_payable,
        user=actor,
        description="Conta a pagar atualizada por pagamento.",
        before=before_payable,
        after=model_snapshot(locked_payable, PAYABLE_AUDIT_FIELDS),
        metadata={"payment_id": payment.id, "ledger_entry_id": ledger_entry.id if ledger_entry else None},
    )
    _audit_ledger_entry(ledger_entry, actor=actor)
    return payment, locked_payable


@transaction.atomic
def reverse_payable_payment(payment, *, reason, actor=None):
    reason = require_audit_reason(reason)
    locked_payment = AccountPayablePayment.objects.select_for_update(of=("self",)).select_related("account_payable").get(pk=payment.pk)
    if locked_payment.reversed_at:
        raise ValidationError("Este pagamento já foi estornado.")
    account = AccountPayable.objects.select_for_update(of=("self",)).get(pk=locked_payment.account_payable_id)
    before_payment = model_snapshot(locked_payment, PAYMENT_AUDIT_FIELDS)
    before_account = model_snapshot(account, PAYABLE_AUDIT_FIELDS)
    locked_payment.reversed_at = timezone.now()
    locked_payment.reversed_by = actor if getattr(actor, "is_authenticated", False) else None
    locked_payment.reversal_reason = reason
    locked_payment.save(update_fields=["reversed_at", "reversed_by", "reversal_reason", "updated_at"])
    account.refresh_from_db()
    account.recalculate(save=True)
    account.refresh_from_db()
    reversal = _record_reversal_ledger_for_payment(locked_payment, actor=actor, reason=reason)
    audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_REVERSAL,
        instance=locked_payment,
        user=actor,
        description=f"Pagamento de conta a pagar estornado: {locked_payment.amount}.",
        before=before_payment,
        after=model_snapshot(locked_payment, PAYMENT_AUDIT_FIELDS),
        metadata={"account_payable_id": account.id, "reversal_ledger_entry_id": reversal.id if reversal else None},
        reason=reason,
    )
    audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_UPDATE,
        instance=account,
        user=actor,
        description="Conta a pagar atualizada por estorno.",
        before=before_account,
        after=model_snapshot(account, PAYABLE_AUDIT_FIELDS),
        metadata={"payment_id": locked_payment.id, "reversal_ledger_entry_id": reversal.id if reversal else None},
        reason=reason,
    )
    return locked_payment, account


@transaction.atomic
def reverse_work_order_payment(payment, *, reason, actor=None):
    reason = require_audit_reason(reason)
    locked_payment = WorkOrderPayment.objects.select_for_update(of=("self",)).select_related("work_order").get(pk=payment.pk)
    if locked_payment.reversed_at:
        raise ValidationError("Este pagamento já foi estornado.")
    work_order = WorkOrder.objects.select_for_update(of=("self",)).get(pk=locked_payment.work_order_id)
    before_payment = model_snapshot(locked_payment, PAYMENT_AUDIT_FIELDS)
    before_order = model_snapshot(work_order, WORK_ORDER_FINANCIAL_FIELDS)
    locked_payment.reversed_at = timezone.now()
    locked_payment.reversed_by = actor if getattr(actor, "is_authenticated", False) else None
    locked_payment.reversal_reason = reason
    locked_payment.save(update_fields=["reversed_at", "reversed_by", "reversal_reason", "updated_at"])
    work_order.refresh_from_db()
    work_order.recalculate_totals(save=True)
    work_order.refresh_from_db()
    receivable = getattr(work_order, "account_receivable", None)
    before_receivable = None
    if receivable:
        before_receivable = model_snapshot(receivable, RECEIVABLE_AUDIT_FIELDS)
        receivable.recalculate(save=True)
        receivable.refresh_from_db()
    reversal = _record_reversal_ledger_for_payment(locked_payment, actor=actor, reason=reason)
    audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_REVERSAL,
        instance=locked_payment,
        user=actor,
        description=f"Pagamento da OS estornado: {locked_payment.amount}.",
        before=before_payment,
        after=model_snapshot(locked_payment, PAYMENT_AUDIT_FIELDS),
        metadata={"work_order_id": work_order.id, "work_order_number": work_order.number, "reversal_ledger_entry_id": reversal.id if reversal else None},
        reason=reason,
    )
    audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_UPDATE,
        instance=work_order,
        user=actor,
        description="Totais financeiros da OS atualizados por estorno.",
        before=before_order,
        after=model_snapshot(work_order, WORK_ORDER_FINANCIAL_FIELDS),
        metadata={"payment_id": locked_payment.id, "reversal_ledger_entry_id": reversal.id if reversal else None},
        reason=reason,
    )
    if receivable and before_receivable is not None:
        audit_financial_event(
            event_type=AuditLog.Action.FINANCIAL_UPDATE,
            instance=receivable,
            user=actor,
            description="Conta a receber atualizada por estorno de pagamento da OS.",
            before=before_receivable,
            after=model_snapshot(receivable, RECEIVABLE_AUDIT_FIELDS),
            metadata={"payment_id": locked_payment.id, "work_order_id": work_order.id, "reversal_ledger_entry_id": reversal.id if reversal else None},
            reason=reason,
        )
    record_event(
        work_order,
        WorkOrderEvent.EventType.PAYMENT_ADDED,
        actor=actor,
        description=f"Pagamento estornado: {locked_payment.amount}. Motivo: {reason}",
        data={"payment_id": locked_payment.id, "amount": str(locked_payment.amount), "reason": reason, "reversal_ledger_entry_id": reversal.id if reversal else None},
    )
    return locked_payment, work_order


@transaction.atomic
def create_manual_payables(*, supplier=None, category="", description, issue_date=None, first_due_date, amount, recurrence_type, installment_total=1, notes="", actor=None):
    amount = Decimal(str(amount))
    installment_total = int(installment_total or 1)
    if amount <= ZERO:
        raise ValidationError("O valor da conta a pagar precisa ser maior que zero.")
    if installment_total < 1:
        raise ValidationError("A quantidade de parcelas precisa ser maior ou igual a 1.")
    if recurrence_type == AccountPayable.RecurrenceType.INSTALLMENT and installment_total < 2:
        raise ValidationError("Conta parcelada precisa ter pelo menos 2 parcelas.")
    if recurrence_type != AccountPayable.RecurrenceType.INSTALLMENT:
        installment_total = 1
    group_id = uuid.uuid4()
    created = []
    for index in range(installment_total):
        due_date = add_months(first_due_date, index) if recurrence_type == AccountPayable.RecurrenceType.INSTALLMENT else first_due_date
        if recurrence_type == AccountPayable.RecurrenceType.INSTALLMENT:
            line_description = f"{description} - parcela {index + 1}/{installment_total}"
            line_amount = (amount / Decimal(installment_total)).quantize(Decimal("0.01"))
            if index == installment_total - 1:
                line_amount = amount - sum(item.amount for item in created)
        else:
            line_description = description
            line_amount = amount
        next_generation_date = add_months(first_due_date, 1) if recurrence_type == AccountPayable.RecurrenceType.FIXED_MONTHLY else None
        account = AccountPayable.objects.create(
            origin=AccountPayable.Origin.MANUAL,
            recurrence_type=recurrence_type,
            supplier=supplier,
            category=category or "",
            description=line_description,
            issue_date=issue_date or timezone.localdate(),
            due_date=due_date,
            amount=line_amount,
            installment_number=index + 1,
            installment_total=installment_total,
            recurrence_group=group_id,
            next_generation_date=next_generation_date,
            notes=notes,
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
            updated_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
        account.recalculate(save=True)
        account.refresh_from_db()
        audit_financial_event(
            event_type=AuditLog.Action.FINANCIAL_CREATE,
            instance=account,
            user=actor,
            description="Conta a pagar manual criada.",
            before={},
            after=model_snapshot(account, PAYABLE_AUDIT_FIELDS),
            metadata={"supplier_id": supplier.id if supplier else None, "recurrence_group": str(group_id), "installment_number": index + 1, "installment_total": installment_total},
        )
        created.append(account)
    return created


@transaction.atomic
def generate_next_fixed_payable(template_account, actor=None):
    locked_account = AccountPayable.objects.select_for_update(of=("self",)).get(pk=template_account.pk)
    if locked_account.recurrence_type != AccountPayable.RecurrenceType.FIXED_MONTHLY:
        raise ValidationError("Somente contas fixas mensais podem gerar próxima competência.")
    next_due_date = locked_account.next_generation_date or add_months(locked_account.due_date, 1)
    exists = AccountPayable.objects.filter(
        recurrence_group=locked_account.recurrence_group,
        due_date=next_due_date,
        recurrence_type=AccountPayable.RecurrenceType.FIXED_MONTHLY,
    ).exists()
    if exists:
        raise ValidationError("A próxima competência desta conta fixa já foi gerada.")
    before_template = model_snapshot(locked_account, PAYABLE_AUDIT_FIELDS)
    account = AccountPayable.objects.create(
        origin=AccountPayable.Origin.MANUAL,
        recurrence_type=AccountPayable.RecurrenceType.FIXED_MONTHLY,
        supplier=locked_account.supplier,
        category=locked_account.category,
        description=locked_account.description,
        issue_date=timezone.localdate(),
        due_date=next_due_date,
        amount=locked_account.amount,
        installment_number=1,
        installment_total=1,
        recurrence_group=locked_account.recurrence_group,
        next_generation_date=add_months(next_due_date, 1),
        notes=locked_account.notes,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
        updated_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    locked_account.next_generation_date = add_months(next_due_date, 1)
    locked_account.updated_by = actor if getattr(actor, "is_authenticated", False) else locked_account.updated_by
    locked_account.save(update_fields=["next_generation_date", "updated_by", "updated_at"])
    account.recalculate(save=True)
    account.refresh_from_db()
    locked_account.refresh_from_db()
    audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_CREATE,
        instance=account,
        user=actor,
        description="Nova competência de conta fixa gerada.",
        before={},
        after=model_snapshot(account, PAYABLE_AUDIT_FIELDS),
        metadata={"template_account_id": locked_account.id, "recurrence_group": str(locked_account.recurrence_group)},
    )
    audit_financial_event(
        event_type=AuditLog.Action.FINANCIAL_UPDATE,
        instance=locked_account,
        user=actor,
        description="Conta fixa atualizada após geração da próxima competência.",
        before=before_template,
        after=model_snapshot(locked_account, PAYABLE_AUDIT_FIELDS),
        metadata={"generated_account_id": account.id, "recurrence_group": str(locked_account.recurrence_group)},
    )
    return account
