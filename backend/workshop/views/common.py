from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
import logging
import requests
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.audit import audit_financial_event, audit_change, model_snapshot
from accounts.models import AuditLog
from accounts.permissions import HasViewPermission
from accounts.roles import ROLE_TECHNICIAN
from accounts.services import get_user_role, user_has_permission
from messaging.models import Contact
from finance.ledger import record_ledger_entry
from finance.models import AccountPayable, AccountReceivable, FinancialLedgerEntry
from purchasing.models import PurchaseOrder

from ..models import (
    GeneralCategory,
    WorkshopProfile,
    PartBrand,
    normalize_lookup_name,
    Part,
    PartStockMovement,
    ServicePackage,
    ServiceDefaultPart,
    Vehicle,
    WorkOrder,
    WorkOrderPhoto,
    WorkOrderEvent,
    WorkOrderCustomerApproval,
    WorkOrderDeliverySignature,
    WorkOrderMessage,
    WorkOrderNotificationRule,
    WorkOrderPart,
    WorkOrderPayment,
    WorkOrderService,
    WorkOrderServiceChecklistItem,
    WorkshopService,
    WorkshopServiceChecklistTemplate,
)
from ..serializers import (
    ChangeWorkOrderStatusSerializer,
    CompleteWorkOrderServiceSerializer,
    GeneralCategorySerializer,
    WorkshopProfileSerializer,
    PublicLandingSerializer,
    PartBrandSerializer,
    PartSerializer,
    PartStockMovementSerializer,
    QualityCheckWorkOrderServiceSerializer,
    SendWorkOrderMessageSerializer,
    ServicePackageSerializer,
    ServiceDefaultPartSerializer,
    StartWorkOrderServiceSerializer,
    StockAdjustmentSerializer,
    VehicleSerializer,
    WorkOrderDetailSerializer,
    WorkOrderPhotoSerializer,
    WorkOrderEventSerializer,
    WorkOrderListSerializer,
    WorkOrderMessageSerializer,
    WorkOrderCustomerApprovalCreateSerializer,
    WorkOrderCustomerApprovalDecisionSerializer,
    WorkOrderCustomerApprovalPublicSerializer,
    WorkOrderCustomerApprovalSerializer,
    WorkOrderDeliverySignatureCreateSerializer,
    WorkOrderDeliverySignatureSerializer,
    WorkOrderServiceChecklistItemSerializer,
    WorkshopServiceChecklistTemplateSerializer,
    WorkOrderNotificationRuleSerializer,
    WorkOrderPartSerializer,
    WorkOrderPaymentSerializer,
    PaymentReversalSerializer,
    WorkOrderSerializer,
    WorkOrderServiceSerializer,
    WorkshopServiceSerializer,
)
from ..documents import generate_work_order_pdf
from ..state_machine import SOURCE_SYSTEM
from ..services import adjust_part_stock, build_customer_approval_url, change_work_order_status, complete_work_order_service, quality_check_work_order_service, record_event, send_work_order_message, start_work_order_service, technical_move_work_order, trigger_status_notifications

User = get_user_model()
logger = logging.getLogger(__name__)


def drf_validation_from_django(exc):
    if hasattr(exc, "message_dict"):
        return ValidationError(exc.message_dict)
    if hasattr(exc, "messages"):
        return ValidationError(exc.messages)
    return ValidationError(str(exc))

def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

def pdf_response(work_order, document_type):
    content = generate_work_order_pdf(work_order, document_type=document_type)
    filename = f"{document_type}-{work_order.number}.pdf".replace("/", "-")
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response

def build_customer_approval_public_url(request, approval):
    """Monta a URL pública do frontend para aprovação digital.

    Em desenvolvimento, usa FRONTEND_BASE_URL do .env/settings para que o link
    enviado por e-mail aponte para o Vite. O frontend também pode sobrescrever
    enviando frontend_base_url no payload ou o header X-Frontend-Base-Url.
    """
    base_url = (
        request.data.get("frontend_base_url")
        or request.headers.get("X-Frontend-Base-Url")
        or getattr(settings, "FRONTEND_BASE_URL", "")
    )
    if not base_url:
        # Fallback defensivo: evita str.rstrip('/api/'), que remove caracteres e
        # não o sufixo literal. Ex.: http://host/api/ -> http://host
        absolute_root = request.build_absolute_uri("/").rstrip("/")
        base_url = absolute_root[:-4] if absolute_root.endswith("/api") else absolute_root
    return f"{str(base_url).rstrip('/')}{approval.public_url_path}"

def send_customer_approval_email(approval, public_url):
    """Envia e registra no console o link de aprovação digital para o cliente.

    A impressão explícita no log/STDOUT é intencional: mesmo que o ambiente esteja
    usando SMTP, Docker/Gunicorn ou outro backend de e-mail, o link de aprovação
    fica visível no console do backend para teste e homologação.
    """
    work_order = approval.work_order
    customer = work_order.customer
    recipient = (approval.customer_email_snapshot or getattr(customer, "email", "") or "").strip()
    customer_name = approval.customer_name_snapshot or customer.full_name or "cliente"
    vehicle_display = work_order.vehicle.display_name if work_order.vehicle_id else "veículo não informado"
    subject = f"Aprovação digital - {approval.document_type_label} {work_order.number}"
    message = (
        f"Olá {customer_name},\n\n"
        f"A oficina gerou um link para você analisar e aprovar digitalmente o documento abaixo.\n\n"
        f"Documento: {approval.document_type_label}\n"
        f"OS: {work_order.number}\n"
        f"Veículo: {vehicle_display}\n"
        f"Total: R$ {work_order.grand_total:.2f}\n"
        f"Validade: {approval.expires_at.strftime('%d/%m/%Y %H:%M') if approval.expires_at else 'sem validade definida'}\n\n"
        f"Acesse o link para aprovar ou recusar:\n{public_url}\n\n"
        "Caso você não tenha solicitado este atendimento, ignore esta mensagem.\n"
    )

    console_message = (
        "\n"
        "================ APROVACAO DIGITAL - EMAIL DE TESTE ================\n"
        f"Para: {recipient or '[cliente sem e-mail cadastrado]'}\n"
        f"Assunto: {subject}\n"
        f"Backend de e-mail: {settings.EMAIL_BACKEND}\n"
        "--------------------------------------------------------------------\n"
        f"{message}"
        "====================================================================\n"
    )
    logger.warning(console_message)

    if not recipient:
        return {
            "email_sent": False,
            "email_to": "",
            "email_backend": settings.EMAIL_BACKEND,
            "console_logged": True,
            "email_error": "Cliente sem e-mail cadastrado. O link foi gerado e impresso no console do backend, mas não foi enviado por e-mail.",
        }

    sent_count = send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
    return {
        "email_sent": bool(sent_count),
        "email_to": recipient,
        "email_backend": settings.EMAIL_BACKEND,
        "console_logged": True,
        "email_error": "",
    }
