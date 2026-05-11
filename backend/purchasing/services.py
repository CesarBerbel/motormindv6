from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from workshop.models import Part, PartStockMovement, WorkOrder, WorkOrderEvent, WorkOrderPart
from workshop.services import adjust_part_stock, record_event

from .models import PurchaseOrder, PurchaseOrderItem

ZERO = Decimal("0.00")
OPEN_PURCHASE_STATUSES = [
    PurchaseOrder.Status.DRAFT,
    PurchaseOrder.Status.REQUESTED,
    PurchaseOrder.Status.APPROVED,
    PurchaseOrder.Status.ORDERED,
    PurchaseOrder.Status.PARTIALLY_RECEIVED,
]


def _actor_or_none(actor):
    return actor if getattr(actor, "is_authenticated", False) else None


def _line_shortage_quantity(line, part=None):
    """Retorna a quantidade que ainda precisa ser comprada para uma linha de OS.

    O fluxo atual reserva estoque antes de criar necessidade de compra. Por isso,
    quando existir stock_shortage_quantity na linha, esse valor é a fonte mais
    confiável. Como fallback, calculamos pelo estoque disponível, descontando
    reservas já existentes de outras OS.
    """
    if not line.part_id or not line.consume_inventory:
        return ZERO
    if (line.stock_shortage_quantity or ZERO) > ZERO:
        return line.stock_shortage_quantity or ZERO
    locked_part = part or line.part
    if locked_part is None:
        locked_part = Part.objects.get(pk=line.part_id)
    available = (locked_part.stock_quantity or ZERO) - (locked_part.reserved_quantity or ZERO)
    if available < ZERO:
        available = ZERO
    shortage = (line.quantity or ZERO) - available
    return shortage if shortage > ZERO else ZERO


def shortage_for_work_order_part(line):
    if not line.part_id or not line.consume_inventory:
        return ZERO
    part = Part.objects.get(pk=line.part_id)
    return _line_shortage_quantity(line, part=part)


def _get_or_create_automatic_purchase_order(work_order, actor=None):
    purchase_order = (
        PurchaseOrder.objects.select_for_update(of=("self",))
        .filter(origin=PurchaseOrder.Origin.AUTOMATIC, work_order=work_order, status__in=OPEN_PURCHASE_STATUSES)
        .order_by("created_at", "id")
        .first()
    )
    if purchase_order:
        return purchase_order
    return PurchaseOrder.objects.create(
        origin=PurchaseOrder.Origin.AUTOMATIC,
        status=PurchaseOrder.Status.DRAFT,
        work_order=work_order,
        notes=f"Necessidade de compra automática gerada por falta de estoque na {work_order.number}.",
        created_by=_actor_or_none(actor),
        updated_by=_actor_or_none(actor),
    )


@transaction.atomic
def ensure_purchase_for_work_order_part(line, actor=None, purchase_order=None):
    locked_line = WorkOrderPart.objects.select_for_update(of=("self",)).select_related("part", "work_order").get(pk=line.pk)
    if not locked_line.part_id or not locked_line.consume_inventory:
        return None
    part = Part.objects.select_for_update(of=("self",)).get(pk=locked_line.part_id)
    shortage = _line_shortage_quantity(locked_line, part=part)
    existing_items = PurchaseOrderItem.objects.select_for_update(of=("self",)).filter(
        work_order_part=locked_line,
        is_auto_generated=True,
        purchase_order__status__in=OPEN_PURCHASE_STATUSES,
    ).select_related("purchase_order")
    existing_item = existing_items.first()

    if shortage <= ZERO:
        for item in existing_items:
            if (item.received_quantity or ZERO) == ZERO:
                order = item.purchase_order
                item.delete()
                if not order.items.exists() and order.origin == PurchaseOrder.Origin.AUTOMATIC:
                    order.delete()
        return None

    if purchase_order is None:
        purchase_order = existing_item.purchase_order if existing_item else _get_or_create_automatic_purchase_order(locked_line.work_order, actor=actor)

    item_notes = (
        f"Déficit automático da {locked_line.work_order.number}: necessário {locked_line.quantity}, "
        f"reservado {locked_line.stock_reserved_quantity or ZERO}, déficit {shortage}."
    )
    if existing_item:
        existing_item.purchase_order = purchase_order
        existing_item.quantity = shortage
        existing_item.part = part
        existing_item.work_order = locked_line.work_order
        existing_item.description = locked_line.description or part.name
        existing_item.unit_cost = locked_line.cost_price or part.cost_price
        existing_item.notes = item_notes
        existing_item.save()
        item = existing_item
    else:
        item = PurchaseOrderItem.objects.create(
            purchase_order=purchase_order,
            part=part,
            work_order=locked_line.work_order,
            work_order_part=locked_line,
            description=locked_line.description or part.name,
            quantity=shortage,
            unit_cost=locked_line.cost_price or part.cost_price,
            is_auto_generated=True,
            notes=item_notes,
        )
    purchase_order.recalculate_totals()
    return purchase_order


@transaction.atomic
def ensure_purchases_for_work_order_shortages(work_order, actor=None):
    """Cria/atualiza necessidade de compra para as faltas de estoque de uma OS.

    Gera um único pedido de compra automático aberto por OS, com um item para cada
    linha de peça que ficou parcial ou sem estoque após a reserva. A função é
    idempotente: se chamada novamente, atualiza quantidades e remove itens que
    deixaram de ter déficit.
    """
    locked_order = WorkOrder.objects.select_for_update(of=("self",)).get(pk=work_order.pk)
    lines = list(
        locked_order.parts.select_related("part")
        .select_for_update(of=("self",))
        .filter(part__isnull=False, consume_inventory=True, stock_consumed_at__isnull=True)
        .order_by("id")
    )
    shortage_lines = []
    for line in lines:
        shortage = _line_shortage_quantity(line, part=line.part)
        if shortage > ZERO:
            shortage_lines.append((line, shortage))

    existing_items = PurchaseOrderItem.objects.select_for_update(of=("self",)).filter(
        work_order=locked_order,
        is_auto_generated=True,
        purchase_order__origin=PurchaseOrder.Origin.AUTOMATIC,
        purchase_order__status__in=OPEN_PURCHASE_STATUSES,
    ).select_related("purchase_order", "work_order_part")
    shortage_line_ids = {line.id for line, _shortage in shortage_lines}

    removed_item_ids = []
    for item in existing_items:
        if item.work_order_part_id not in shortage_line_ids and (item.received_quantity or ZERO) == ZERO:
            order = item.purchase_order
            removed_item_ids.append(item.id)
            item.delete()
            if not order.items.exists() and order.origin == PurchaseOrder.Origin.AUTOMATIC:
                order.delete()

    if not shortage_lines:
        return {
            "purchase_order_id": None,
            "purchase_order_number": "",
            "created_item_ids": [],
            "updated_item_ids": [],
            "removed_item_ids": removed_item_ids,
            "shortage_total": "0.00",
        }

    purchase_order = _get_or_create_automatic_purchase_order(locked_order, actor=actor)
    before_item_ids = set(purchase_order.items.values_list("id", flat=True))
    item_ids = []
    shortage_total = ZERO
    shortage_details = []
    for line, shortage in shortage_lines:
        ensure_purchase_for_work_order_part(line, actor=actor, purchase_order=purchase_order)
        item = PurchaseOrderItem.objects.get(work_order_part=line, is_auto_generated=True, purchase_order__status__in=OPEN_PURCHASE_STATUSES)
        item_ids.append(item.id)
        shortage_total += shortage
        shortage_details.append({
            "work_order_part_id": line.id,
            "part_id": line.part_id,
            "part_sku": line.part.sku,
            "part_name": line.part.name,
            "required_quantity": str(line.quantity or ZERO),
            "reserved_quantity": str(line.stock_reserved_quantity or ZERO),
            "shortage_quantity": str(shortage),
            "purchase_order_item_id": item.id,
        })

    purchase_order.refresh_from_db()
    purchase_order.recalculate_totals()
    after_item_ids = set(purchase_order.items.values_list("id", flat=True))
    created_item_ids = sorted(after_item_ids - before_item_ids)
    updated_item_ids = sorted(after_item_ids & before_item_ids)
    summary = {
        "purchase_order_id": purchase_order.id,
        "purchase_order_number": purchase_order.number,
        "created_item_ids": created_item_ids,
        "updated_item_ids": updated_item_ids,
        "removed_item_ids": removed_item_ids,
        "shortage_total": str(shortage_total),
        "items": shortage_details,
    }
    record_event(
        locked_order,
        WorkOrderEvent.EventType.PURCHASE_NEEDED,
        actor=actor,
        description=f"Necessidade de compra automática {purchase_order.number} gerada/atualizada para peças faltantes.",
        data=summary,
    )
    return summary


@transaction.atomic
def receive_purchase_order_items(purchase_order, items, actor=None):
    movements = []
    locked_order = PurchaseOrder.objects.select_for_update(of=("self",)).get(pk=purchase_order.pk)
    if locked_order.status == PurchaseOrder.Status.CANCELLED:
        raise ValidationError("Pedido cancelado não pode receber itens.")
    for item_data in items:
        item_id = item_data.get("item_id")
        quantity = Decimal(str(item_data.get("quantity", "0")))
        unit_cost = Decimal(str(item_data.get("unit_cost", "0"))) if item_data.get("unit_cost") not in {None, ""} else None
        if quantity <= ZERO:
            raise ValidationError("Quantidade recebida precisa ser maior que zero.")
        item = PurchaseOrderItem.objects.select_for_update(of=("self",)).select_related("part").get(pk=item_id, purchase_order=locked_order)
        if not item.part_id:
            raise ValidationError(f"O item {item.description} não possui peça vinculada para entrada no estoque.")
        pending = item.pending_quantity
        if quantity > pending:
            raise ValidationError(f"Quantidade recebida de {item.description} maior que o saldo pendente.")
        movement = adjust_part_stock(
            item.part,
            quantity=quantity,
            movement_type=PartStockMovement.MovementType.PURCHASE,
            actor=actor,
            notes=f"Entrada do pedido de compra {locked_order.number}",
            unit_cost=unit_cost or item.unit_cost or item.part.cost_price,
        )
        item.received_quantity = (item.received_quantity or ZERO) + quantity
        if unit_cost is not None:
            item.unit_cost = unit_cost
        item.save()
        movements.append(movement)
    locked_order.refresh_from_db()
    locked_order.recalculate_totals()
    locked_order.refresh_status_from_receipts()
    if locked_order.status in {PurchaseOrder.Status.PARTIALLY_RECEIVED, PurchaseOrder.Status.RECEIVED}:
        locked_order.received_at = locked_order.received_at or timezone.now()
        locked_order.save(update_fields=["received_at", "updated_at"])
    if locked_order.work_order_id:
        record_event(
            locked_order.work_order,
            WorkOrderEvent.EventType.INVENTORY_CONSUMED,
            actor=actor,
            description=f"Itens recebidos no pedido de compra {locked_order.number}.",
            data={"purchase_order_id": locked_order.id, "stock_movement_ids": [movement.id for movement in movements]},
        )
    return locked_order, movements
