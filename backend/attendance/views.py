from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasViewPermission
from workshop.documents import generate_estimate_pdf
from workshop.serializers import PartSerializer, WorkOrderDetailSerializer, WorkOrderListSerializer
from workshop.models import Part, WorkOrder

from .models import CounterSale, Estimate, EstimateCustomerApproval
from .serializers import (
    CancelCounterSaleSerializer,
    ChangeEstimateStatusSerializer,
    ConvertEstimateSerializer,
    CounterSaleSerializer,
    EstimateCustomerApprovalCreateSerializer,
    EstimateCustomerApprovalDecisionSerializer,
    EstimateCustomerApprovalPublicSerializer,
    EstimateCustomerApprovalSerializer,
    EstimateSerializer,
    FinalizeCounterSaleSerializer,
    RegisterCounterSalePaymentSerializer,
)
from .services import build_estimate_approval_url, ensure_pending_estimate_approval, send_estimate_approval_email


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def build_estimate_approval_public_url(request, approval, frontend_base_url=""):
    base_url = (
        frontend_base_url
        or request.data.get("frontend_base_url")
        or request.headers.get("X-Frontend-Base-Url")
    )
    if base_url:
        return f"{str(base_url).rstrip('/')}{approval.public_url_path}"
    return build_estimate_approval_url(approval)


class AttendanceDashboardView(APIView):
    permission_classes = [HasViewPermission]
    permission_code = "dashboard.attendance"

    def get(self, request):
        today = timezone.localdate()
        month_start = today.replace(day=1)
        open_work_order_statuses = [WorkOrder.Status.OPEN, WorkOrder.Status.WAITING_PARTS, WorkOrder.Status.IN_PROGRESS]
        estimate_open_statuses = [Estimate.Status.OPEN, Estimate.Status.DIAGNOSIS, Estimate.Status.AWAITING_APPROVAL]
        sales = CounterSale.objects.select_related("customer").all()
        estimates = Estimate.objects.select_related("customer", "vehicle", "converted_work_order").all()
        finalized_sales = sales.filter(status=CounterSale.Status.FINALIZED)
        sales_month = finalized_sales.filter(sold_at__date__gte=month_start).aggregate(total=Sum("total_amount"), paid=Sum("paid_amount"), balance=Sum("balance_amount"))
        estimates_month = estimates.filter(created_at__date__gte=month_start).aggregate(total=Sum("total_amount"))
        return Response({
            "counts": {
                "open_work_orders": WorkOrder.objects.filter(status__in=open_work_order_statuses).count(),
                "awaiting_approval_work_orders": estimates.filter(status=Estimate.Status.AWAITING_APPROVAL).count(),
                "ready_work_orders": WorkOrder.objects.filter(status=WorkOrder.Status.COMPLETED).count(),
                "estimates_open": estimates.filter(status__in=estimate_open_statuses).count(),
                "estimates_sent": estimates.filter(status=Estimate.Status.AWAITING_APPROVAL).count(),
                "estimates_approved_month": estimates.filter(status__in=[Estimate.Status.APPROVED, Estimate.Status.PARTIALLY_APPROVED, Estimate.Status.CONVERTED], approved_at__date__gte=month_start).count(),
                "counter_sales_today": finalized_sales.filter(sold_at__date=today).count(),
                "counter_sales_month_amount": sales_month["total"] or 0,
                "counter_sales_month_paid": sales_month["paid"] or 0,
                "counter_sales_month_balance": sales_month["balance"] or 0,
                "estimates_month_amount": estimates_month["total"] or 0,
                "low_stock_parts": Part.objects.filter(stock_quantity__lte=F("minimum_stock")).count(),
            },
            "work_order_status_counts": list(WorkOrder.objects.values("status").annotate(total=Count("id")).order_by("status")),
            "estimate_status_counts": list(estimates.values("status").annotate(total=Count("id")).order_by("status")),
            "sale_status_counts": list(sales.values("status").annotate(total=Count("id")).order_by("status")),
            "recent_work_orders": WorkOrderListSerializer(WorkOrder.objects.select_related("customer", "vehicle", "assigned_to")[:8], many=True).data,
            "recent_estimates": EstimateSerializer(estimates[:8], many=True).data,
            "recent_counter_sales": CounterSaleSerializer(sales[:8], many=True).data,
            "ready_work_orders": WorkOrderListSerializer(WorkOrder.objects.select_related("customer", "vehicle", "assigned_to").filter(status=WorkOrder.Status.COMPLETED)[:8], many=True).data,
            "low_stock_parts": PartSerializer(Part.objects.filter(stock_quantity__lte=F("minimum_stock"))[:8], many=True).data,
        })


class CounterSaleViewSet(viewsets.ModelViewSet):
    serializer_class = CounterSaleSerializer
    permission_classes = [HasViewPermission]
    permission_code_map = {
        "read": "counter_sales.view",
        "write": "counter_sales.manage",
        "create": "counter_sales.manage",
        "update": "counter_sales.manage",
        "partial_update": "counter_sales.manage",
        "destroy": "counter_sales.manage",
        "finalize": "counter_sales.manage",
        "register_payment": "payments.manage",
        "cancel": "counter_sales.manage",
    }
    queryset = CounterSale.objects.select_related("customer", "account_receivable").prefetch_related("items__part", "payments").all()

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        status_value = self.request.query_params.get("status")
        customer_id = self.request.query_params.get("customer")
        if search:
            qs = qs.filter(Q(number__icontains=search) | Q(customer_name__icontains=search) | Q(customer__first_name__icontains=search) | Q(customer__last_name__icontains=search) | Q(items__description__icontains=search) | Q(items__part__sku__icontains=search))
        if status_value:
            qs = qs.filter(status=status_value)
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        return qs.distinct()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["actor"] = self.request.user
        return context

    @action(detail=True, methods=["post"])
    def finalize(self, request, pk=None):
        sale = self.get_object()
        serializer = FinalizeCounterSaleSerializer(data=request.data, context={"counter_sale": sale, "actor": request.user})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(CounterSaleSerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="register-payment")
    def register_payment(self, request, pk=None):
        sale = self.get_object()
        serializer = RegisterCounterSalePaymentSerializer(data=request.data, context={"counter_sale": sale, "actor": request.user})
        serializer.is_valid(raise_exception=True)
        payment, updated = serializer.save()
        return Response({"payment_id": payment.id, "counter_sale": CounterSaleSerializer(updated).data})

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        sale = self.get_object()
        serializer = CancelCounterSaleSerializer(data=request.data, context={"counter_sale": sale, "actor": request.user})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(CounterSaleSerializer(updated).data)


class EstimateViewSet(viewsets.ModelViewSet):
    serializer_class = EstimateSerializer
    permission_classes = [HasViewPermission]
    permission_code_map = {
        "read": "estimates.view",
        "write": "estimates.manage",
        "create": "estimates.manage",
        "update": "estimates.manage",
        "partial_update": "estimates.manage",
        "destroy": "estimates.manage",
        "change_status": "estimates.manage",
        "convert_to_work_order": "work_orders.create",
        "customer_approvals": "estimates.view",
        "create_customer_approval": "estimates.manage",
        "document": "estimates.view",
    }
    queryset = Estimate.objects.select_related("customer", "vehicle", "converted_work_order").prefetch_related("services__service", "parts__part", "parts__service_item", "customer_approvals").all()

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        status_value = self.request.query_params.get("status")
        customer_id = self.request.query_params.get("customer")
        vehicle_id = self.request.query_params.get("vehicle")
        if search:
            qs = qs.filter(Q(number__icontains=search) | Q(title__icontains=search) | Q(complaint__icontains=search) | Q(customer__first_name__icontains=search) | Q(customer__last_name__icontains=search) | Q(vehicle__plate__icontains=search))
        if status_value:
            qs = qs.filter(status=status_value)
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if vehicle_id:
            qs = qs.filter(vehicle_id=vehicle_id)
        return qs.distinct()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["actor"] = self.request.user
        return context

    @action(detail=True, methods=["post"], url_path="change-status")
    def change_status(self, request, pk=None):
        estimate = self.get_object()
        serializer = ChangeEstimateStatusSerializer(data=request.data, context={"estimate": estimate, "actor": request.user})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(EstimateSerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="convert-to-work-order")
    def convert_to_work_order(self, request, pk=None):
        estimate = self.get_object()
        serializer = ConvertEstimateSerializer(data=request.data, context={"estimate": estimate, "actor": request.user})
        serializer.is_valid(raise_exception=True)
        work_order = serializer.save()
        return Response(WorkOrderDetailSerializer(work_order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="customer-approvals")
    def customer_approvals(self, request, pk=None):
        approvals = self.get_object().customer_approvals.select_related("requested_by", "generated_work_order").all()
        return Response(EstimateCustomerApprovalSerializer(approvals, many=True).data)

    @action(detail=True, methods=["post"], url_path="create-customer-approval")
    def create_customer_approval(self, request, pk=None):
        estimate = self.get_object()
        serializer = EstimateCustomerApprovalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approval = ensure_pending_estimate_approval(estimate, actor=request.user, expires_days=serializer.validated_data.get("expires_days", 7))
        public_url = build_estimate_approval_public_url(request, approval, frontend_base_url=serializer.validated_data.get("frontend_base_url", ""))
        email_info = send_estimate_approval_email(approval, public_url)
        data = EstimateCustomerApprovalSerializer(approval).data
        data["public_url"] = public_url
        data["email"] = email_info
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def document(self, request, pk=None):
        estimate = self.get_object()
        content = generate_estimate_pdf(estimate)
        filename = f"estimate-{estimate.number}.pdf".replace("/", "-")
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response


class EstimateApprovalPublicView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "public_approval"

    def get_object(self, token):
        return (
            EstimateCustomerApproval.objects
            .select_related("estimate__customer", "estimate__vehicle", "requested_by", "generated_work_order")
            .prefetch_related("estimate__services", "estimate__parts__part", "estimate__parts__service_item")
            .get(token=token, is_active=True)
        )

    def get(self, request, token):
        try:
            approval = self.get_object(token)
        except EstimateCustomerApproval.DoesNotExist:
            return Response({"detail": "Link de aprovação de orçamento não encontrado ou indisponível."}, status=status.HTTP_404_NOT_FOUND)
        return Response(EstimateCustomerApprovalPublicSerializer(approval).data)

    def post(self, request, token):
        try:
            approval = self.get_object(token)
        except EstimateCustomerApproval.DoesNotExist:
            return Response({"detail": "Link de aprovação de orçamento não encontrado ou indisponível."}, status=status.HTTP_404_NOT_FOUND)
        serializer = EstimateCustomerApprovalDecisionSerializer(
            data=request.data,
            context={
                "approval": approval,
                "ip_address": get_client_ip(request),
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            },
        )
        serializer.is_valid(raise_exception=True)
        updated_approval, work_order = serializer.save()
        updated_approval.refresh_from_db()
        return Response(EstimateCustomerApprovalPublicSerializer(updated_approval).data)

class EstimateApprovalPublicPdfView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "public_approval"

    def get(self, request, token):
        try:
            approval = (
                EstimateCustomerApproval.objects
                .select_related("estimate__customer", "estimate__vehicle")
                .prefetch_related("estimate__services", "estimate__parts__part", "estimate__parts__service_item")
                .get(token=token, is_active=True)
            )
        except EstimateCustomerApproval.DoesNotExist:
            return Response({"detail": "Link de aprovação de orçamento não encontrado ou indisponível."}, status=status.HTTP_404_NOT_FOUND)
        content = generate_estimate_pdf(approval.estimate)
        filename = f"estimate-{approval.estimate.number}.pdf".replace("/", "-")
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response
