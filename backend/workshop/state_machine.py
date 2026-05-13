"""Máquina de estados oficial da Ordem de Serviço.

A OS agora representa somente a execução operacional depois que um orçamento foi
aprovado total ou parcialmente. Diagnóstico e aprovação pertencem ao orçamento.
"""

from dataclasses import dataclass

from django.core.exceptions import ValidationError

from accounts.roles import ROLE_ADMINISTRATIVE, ROLE_ATTENDANT, ROLE_FINANCE, ROLE_OWNER, ROLE_STOCK, ROLE_TECHNICIAN
from accounts.services import get_user_role, user_has_permission

from .models import WorkOrder


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

WORK_ORDER_STATE_GRAPH: dict[str, tuple[TransitionRule, ...]] = {
    WorkOrder.Status.OPEN: (
        TransitionRule(
            target=WorkOrder.Status.IN_PROGRESS,
            label="Iniciar execução",
            description="Inicia a execução de uma OS aberta gerada a partir de orçamento aprovado.",
            roles=TECHNICAL_ROLES,
            sources=frozenset({SOURCE_MANUAL, SOURCE_TECHNICAL_START, SOURCE_SYSTEM}),
        ),
        TransitionRule(
            target=WorkOrder.Status.WAITING_PARTS,
            label="Aguardar peças",
            description="Pausa a OS aberta enquanto peças necessárias são separadas ou compradas.",
            roles=TECHNICAL_ROLES,
            sources=frozenset({SOURCE_MANUAL, SOURCE_TECHNICAL_WAITING_PARTS, SOURCE_SYSTEM}),
        ),
        TransitionRule(
            target=WorkOrder.Status.CANCELLED,
            label="Cancelar OS",
            description="Cancela uma OS aberta com justificativa obrigatória.",
            roles=ATTENDANCE_ROLES | TECHNICAL_ROLES | FINISHING_ROLES,
            sources=frozenset({SOURCE_MANUAL, SOURCE_SYSTEM}),
            requires_note=True,
        ),
    ),
    WorkOrder.Status.IN_PROGRESS: (
        TransitionRule(
            target=WorkOrder.Status.WAITING_PARTS,
            label="Aguardar peças",
            description="Pausa a execução enquanto peças necessárias são separadas ou compradas.",
            roles=TECHNICAL_ROLES,
            sources=frozenset({SOURCE_MANUAL, SOURCE_TECHNICAL_WAITING_PARTS, SOURCE_SYSTEM}),
        ),
        TransitionRule(
            target=WorkOrder.Status.COMPLETED,
            label="Concluir OS",
            description="Conclui a execução operacional da OS.",
            roles=TECHNICAL_ROLES | FINISHING_ROLES,
            sources=frozenset({SOURCE_MANUAL, SOURCE_TECHNICAL_COMPLETE, SOURCE_SYSTEM}),
        ),
        TransitionRule(
            target=WorkOrder.Status.CANCELLED,
            label="Cancelar OS",
            description="Cancela uma OS em execução com justificativa obrigatória.",
            roles=ATTENDANCE_ROLES | TECHNICAL_ROLES | FINISHING_ROLES,
            sources=frozenset({SOURCE_MANUAL, SOURCE_SYSTEM}),
            requires_note=True,
        ),
    ),
    WorkOrder.Status.WAITING_PARTS: (
        TransitionRule(
            target=WorkOrder.Status.IN_PROGRESS,
            label="Retomar execução",
            description="Retoma uma OS que estava aguardando peças.",
            roles=TECHNICAL_ROLES,
            sources=frozenset({SOURCE_MANUAL, SOURCE_TECHNICAL_START, SOURCE_SYSTEM}),
        ),
        TransitionRule(
            target=WorkOrder.Status.COMPLETED,
            label="Concluir sem nova execução",
            description="Conclui a OS diretamente quando a pendência de peças foi resolvida fora da bancada.",
            roles=TECHNICAL_ROLES | FINISHING_ROLES,
            sources=frozenset({SOURCE_MANUAL, SOURCE_TECHNICAL_COMPLETE, SOURCE_SYSTEM}),
            requires_note=True,
        ),
        TransitionRule(
            target=WorkOrder.Status.CANCELLED,
            label="Cancelar OS",
            description="Cancela uma OS aguardando peças com justificativa obrigatória.",
            roles=ATTENDANCE_ROLES | TECHNICAL_ROLES | FINISHING_ROLES,
            sources=frozenset({SOURCE_MANUAL, SOURCE_SYSTEM}),
            requires_note=True,
        ),
    ),
    WorkOrder.Status.COMPLETED: (),
    WorkOrder.Status.CANCELLED: (),
}

TERMINAL_STATUSES = frozenset({WorkOrder.Status.COMPLETED, WorkOrder.Status.CANCELLED})

STATE_ORDER = {
    WorkOrder.Status.OPEN: 10,
    WorkOrder.Status.IN_PROGRESS: 20,
    WorkOrder.Status.WAITING_PARTS: 25,
    WorkOrder.Status.COMPLETED: 30,
    WorkOrder.Status.CANCELLED: 99,
}

INVALID_REGRESSION_HINTS = {
    (WorkOrder.Status.COMPLETED, WorkOrder.Status.OPEN): "OS concluída é estado final operacional. Abra uma nova OS de retorno/garantia se necessário.",
    (WorkOrder.Status.COMPLETED, WorkOrder.Status.IN_PROGRESS): "OS concluída não volta para execução pelo fluxo principal. Registre uma OS de retorno/garantia.",
    (WorkOrder.Status.CANCELLED, WorkOrder.Status.OPEN): "OS cancelada não pode ser reaberta pelo fluxo operacional. Abra uma nova OS ou gere um novo orçamento, se necessário.",
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
        if source not in rule.sources and SOURCE_SYSTEM not in rule.sources:
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
            "status": f"A OS está em estado final ({_status_label(current_status)}) e não pode mudar de status pelo fluxo operacional.",
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

    if rule.requires_note and not (note or "").strip():
        raise WorkOrderTransitionError({
            "note": f"Informe uma observação para a transição {_status_label(current_status)} → {_status_label(new_status)}.",
            "current_status": current_status,
            "target_status": new_status,
        })

    return rule


def allowed_target_values(work_order: WorkOrder, actor=None, source: str | None = SOURCE_MANUAL) -> set[str]:
    return {item["status"] for item in available_status_transitions(work_order, actor=actor, source=source)}
