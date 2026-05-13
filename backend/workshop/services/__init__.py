"""Serviços do app workshop organizados por domínio.

Este pacote mantém a API pública histórica de `workshop.services` para que
imports antigos continuem funcionando enquanto a implementação fica separada
em módulos menores e mais fáceis de testar.
"""

from .approvals import build_customer_approval_url, ensure_pending_customer_approval
from .context import contact_context, money, vehicle_context, work_order_context, workshop_context
from .events import apply_status_timestamps, record_event
from .inventory import adjust_part_stock, consume_parts_inventory, reserve_parts_for_work_order, release_work_order_part_reservations
from .notifications import send_work_order_message, trigger_status_notifications
from .status import cancel_work_order, change_work_order_status, technical_move_work_order
from .technical_services import complete_work_order_service, quality_check_work_order_service, start_work_order_service

__all__ = [
    "adjust_part_stock",
    "apply_status_timestamps",
    "build_customer_approval_url",
    "change_work_order_status",
    "complete_work_order_service",
    "consume_parts_inventory",
    "reserve_parts_for_work_order",
    "release_work_order_part_reservations",
    "contact_context",
    "ensure_pending_customer_approval",
    "money",
    "quality_check_work_order_service",
    "record_event",
    "send_work_order_message",
    "start_work_order_service",
    "technical_move_work_order",
    "trigger_status_notifications",
    "vehicle_context",
    "work_order_context",
    "workshop_context",
]
