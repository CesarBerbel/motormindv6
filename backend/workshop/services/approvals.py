from django.utils import timezone

from accounts.url_utils import get_frontend_base_url

from ..models import WorkOrderCustomerApproval


def build_customer_approval_url(approval):
    base_url = get_frontend_base_url().rstrip("/")
    return f"{base_url}{approval.public_url_path}"


def ensure_pending_customer_approval(work_order, actor=None, expires_days=7):
    approval = (
        WorkOrderCustomerApproval.objects
        .filter(
            work_order=work_order,
            document_type=WorkOrderCustomerApproval.DocumentType.ESTIMATE,
            status=WorkOrderCustomerApproval.Status.PENDING,
            is_active=True,
        )
        .order_by("-requested_at", "-id")
        .first()
    )
    if approval:
        return approval
    return WorkOrderCustomerApproval.objects.create(
        work_order=work_order,
        document_type=WorkOrderCustomerApproval.DocumentType.ESTIMATE,
        requested_by=actor if getattr(actor, "is_authenticated", False) else None,
        expires_at=timezone.now() + timezone.timedelta(days=expires_days),
    )
