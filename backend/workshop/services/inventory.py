from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .context import ZERO
from .events import record_event
from ..models import Part, PartStockMovement, WorkOrder, WorkOrderEvent, WorkOrderPart


def _actor_or_none(actor):
    return actor if getattr(actor, "is_authenticated", False) else None


def adjust_part_stock(part, quantity, movement_type=PartStockMovement.MovementType.ADJUSTMENT, actor=None, notes="", work_order=None, unit_cost=None):
    quantity = Decimal(str(quantity))
    unit_cost = part.cost_price if unit_cost is None else Decimal(str(unit_cost))
    with transaction.atomic():
        locked = Part.objects.select_for_update(of=("self",)).get(pk=part.pk)
        locked.stock_quantity = (locked.stock_quantity or ZERO) + quantity
        locked.save(update_fields=["stock_quantity", "updated_at"])
        movement = PartStockMovement.objects.create(
            part=locked,
            movement_type=movement_type,
            quantity=quantity,
            unit_cost=unit_cost,
            work_order=work_order,
            notes=notes,
            actor=_actor_or_none(actor),
        )
    return movement


def reserve_parts_for_work_order(work_order, actor=None, source_estimate=None):
    """Reserva estoque disponível para as peças de uma OS.

    A reserva não baixa o estoque físico. Ela aumenta Part.reserved_quantity e
    marca cada linha da OS com quantidade reservada, déficit e status de reserva.
    A baixa real continua ocorrendo no consumo da OS.
    """
    summary = {
        "reserved_line_ids": [],
        "partial_line_ids": [],
        "unavailable_line_ids": [],
        "not_applicable_line_ids": [],
        "movement_ids": [],
    }
    now = timezone.now()
    with transaction.atomic():
        locked_order = WorkOrder.objects.select_for_update(of=("self",)).get(pk=work_order.pk)
        lines = list(
            locked_order.parts.select_related("part")
            .select_for_update(of=("self",))
            .filter(stock_consumed_at__isnull=True)
            .order_by("id")
        )
        for line in lines:
            quantity = line.quantity or ZERO
            if not line.part_id or not line.consume_inventory or quantity <= ZERO:
                line.stock_reserved_quantity = ZERO
                line.stock_shortage_quantity = ZERO
                line.stock_reservation_status = WorkOrderPart.ReservationStatus.NOT_APPLICABLE
                line.stock_reserved_at = None
                line.stock_reservation_notes = "Linha sem peça de estoque ou sem controle de consumo."
                line.save(update_fields=[
                    "stock_reserved_quantity",
                    "stock_shortage_quantity",
                    "stock_reservation_status",
                    "stock_reserved_at",
                    "stock_reservation_notes",
                    "updated_at",
                ])
                summary["not_applicable_line_ids"].append(line.id)
                continue

            part = Part.objects.select_for_update(of=("self",)).get(pk=line.part_id)
            available = (part.stock_quantity or ZERO) - (part.reserved_quantity or ZERO)
            if available < ZERO:
                available = ZERO
            reserved = min(quantity, available)
            shortage = quantity - reserved
            movement = None

            if reserved > ZERO:
                part.reserved_quantity = (part.reserved_quantity or ZERO) + reserved
                part.save(update_fields=["reserved_quantity", "updated_at"])
                movement = PartStockMovement.objects.create(
                    part=part,
                    movement_type=PartStockMovement.MovementType.RESERVATION,
                    quantity=reserved,
                    unit_cost=line.cost_price or part.cost_price or ZERO,
                    work_order=locked_order,
                    notes=(
                        f"Reserva automática para {locked_order.number}"
                        + (f" a partir do orçamento {source_estimate.number}." if source_estimate else ".")
                    ),
                    actor=_actor_or_none(actor),
                )
                summary["movement_ids"].append(movement.id)

            if shortage <= ZERO:
                status = WorkOrderPart.ReservationStatus.RESERVED
                notes = f"Reserva integral realizada: {reserved}."
                summary["reserved_line_ids"].append(line.id)
            elif reserved > ZERO:
                status = WorkOrderPart.ReservationStatus.PARTIAL
                notes = f"Reserva parcial: {reserved} reservado; déficit {shortage}."
                summary["partial_line_ids"].append(line.id)
            else:
                status = WorkOrderPart.ReservationStatus.UNAVAILABLE
                notes = f"Sem estoque disponível; déficit {shortage}."
                summary["unavailable_line_ids"].append(line.id)

            line.stock_reserved_quantity = reserved
            line.stock_shortage_quantity = shortage
            line.stock_reservation_status = status
            line.stock_reserved_at = now if reserved > ZERO else None
            line.stock_reservation_notes = notes
            if movement:
                line.stock_reservation_movement = movement
            line.save(update_fields=[
                "stock_reserved_quantity",
                "stock_shortage_quantity",
                "stock_reservation_status",
                "stock_reserved_at",
                "stock_reservation_notes",
                "stock_reservation_movement",
                "updated_at",
            ])

        has_shortage = bool(summary["partial_line_ids"] or summary["unavailable_line_ids"])
        old_status = locked_order.status
        if has_shortage and locked_order.status != WorkOrder.Status.WAITING_PARTS:
            locked_order.status = WorkOrder.Status.WAITING_PARTS
            locked_order.save(update_fields=["status", "updated_at"])
        elif not has_shortage and locked_order.status == WorkOrder.Status.WAITING_PARTS:
            locked_order.status = WorkOrder.Status.OPEN
            locked_order.save(update_fields=["status", "updated_at"])
        new_status = locked_order.status

    event_description = "Reserva automática de peças da ordem de serviço."
    if summary["partial_line_ids"] or summary["unavailable_line_ids"]:
        event_description = "Reserva automática de peças com déficit de estoque."
    record_event(
        WorkOrder.objects.get(pk=work_order.pk),
        WorkOrderEvent.EventType.INVENTORY_RESERVED,
        actor=actor,
        description=event_description,
        old_status=old_status,
        new_status=new_status,
        data={
            **summary,
            "source_estimate_id": getattr(source_estimate, "id", None),
            "source_estimate_number": getattr(source_estimate, "number", ""),
        },
    )
    return summary


def release_work_order_part_reservations(work_order, actor=None, reason=""):
    released = []
    with transaction.atomic():
        locked_order = WorkOrder.objects.select_for_update(of=("self",)).get(pk=work_order.pk)
        lines = list(
            locked_order.parts.select_related("part")
            .select_for_update(of=("self",))
            .filter(stock_reserved_quantity__gt=ZERO, stock_consumed_at__isnull=True)
        )
        for line in lines:
            if not line.part_id:
                continue
            part = Part.objects.select_for_update(of=("self",)).get(pk=line.part_id)
            quantity = line.stock_reserved_quantity or ZERO
            part.reserved_quantity = max((part.reserved_quantity or ZERO) - quantity, ZERO)
            part.save(update_fields=["reserved_quantity", "updated_at"])
            movement = PartStockMovement.objects.create(
                part=part,
                movement_type=PartStockMovement.MovementType.RESERVATION_RELEASE,
                quantity=-quantity,
                unit_cost=line.cost_price or part.cost_price or ZERO,
                work_order=locked_order,
                notes=(f"Liberação de reserva da {locked_order.number}. {reason}".strip()),
                actor=_actor_or_none(actor),
            )
            line.stock_reserved_quantity = ZERO
            line.stock_shortage_quantity = line.quantity or ZERO
            line.stock_reservation_status = WorkOrderPart.ReservationStatus.PENDING
            line.stock_reserved_at = None
            line.stock_reservation_notes = "Reserva liberada."
            line.save(update_fields=[
                "stock_reserved_quantity",
                "stock_shortage_quantity",
                "stock_reservation_status",
                "stock_reserved_at",
                "stock_reservation_notes",
                "updated_at",
            ])
            released.append(movement.id)
    if released:
        record_event(work_order, WorkOrderEvent.EventType.INVENTORY_RESERVATION_RELEASED, actor=actor, description="Liberação de reserva de peças da OS.", data={"stock_movement_ids": released})
    return released


def consume_parts_inventory(work_order, actor=None):
    consumed = []
    now = timezone.now()
    with transaction.atomic():
        locked_order = WorkOrder.objects.select_for_update(of=("self",)).get(pk=work_order.pk)
        if locked_order.inventory_consumed_at:
            return consumed
        lines = locked_order.parts.select_related("part").filter(part__isnull=False, consume_inventory=True, stock_consumed_at__isnull=True)
        for line in lines:
            part = Part.objects.select_for_update(of=("self",)).get(pk=line.part_id)
            quantity = line.quantity or ZERO
            reserved = line.stock_reserved_quantity or ZERO
            available_without_this_reservation = (part.stock_quantity or ZERO) - (part.reserved_quantity or ZERO) + reserved
            if available_without_this_reservation < quantity:
                raise ValidationError({"estoque": f"Estoque insuficiente para {part.name}. Disponivel: {available_without_this_reservation}, necessario: {quantity}."})
            part.stock_quantity = (part.stock_quantity or ZERO) - quantity
            if reserved > ZERO:
                part.reserved_quantity = max((part.reserved_quantity or ZERO) - reserved, ZERO)
            part.save(update_fields=["stock_quantity", "reserved_quantity", "updated_at"])
            movement = PartStockMovement.objects.create(
                part=part,
                movement_type=PartStockMovement.MovementType.CONSUMPTION,
                quantity=-quantity,
                unit_cost=line.cost_price or part.cost_price,
                work_order=locked_order,
                notes=f"Consumo automatico na {locked_order.number}",
                actor=_actor_or_none(actor),
            )
            line.stock_consumed_at = now
            line.stock_movement = movement
            line.stock_reserved_quantity = ZERO
            line.stock_shortage_quantity = ZERO
            line.stock_reservation_status = WorkOrderPart.ReservationStatus.NOT_APPLICABLE
            line.save(update_fields=["stock_consumed_at", "stock_movement", "stock_reserved_quantity", "stock_shortage_quantity", "stock_reservation_status", "updated_at"])
            consumed.append(movement.id)
        locked_order.inventory_consumed_at = now
        locked_order.save(update_fields=["inventory_consumed_at", "updated_at"])
    record_event(work_order, WorkOrderEvent.EventType.INVENTORY_CONSUMED, actor=actor, description="Baixa automatica de pecas da ordem de servico.", data={"stock_movement_ids": consumed})
    return consumed
