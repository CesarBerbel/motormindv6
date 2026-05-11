from decimal import Decimal

from .approvals import build_customer_approval_url, ensure_pending_customer_approval
from ..models import WorkshopProfile, WorkOrder

ZERO = Decimal("0.00")


def money(value):
    value = value or ZERO
    return f"{value:.2f}"
def contact_context(contact):
    if not contact:
        return {}
    return {
        "id": contact.id,
        "nome": contact.full_name,
        "full_name": contact.full_name,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "email": contact.email,
        "telefone": contact.phone_e164,
        "phone_e164": contact.phone_e164,
        "custom_data": contact.custom_data or {},
    }
def vehicle_context(vehicle):
    if not vehicle:
        return {}
    return {
        "id": vehicle.id,
        "placa": vehicle.plate,
        "marca": vehicle.make,
        "modelo": vehicle.model,
        "versao": vehicle.version,
        "ano": vehicle.year,
        "cor": vehicle.color,
        "vin": vehicle.vin,
        "km": vehicle.odometer_km,
        "display": vehicle.display_name,
    }
def workshop_context(profile):
    if not profile:
        return {}
    return {
        "id": profile.id,
        "nome": profile.display_name,
        "display_name": profile.display_name,
        "legal_name": profile.legal_name,
        "trade_name": profile.trade_name,
        "documento": profile.document_number,
        "document_number": profile.document_number,
        "email": profile.email,
        "telefone": profile.phone_e164,
        "phone_e164": profile.phone_e164,
        "endereco": profile.address_display,
        "address_display": profile.address_display,
    }
def work_order_context(work_order, actor=None, include_approval=False):
    approval_url = ""
    approval = None
    if include_approval:
        approval = ensure_pending_customer_approval(work_order, actor=actor)
        approval_url = build_customer_approval_url(approval)
    order = {
        "id": work_order.id,
        "numero": work_order.number,
        "number": work_order.number,
        "titulo": work_order.title,
        "title": work_order.title,
        "status": work_order.status,
        "status_label": work_order.status_label,
        "prioridade": work_order.priority,
        "priority": work_order.priority,
        "priority_label": work_order.priority_label,
        "reclamacao": work_order.complaint,
        "complaint": work_order.complaint,
        "diagnostico": work_order.diagnosis,
        "diagnosis": work_order.diagnosis,
        "solucao": work_order.solution,
        "solution": work_order.solution,
        "km_entrada": work_order.mileage_in,
        "mileage_in": work_order.mileage_in,
        "previsao": work_order.promised_at,
        "promised_at": work_order.promised_at,
        "total_servicos": money(work_order.subtotal_services),
        "total_pecas": money(work_order.subtotal_parts),
        "desconto_total": money(work_order.discount_total),
        "total": money(work_order.grand_total),
        "pago": money(work_order.paid_total),
        "saldo": money(work_order.balance_due),
        "created_at": work_order.created_at,
        "updated_at": work_order.updated_at,
    }
    vehicle = vehicle_context(work_order.vehicle)
    customer = contact_context(work_order.customer)
    workshop = workshop_context(WorkshopProfile.get_solo())
    return {
        "ordem": order,
        "os": order,
        "work_order": order,
        "numero_os": work_order.number,
        "status_os": work_order.status_label,
        "total_os": money(work_order.grand_total),
        "saldo_os": money(work_order.balance_due),
        "cliente": customer,
        "customer": customer,
        "oficina": workshop,
        "workshop": workshop,
        "nome_oficina": workshop.get("nome", ""),
        "email_oficina": workshop.get("email", ""),
        "telefone_oficina": workshop.get("telefone", ""),
        "nome_cliente": customer.get("nome", ""),
        "email_cliente": customer.get("email", ""),
        "telefone_cliente": customer.get("telefone", ""),
        "veiculo": vehicle,
        "vehicle": vehicle,
        "placa_veiculo": vehicle.get("placa", ""),
        "modelo_veiculo": vehicle.get("modelo", ""),
        "approval_url": approval_url,
        "aprovacao_url": approval_url,
        "approval": approval,
        "aprovacao": approval,
    }
