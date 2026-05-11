import logging

from django.core.exceptions import ValidationError

from messaging.models import MessageTemplate
from messaging.services import create_and_send

from .context import work_order_context
from .events import record_event
from ..models import WorkshopProfile, WorkOrder, WorkOrderEvent, WorkOrderMessage, WorkOrderNotificationRule

logger = logging.getLogger(__name__)


def _notification_targets(rule):
    target = getattr(rule, "recipient_target", WorkOrderNotificationRule.RecipientTarget.CUSTOMER) if rule else WorkOrderNotificationRule.RecipientTarget.CUSTOMER
    if target == WorkOrderNotificationRule.RecipientTarget.BOTH:
        return [WorkOrderNotificationRule.RecipientTarget.CUSTOMER, WorkOrderNotificationRule.RecipientTarget.WORKSHOP]
    return [target]
def _recipient_kwargs_for_work_order(work_order, template, target):
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
        if not work_order.customer.email:
            raise ValidationError({"cliente": "Cliente sem email cadastrado."})
        return {"contact": work_order.customer, "raw_email": "", "raw_phone": ""}
    if not work_order.customer.phone_e164:
        raise ValidationError({"cliente": "Cliente sem WhatsApp em formato E.164."})
    return {"contact": work_order.customer, "raw_email": "", "raw_phone": ""}
def send_work_order_message(work_order, template, actor=None, trigger_type=WorkOrderMessage.TriggerType.MANUAL, notification_rule=None, recipient_target=None):
    targets = [recipient_target] if recipient_target else _notification_targets(notification_rule)
    created_relations = []
    for target in targets:
        kwargs = _recipient_kwargs_for_work_order(work_order, template, target)
        log = create_and_send(
            template=template,
            actor=actor,
            extra=work_order_context(work_order, actor=actor, include_approval=False),
            send_now=True,
            **kwargs,
        )
        relation = WorkOrderMessage.objects.create(
            work_order=work_order,
            trigger_type=trigger_type,
            trigger_status=work_order.status if trigger_type == WorkOrderMessage.TriggerType.STATUS_AUTO else "",
            channel=template.channel,
            recipient_target=target or "",
            template=template,
            notification_rule=notification_rule,
            message_log=log,
            status=log.status,
            error_message=log.error_message,
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
        event_type = WorkOrderEvent.EventType.MESSAGE_SENT if log.status == "sent" else WorkOrderEvent.EventType.ERROR
        status_label = "enviada" if log.status == "sent" else ("simulada/ignorada" if log.status == "skipped" else "falhou")
        record_event(
            work_order,
            event_type,
            actor=actor,
            description=(
                f"Mensagem {template.channel} {status_label} pelo template {template.name} "
                f"para {dict(WorkOrderNotificationRule.RecipientTarget.choices).get(target, target)}."
                + (f" Detalhe: {log.error_message}" if log.error_message else "")
            ),
            data={"message_log_id": log.id, "work_order_message_id": relation.id, "status": log.status, "recipient_target": target, "error_message": log.error_message},
        )
        created_relations.append(relation)
    return created_relations[0] if len(created_relations) == 1 else created_relations
def _create_failed_work_order_message(work_order, rule, actor, error_message):
    """Registra falha de notificacao automatica na tabela de mensagens e no historico da OS."""
    relation = WorkOrderMessage.objects.create(
        work_order=work_order,
        trigger_type=WorkOrderMessage.TriggerType.STATUS_AUTO,
        trigger_status=work_order.status,
        channel=getattr(rule, "channel", "") or getattr(getattr(rule, "template", None), "channel", ""),
        recipient_target=getattr(rule, "recipient_target", "") or "",
        template=getattr(rule, "template", None),
        notification_rule=rule,
        status="failed",
        error_message=str(error_message),
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    record_event(
        work_order,
        WorkOrderEvent.EventType.ERROR,
        actor=actor,
        description=f"Notificacao automatica {getattr(rule, 'name', '')} falhou: {error_message}",
        data={"work_order_message_id": relation.id, "status": "failed", "error_message": str(error_message)},
    )
    return relation
def trigger_status_notifications(work_order, actor=None):
    """Dispara as notificacoes automaticas do status atual da OS.

    Esta funcao imprime e registra cada etapa. Se uma regra for encontrada, ela
    sempre gera um WorkOrderMessage: sent/failed. Assim a tela de historico de
    mensagens mostra exatamente por que nao saiu email/WhatsApp.
    """
    sent = []
    logger.info(
        "\n================ MENSAGERIA - GATILHO AUTOMATICO DE OS ================\n"
        "OS: %s | ID: %s\n"
        "Status atual: %s (%s)\n"
        "Buscando regras ativas para este status...\n"
        "======================================================================",
        work_order.number,
        work_order.pk,
        work_order.status_label,
        work_order.status,
    )
    rules = list(
        WorkOrderNotificationRule.objects.select_related("template").filter(
            is_active=True,
            entity_type=WorkOrderNotificationRule.EntityType.WORK_ORDER,
            trigger_status=work_order.status,
        )
    )
    logger.info("[MENSAGERIA AUTO] Regras encontradas para %s: %s", work_order.status, len(rules))
    if not rules:
        detail = f"Nenhuma notificacao automatica ativa configurada para o status {work_order.status_label} ({work_order.status})."
        logger.info("[MENSAGERIA AUTO] %s", detail)
        record_event(work_order, WorkOrderEvent.EventType.ERROR, actor=actor, description=detail)
        return sent

    for rule in rules:
        template = getattr(rule, "template", None)
        logger.info(
            "[MENSAGERIA AUTO] Regra ID=%s | nome='%s' | ativa=%s | status=%s | canal_regra=%s | template_id=%s | template='%s' | canal_template=%s | template_ativo=%s | destinatario=%s | enviar_uma_vez=%s",
            rule.id,
            rule.name,
            rule.is_active,
            rule.trigger_status,
            rule.channel,
            getattr(template, "id", None),
            getattr(template, "name", ""),
            getattr(template, "channel", ""),
            getattr(template, "is_active", None),
            getattr(rule, "recipient_target", ""),
            rule.send_once_per_status,
        )
        if not template:
            relation = _create_failed_work_order_message(work_order, rule, actor, "Template removido ou nao encontrado.")
            sent.append(relation.id)
            logger.warning("[MENSAGERIA AUTO] Regra %s falhou: template ausente.", rule.name)
            continue
        if not template.is_active:
            relation = _create_failed_work_order_message(work_order, rule, actor, "Template inativo.")
            sent.append(relation.id)
            logger.warning("[MENSAGERIA AUTO] Regra %s falhou: template inativo.", rule.name)
            continue
        if template.channel != rule.channel:
            # Antes esta divergencia ignorava a regra. Na pratica isso escondia o erro e impedia o envio.
            # Agora o envio segue pelo canal do template e o ajuste fica registrado para auditoria.
            warning = (
                f"Regra {rule.name} tem canal {rule.channel}, mas o template {template.name} e do canal {template.channel}. "
                f"O envio automatico seguira pelo canal do template."
            )
            logger.warning("[MENSAGERIA AUTO] AVISO: %s", warning)
            record_event(work_order, WorkOrderEvent.EventType.UPDATED, actor=actor, description=warning)
        if rule.send_once_per_status:
            already_sent = WorkOrderMessage.objects.filter(
                work_order=work_order,
                notification_rule=rule,
                trigger_status=work_order.status,
                message_log__status="sent",
            ).exists()
            if already_sent:
                detail = f"Regra {rule.name} nao reenviada: ja existe envio automatico com sucesso para este status."
                logger.info("[MENSAGERIA AUTO] %s", detail)
                record_event(work_order, WorkOrderEvent.EventType.UPDATED, actor=actor, description=detail)
                continue
        try:
            logger.info(
                "[MENSAGERIA AUTO] Executando regra '%s' | canal_template=%s | destinatario=%s",
                rule.name,
                template.channel,
                getattr(rule, "recipient_target", ""),
            )
            relation = send_work_order_message(
                work_order,
                template,
                actor=actor,
                trigger_type=WorkOrderMessage.TriggerType.STATUS_AUTO,
                notification_rule=rule,
            )
            relations = relation if isinstance(relation, list) else [relation]
            sent.extend(item.id for item in relations)
            logger.info(
                "[MENSAGERIA AUTO] Regra '%s' gerou WorkOrderMessage IDs/status: %s",
                rule.name,
                [(item.id, item.status, item.error_message) for item in relations],
            )
        except Exception as exc:
            relation = _create_failed_work_order_message(work_order, rule, actor, exc)
            sent.append(relation.id)
            logger.exception("[MENSAGERIA AUTO] ERRO na regra %s: %s", rule.name, exc)
    return sent
