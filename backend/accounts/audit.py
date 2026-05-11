from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import models
from django.forms.models import model_to_dict
from django.utils import timezone

from .models import AuditLog


def get_client_ip(request):
    if not request:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _actor_from(user=None, request=None):
    actor = user
    if request is not None and getattr(request, "user", None) and request.user.is_authenticated:
        actor = request.user
    return actor if getattr(actor, "is_authenticated", False) else None


def serialize_audit_value(value):
    """Converte valores Django/Python para JSON estável no AuditLog."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, models.Model):
        return getattr(value, "pk", None)
    if hasattr(value, "name") and not isinstance(value, str):
        return value.name
    if isinstance(value, (list, tuple, set)):
        return [serialize_audit_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize_audit_value(item) for key, item in value.items()}
    return value


def model_snapshot(instance, fields=None):
    """Gera snapshot JSON do model para trilha before/after.

    Use campos explícitos para objetos financeiros e OS; isso evita salvar dados
    pessoais demais e mantém o log objetivo, legível e auditável.
    """
    if instance is None:
        return {}
    if fields is None:
        raw = model_to_dict(instance)
        fields = raw.keys()
    snapshot = {}
    for field in fields:
        try:
            value = getattr(instance, field)
        except AttributeError:
            continue
        if callable(value):
            continue
        snapshot[field] = serialize_audit_value(value)
    return snapshot


def model_diff(before, after):
    before = before or {}
    after = after or {}
    diff = {}
    for key in sorted(set(before.keys()) | set(after.keys())):
        old_value = before.get(key)
        new_value = after.get(key)
        if old_value != new_value:
            diff[key] = {"before": old_value, "after": new_value}
    return diff


def audit_log(*, action, instance=None, user=None, request=None, description="", before=None, after=None, metadata=None):
    app_label = ""
    model_name = ""
    object_id = ""
    object_repr = ""
    if instance is not None:
        meta = instance._meta
        app_label = meta.app_label
        model_name = meta.model_name
        object_id = str(getattr(instance, "pk", "") or "")
        object_repr = str(instance)[:255]
    actor = _actor_from(user=user, request=request)
    return AuditLog.objects.create(
        action=action,
        app_label=app_label,
        model_name=model_name,
        object_id=object_id,
        object_repr=object_repr,
        user=actor,
        description=description[:255],
        before=serialize_audit_value(before or {}),
        after=serialize_audit_value(after or {}),
        metadata=serialize_audit_value(metadata or {}),
        ip_address=get_client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else ""),
    )


def audit_change(*, action, instance, user=None, request=None, description="", before=None, after=None, metadata=None):
    before = before or {}
    after = after if after is not None else model_snapshot(instance)
    diff = model_diff(before, after)
    full_metadata = {"changed_fields": sorted(diff.keys()), "diff": diff, **(metadata or {})}
    return audit_log(
        action=action,
        instance=instance,
        user=user,
        request=request,
        description=description,
        before=before,
        after=after,
        metadata=full_metadata,
    )


def audit_financial_event(*, event_type, instance, user=None, request=None, description="", before=None, after=None, metadata=None, reason=""):
    """Registra evento financeiro padronizado no AuditLog.

    event_type deve ser uma das ações financeiras de AuditLog.Action.
    reason é mantido em metadata para aprovações, estornos e mudanças críticas.
    """
    metadata = {"domain": "finance", "reason": reason or "", **(metadata or {})}
    return audit_change(
        action=event_type,
        instance=instance,
        user=user,
        request=request,
        description=description,
        before=before,
        after=after,
        metadata=metadata,
    )


def require_audit_reason(reason, *, field_name="reason", min_length=5):
    reason = (reason or "").strip()
    if len(reason) < min_length:
        raise ValidationError({field_name: f"Informe uma justificativa com pelo menos {min_length} caracteres para esta ação crítica."})
    return reason
