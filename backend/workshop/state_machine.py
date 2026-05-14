"""Máquina de estados oficial da Ordem de Serviço.

Implementa as transições operacionais solicitadas para OS, mantendo o backend
como fonte de verdade independente do frontend.
"""

from dataclasses import dataclass

from django.core.exceptions import ValidationError

from accounts.roles import ROLE_ADMINISTRATIVE, ROLE_ATTENDANT, ROLE_FINANCE, ROLE_OWNER, ROLE_STOCK, ROLE_TECHNICIAN
from accounts.services import get_user_role, user_has_permission

from .models import WorkOrder, WorkshopProfile


@dataclass(frozen=True)
class TransitionRule:
    target: str
    label: str
    description: str
    roles: frozenset[str]
    sources: frozenset[str]
    requires_note: bool = False


SOURCE_MANUAL = "manual"
SOURCE_TECHNICAL_START = "technical_start"
SOURCE_TECHNICAL_COMPLETE = "technical_complete"
SOURCE_TECHNICAL_WAITING_PARTS = "technical_waiting_parts"
SOURCE_QUALITY_REWORK = "quality_rework"
SOURCE_SYSTEM = "system"

ADMINISTRATIVE_ROLES = frozenset({ROLE_OWNER, ROLE_ADMINISTRATIVE})
ATTENDANCE_ROLES = frozenset({ROLE_OWNER, ROLE_ADMINISTRATIVE, ROLE_ATTENDANT})
TECHNICAL_ROLES = frozenset({ROLE_OWNER, ROLE_ADMINISTRATIVE, ROLE_TECHNICIAN})
FINISHING_ROLES = frozenset({ROLE_OWNER, ROLE_ADMINISTRATIVE, ROLE_ATTENDANT, ROLE_FINANCE})
SYSTEM_ROLES = frozenset({ROLE_OWNER, ROLE_ADMINISTRATIVE, ROLE_ATTENDANT, ROLE_TECHNICIAN, ROLE_FINANCE, ROLE_STOCK})
ANY_SOURCE = frozenset({SOURCE_MANUAL, SOURCE_TECHNICAL_START, SOURCE_TECHNICAL_COMPLETE, SOURCE_TECHNICAL_WAITING_PARTS, SOURCE_QUALITY_REWORK, SOURCE_SYSTEM})


def _rule(target, label, description, roles, *, requires_note=False, sources=None):
    return TransitionRule(
        target=target,
        label=label,
        description=description,
        roles=roles,
        sources=sources or ANY_SOURCE,
        requires_note=requires_note,
    )


WORK_ORDER_STATE_GRAPH: dict[str, tuple[TransitionRule, ...]] = {
    WorkOrder.Status.OPEN: (
        _rule(WorkOrder.Status.IN_PROGRESS, "Iniciar execução", "Move uma OS aberta para execução.", TECHNICAL_ROLES),
        _rule(WorkOrder.Status.WAITING_PARTS, "Aguardar peças", "Move uma OS aberta para espera de peças.", TECHNICAL_ROLES),
        _rule(WorkOrder.Status.AWAITING_APPROVAL, "Aguardar aprovação", "Move uma OS aberta para aprovação complementar.", ATTENDANCE_ROLES | TECHNICAL_ROLES),
        _rule(WorkOrder.Status.CANCELLED, "Cancelar OS", "Cancela uma OS aberta.", ATTENDANCE_ROLES | TECHNICAL_ROLES | FINISHING_ROLES, requires_note=True),
    ),
    WorkOrder.Status.IN_PROGRESS: (
        _rule(WorkOrder.Status.WAITING_PARTS, "Aguardar peças", "Pausa a execução enquanto peças são aguardadas.", TECHNICAL_ROLES),
        _rule(WorkOrder.Status.AWAITING_APPROVAL, "Aguardar aprovação", "Aguarda aprovação de revisão/ajuste.", ATTENDANCE_ROLES | TECHNICAL_ROLES),
        _rule(WorkOrder.Status.PAUSED, "Pausar", "Pausa a execução com justificativa.", TECHNICAL_ROLES, requires_note=True),
        _rule(WorkOrder.Status.COMPLETED, "Concluir", "Conclui a execução operacional.", TECHNICAL_ROLES | FINISHING_ROLES),
        _rule(WorkOrder.Status.CANCELLED, "Cancelar OS", "Cancela uma OS em execução.", ATTENDANCE_ROLES | TECHNICAL_ROLES | FINISHING_ROLES, requires_note=True),
    ),
    WorkOrder.Status.WAITING_PARTS: (
        _rule(WorkOrder.Status.IN_PROGRESS, "Retomar execução", "Retoma a execução após chegada/liberação de peças.", TECHNICAL_ROLES),
        _rule(WorkOrder.Status.AWAITING_APPROVAL, "Aguardar aprovação", "Aguarda aprovação enquanto há pendência de peças/valores.", ATTENDANCE_ROLES | TECHNICAL_ROLES),
        _rule(WorkOrder.Status.PAUSED, "Pausar", "Pausa a OS aguardando peças.", TECHNICAL_ROLES, requires_note=True),
        _rule(WorkOrder.Status.CANCELLED, "Cancelar OS", "Cancela uma OS aguardando peças.", ATTENDANCE_ROLES | TECHNICAL_ROLES | FINISHING_ROLES, requires_note=True),
    ),
    WorkOrder.Status.AWAITING_APPROVAL: (
        _rule(WorkOrder.Status.IN_PROGRESS, "Retomar execução", "Retoma a OS após aprovação.", TECHNICAL_ROLES | ATTENDANCE_ROLES),
        _rule(WorkOrder.Status.PAUSED, "Pausar", "Pausa a OS aguardando aprovação.", TECHNICAL_ROLES | ATTENDANCE_ROLES, requires_note=True),
        _rule(WorkOrder.Status.COMPLETED, "Concluir", "Conclui a OS após aprovação sem nova execução.", TECHNICAL_ROLES | FINISHING_ROLES),
        _rule(WorkOrder.Status.CANCELLED, "Cancelar OS", "Cancela uma OS aguardando aprovação.", ATTENDANCE_ROLES | TECHNICAL_ROLES | FINISHING_ROLES, requires_note=True),
    ),
    WorkOrder.Status.PAUSED: (
        _rule(WorkOrder.Status.IN_PROGRESS, "Retomar execução", "Retoma uma OS pausada.", TECHNICAL_ROLES),
        _rule(WorkOrder.Status.WAITING_PARTS, "Aguardar peças", "Move uma OS pausada para espera de peças.", TECHNICAL_ROLES),
        _rule(WorkOrder.Status.AWAITING_APPROVAL, "Aguardar aprovação", "Move uma OS pausada para aprovação.", ATTENDANCE_ROLES | TECHNICAL_ROLES),
        _rule(WorkOrder.Status.CANCELLED, "Cancelar OS", "Cancela uma OS pausada.", ATTENDANCE_ROLES | TECHNICAL_ROLES | FINISHING_ROLES, requires_note=True),
    ),
    WorkOrder.Status.COMPLETED: (
        _rule(WorkOrder.Status.DELIVERED, "Entregar", "Entrega o veículo/serviço ao cliente.", FINISHING_ROLES),
        _rule(WorkOrder.Status.IN_PROGRESS, "Reabrir execução", "Reabre uma OS concluída mediante permissão especial.", ADMINISTRATIVE_ROLES | TECHNICAL_ROLES, requires_note=True),
    ),
    WorkOrder.Status.DELIVERED: (),
    WorkOrder.Status.CANCELLED: (),
}

TERMINAL_STATUSES = frozenset({WorkOrder.Status.DELIVERED, WorkOrder.Status.CANCELLED})

STATE_ORDER = {
    WorkOrder.Status.OPEN: 10,
    WorkOrder.Status.IN_PROGRESS: 20,
    WorkOrder.Status.WAITING_PARTS: 25,
    WorkOrder.Status.AWAITING_APPROVAL: 30,
    WorkOrder.Status.PAUSED: 35,
    WorkOrder.Status.COMPLETED: 40,
    WorkOrder.Status.DELIVERED: 50,
    WorkOrder.Status.CANCELLED: 99,
}

INVALID_REGRESSION_HINTS = {
    (WorkOrder.Status.DELIVERED, WorkOrder.Status.IN_PROGRESS): "OS entregue é estado final. Abra uma nova OS de garantia, retrabalho ou retorno.",
    (WorkOrder.Status.CANCELLED, WorkOrder.Status.OPEN): "OS cancelada não pode ser reaberta. Abra uma nova OS ou gere novo orçamento.",
}


class WorkOrderTransitionError(ValidationError):
    """Erro de transição de estado da OS."""


def _status_label(status: str) -> str:
    return dict(WorkOrder.Status.choices).get(status, status)


def _rules_from(status: str) -> tuple[TransitionRule, ...]:
    return WORK_ORDER_STATE_GRAPH.get(status, ())


def _find_rule(current_status: str, target_status: str) -> TransitionRule | None:
    for rule in _rules_from(current_status):
        if rule.target == target_status:
            return rule
    return None


def _actor_role(actor) -> str | None:
    return get_user_role(actor) if getattr(actor, "is_authenticated", False) else None


def _actor_can_use_rule(actor, rule: TransitionRule) -> bool:
    role = _actor_role(actor)
    if role in rule.roles:
        return True
    if role in ADMINISTRATIVE_ROLES and user_has_permission(actor, "*"):
        return True
    return False


def _normalize_source(source: str | None) -> str:
    return source or SOURCE_MANUAL


def _transition_data(current_status: str, rule: TransitionRule) -> dict:
    return {
        "status": rule.target,
        "status_label": _status_label(rule.target),
        "from_status": current_status,
        "from_status_label": _status_label(current_status),
        "label": rule.label,
        "description": rule.description,
        "requires_note": rule.requires_note,
        "is_forward": STATE_ORDER.get(rule.target, 0) >= STATE_ORDER.get(current_status, 0),
    }


def all_state_machine_transitions() -> list[dict]:
    transitions = []
    for current_status, rules in WORK_ORDER_STATE_GRAPH.items():
        for rule in rules:
            transitions.append(_transition_data(current_status, rule))
    return transitions


def available_status_transitions(work_order: WorkOrder, actor=None, source: str | None = SOURCE_MANUAL) -> list[dict]:
    source = _normalize_source(source)
    if not work_order or not work_order.status:
        return []
    transitions = []
    for rule in _rules_from(work_order.status):
        if source not in rule.sources:
            continue
        if actor is not None and not _actor_can_use_rule(actor, rule):
            continue
        transitions.append(_transition_data(work_order.status, rule))
    return transitions


def validate_work_order_transition(work_order: WorkOrder, new_status: str, actor=None, note: str = "", source: str | None = SOURCE_MANUAL) -> TransitionRule | None:
    source = _normalize_source(source)
    current_status = work_order.status
    valid_statuses = {value for value, _label in WorkOrder.Status.choices}

    if new_status not in valid_statuses:
        raise WorkOrderTransitionError({"status": f"Status inválido: {new_status}."})

    if current_status == new_status:
        return None

    if current_status in TERMINAL_STATUSES:
        raise WorkOrderTransitionError({
            "status": f"A OS está em estado final ({_status_label(current_status)}) e não pode mudar de status operacional.",
            "current_status": current_status,
            "target_status": new_status,
        })

    rule = _find_rule(current_status, new_status)
    if not rule:
        hint = INVALID_REGRESSION_HINTS.get((current_status, new_status)) or f"Transição não permitida pela máquina de estados: {_status_label(current_status)} → {_status_label(new_status)}."
        raise WorkOrderTransitionError({
            "status": hint,
            "current_status": current_status,
            "target_status": new_status,
            "allowed_targets": [_transition_data(current_status, allowed) for allowed in _rules_from(current_status)],
        })

    if source not in rule.sources:
        raise WorkOrderTransitionError({
            "status": f"A origem '{source}' não pode executar a transição {_status_label(current_status)} → {_status_label(new_status)}.",
            "current_status": current_status,
            "target_status": new_status,
        })

    if actor is not None and not _actor_can_use_rule(actor, rule):
        role = _actor_role(actor) or "sem perfil"
        raise WorkOrderTransitionError({
            "permissao": f"Seu perfil ({role}) não tem permissão para mover a OS de {_status_label(current_status)} para {_status_label(new_status)}.",
            "current_status": current_status,
            "target_status": new_status,
        })

    if current_status == WorkOrder.Status.COMPLETED and new_status == WorkOrder.Status.IN_PROGRESS:
        if not (get_user_role(actor) in ADMINISTRATIVE_ROLES or user_has_permission(actor, "work_orders.reopen_completed")):
            raise WorkOrderTransitionError({
                "permissao": "Somente usuário autorizado pode voltar uma OS concluída para execução.",
                "current_status": current_status,
                "target_status": new_status,
            })

    if new_status == WorkOrder.Status.DELIVERED:
        profile = WorkshopProfile.get_solo()
        work_order.recalculate_totals(save=False)
        if work_order.balance_due > 0 and not profile.delivery_with_pending_payment_allowed:
            raise WorkOrderTransitionError({
                "status": "A entrega com pagamento pendente está bloqueada na configuração da oficina.",
                "current_status": current_status,
                "target_status": new_status,
                "balance_due": str(work_order.balance_due),
            })

    if rule.requires_note and not (note or "").strip():
        raise WorkOrderTransitionError({
            "note": f"Informe uma observação para a transição {_status_label(current_status)} → {_status_label(new_status)}.",
            "current_status": current_status,
            "target_status": new_status,
        })

    return rule


def allowed_target_values(work_order: WorkOrder, actor=None, source: str | None = SOURCE_MANUAL) -> set[str]:
    return {item["status"] for item in available_status_transitions(work_order, actor=actor, source=source)}
