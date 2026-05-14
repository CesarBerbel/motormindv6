from .common import *


class WorkshopDashboardView(APIView):
    permission_classes = [HasViewPermission]
    permission_code = ["dashboard.attendance", "dashboard.stock", "dashboard.technical", "dashboard.finance"]

    def get(self, request):
        today = timezone.localdate()
        open_statuses = [WorkOrder.Status.OPEN, WorkOrder.Status.WAITING_PARTS, WorkOrder.Status.IN_PROGRESS]
        month_start = today.replace(day=1)
        paid_month = WorkOrderPayment.objects.filter(paid_at__date__gte=month_start).aggregate(total=Sum("amount"))["total"] or 0
        return Response({
            "counts": {
                "vehicles": Vehicle.objects.count(),
                "parts": Part.objects.count(),
                "open_work_orders": WorkOrder.objects.filter(status__in=open_statuses).count(),
                "awaiting_approval": 0,
                "in_progress": WorkOrder.objects.filter(status=WorkOrder.Status.IN_PROGRESS).count(),
                "ready": WorkOrder.objects.filter(status=WorkOrder.Status.COMPLETED).count(),
                "delivered_today": WorkOrder.objects.filter(status=WorkOrder.Status.COMPLETED, delivered_at__date=today).count(),
                "low_stock_parts": Part.objects.filter(stock_quantity__lte=F("minimum_stock")).count(),
                "paid_month": paid_month,
            },
            "status_counts": list(WorkOrder.objects.values("status").annotate(total=Count("id")).order_by("status")),
            "recent_work_orders": WorkOrderListSerializer(WorkOrder.objects.select_related("customer", "vehicle", "assigned_to")[:10], many=True).data,
            "low_stock_parts": PartSerializer(Part.objects.filter(stock_quantity__lte=F("minimum_stock"))[:10], many=True).data,
        })


class RoleDashboardView(APIView):
    permission_classes = [HasViewPermission]

    def get(self, request, role):
        permission_by_role = {
            "dono": "users.manage",
            "administrativo": "users.manage",
            "atendimento": "dashboard.attendance",
            "estoque": "dashboard.stock",
            "tecnico": "dashboard.technical",
            "financeiro": "dashboard.finance",
        }
        required = permission_by_role.get(role)
        if required is None:
            raise ValidationError({"role": "Dashboard inválido."})
        if not user_has_permission(request.user, required):
            raise PermissionDenied("Você não tem permissão para este dashboard.")

        today = timezone.localdate()
        month_start = today.replace(day=1)
        open_statuses = [WorkOrder.Status.OPEN, WorkOrder.Status.WAITING_PARTS, WorkOrder.Status.IN_PROGRESS]
        base = {
            "role": role,
            "counts": {},
            "recent_work_orders": WorkOrderListSerializer(WorkOrder.objects.select_related("customer", "vehicle", "assigned_to")[:10], many=True).data,
            "low_stock_parts": [],
            "recent_payments": [],
        }

        if role in {"dono", "administrativo", "atendimento"}:
            base["counts"].update({
                "contacts": Contact.objects.count(),
                "vehicles": Vehicle.objects.count(),
                "open_work_orders": WorkOrder.objects.filter(status__in=open_statuses).count(),
                "awaiting_approval": 0,
                "delivered_today": WorkOrder.objects.filter(status=WorkOrder.Status.COMPLETED, delivered_at__date=today).count(),
            })
        if role in {"dono", "administrativo", "estoque"}:
            open_purchase_statuses = [PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.REQUESTED, PurchaseOrder.Status.APPROVED, PurchaseOrder.Status.ORDERED, PurchaseOrder.Status.PARTIALLY_RECEIVED]
            base["low_stock_parts"] = PartSerializer(Part.objects.filter(stock_quantity__lte=F("minimum_stock"))[:10], many=True).data
            base["counts"].update({
                "parts": Part.objects.count(),
                "low_stock_parts": Part.objects.filter(stock_quantity__lte=F("minimum_stock")).count(),
                "stock_movements_today": PartStockMovement.objects.filter(created_at__date=today).count(),
                "open_purchase_orders": PurchaseOrder.objects.filter(status__in=open_purchase_statuses).count(),
                "auto_purchase_orders": PurchaseOrder.objects.filter(origin=PurchaseOrder.Origin.AUTOMATIC, status__in=open_purchase_statuses).count(),
            })
        if role in {"dono", "administrativo", "tecnico"}:
            technician_qs = WorkOrderService.objects.select_related("work_order", "service", "technician")
            if get_user_role(request.user) == ROLE_TECHNICIAN:
                technician_qs = technician_qs.filter(Q(technician=request.user) | Q(work_order__assigned_to=request.user))
            base["counts"].update({
                "services_pending": technician_qs.filter(status=WorkOrderService.Status.PENDING).count(),
                "services_in_progress": technician_qs.filter(status=WorkOrderService.Status.IN_PROGRESS).count(),
                "services_done": technician_qs.filter(status=WorkOrderService.Status.DONE).count(),
            })
        if role in {"dono", "administrativo", "financeiro"}:
            base["recent_payments"] = WorkOrderPaymentSerializer(WorkOrderPayment.objects.select_related("work_order", "created_by")[:10], many=True).data
            paid_month = WorkOrderPayment.objects.filter(paid_at__date__gte=month_start).aggregate(total=Sum("amount"))["total"] or 0
            receivable_balance = AccountReceivable.objects.aggregate(total=Sum("balance_amount"))["total"] or 0
            payable_balance = AccountPayable.objects.aggregate(total=Sum("balance_amount"))["total"] or 0
            base["counts"].update({
                "paid_month": paid_month,
                "payments_today": WorkOrderPayment.objects.filter(paid_at__date=today).count(),
                "balance_due": receivable_balance,
                "payables_due": payable_balance,
                "projected_balance": receivable_balance - payable_balance,
                "open_receivables": AccountReceivable.objects.filter(status__in=[AccountReceivable.Status.OPEN, AccountReceivable.Status.PARTIAL, AccountReceivable.Status.OVERDUE]).count(),
                "overdue_receivables": AccountReceivable.objects.filter(status=AccountReceivable.Status.OVERDUE).count(),
                "open_payables": AccountPayable.objects.filter(status__in=[AccountPayable.Status.OPEN, AccountPayable.Status.PARTIAL, AccountPayable.Status.OVERDUE]).count(),
                "overdue_payables": AccountPayable.objects.filter(status=AccountPayable.Status.OVERDUE).count(),
            })
        return Response(base)


class TechnicalDashboardView(APIView):
    permission_classes = [HasViewPermission]
    permission_code = ["dashboard.technical", "technical.dashboard"]

    def _technicians(self):
        return User.objects.select_related("profile").filter(is_active=True, profile__role=ROLE_TECHNICIAN).order_by("first_name", "last_name", "username")

    def _selected_technician(self, request):
        technician_id = request.query_params.get("technician")
        if get_user_role(request.user) == ROLE_TECHNICIAN:
            return request.user
        if technician_id:
            try:
                return self._technicians().get(pk=technician_id)
            except User.DoesNotExist:
                raise ValidationError({"technician": "Técnico informado não foi encontrado."})
        return None

    def _order_queryset(self, request):
        qs = WorkOrder.objects.select_related("customer", "vehicle", "assigned_to").prefetch_related("services__technician").exclude(status=WorkOrder.Status.COMPLETED)
        selected = self._selected_technician(request)
        if selected:
            qs = qs.filter(Q(assigned_to=selected) | Q(services__technician=selected))
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(Q(number__icontains=search) | Q(title__icontains=search) | Q(customer__first_name__icontains=search) | Q(customer__last_name__icontains=search) | Q(vehicle__plate__icontains=search))
        return qs.distinct()

    def _estimate_queryset(self, request):
        from attendance.models import Estimate

        qs = Estimate.objects.select_related("customer", "vehicle", "converted_work_order", "revision_work_order").filter(
            status__in=[Estimate.Status.DRAFT, Estimate.Status.SENT]
        )
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(Q(number__icontains=search) | Q(title__icontains=search) | Q(complaint__icontains=search) | Q(customer__first_name__icontains=search) | Q(customer__last_name__icontains=search) | Q(vehicle__plate__icontains=search))
        return qs.distinct()

    def _serialize_estimates(self, queryset, limit=50):
        def serialize(item):
            return {
                "kind": "estimate",
                "id": item.id,
                "number": item.number,
                "customer_name": item.customer.full_name if item.customer_id else "Cliente não informado",
                "vehicle_display": item.vehicle.display_name if item.vehicle_id else "Sem veículo",
                "title": item.title,
                "complaint": item.complaint,
                "diagnosis": item.diagnosis,
                "status": item.status,
                "status_label": item.status_label,
                "priority": "normal",
                "priority_label": "Normal",
                "promised_at": None,
                "valid_until": item.valid_until,
                "assigned_to_name": "Orçamento / diagnóstico",
                "grand_total": item.total_amount,
                "paid_total": "0.00",
                "balance_due": item.total_amount,
                "converted_work_order": item.converted_work_order_id,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
        return [serialize(item) for item in list(queryset[:limit])]

    def _serialize_orders(self, queryset, limit=50):
        data = WorkOrderListSerializer(queryset[:limit], many=True).data
        for item in data:
            item["kind"] = "os"
        return list(data)

    def get(self, request):
        from attendance.models import Estimate

        qs = self._order_queryset(request)
        estimate_qs = self._estimate_queryset(request)
        queue_qs = qs.filter(status=WorkOrder.Status.OPEN).order_by("priority", "promised_at", "id")
        active_qs = qs.filter(status=WorkOrder.Status.IN_PROGRESS).order_by("priority", "promised_at", "id")
        waiting_parts_qs = qs.filter(status=WorkOrder.Status.WAITING_PARTS).order_by("priority", "promised_at", "id")
        approval_estimate_qs = estimate_qs.filter(status=Estimate.Status.SENT).order_by("valid_until", "id")
        estimate_queue_qs = estimate_qs.filter(status=Estimate.Status.DRAFT).order_by("valid_until", "id")
        estimate_diagnosis_qs = Estimate.objects.none()
        done_qs = WorkOrder.objects.select_related("customer", "vehicle", "assigned_to").filter(status=WorkOrder.Status.COMPLETED).order_by("-updated_at", "-completed_at", "id")[:30]
        today = timezone.localdate()
        selected = self._selected_technician(request)
        technicians = [
            {
                "id": user.id,
                "name": user.get_full_name() or user.username,
                "email": user.email,
                "specialty": getattr(getattr(user, "profile", None), "technician_specialty", ""),
                "specialty_label": getattr(getattr(user, "profile", None), "technician_specialty_label", ""),
            }
            for user in self._technicians()
        ]
        queue_items = self._serialize_orders(queue_qs) + self._serialize_estimates(estimate_queue_qs)
        active_items = self._serialize_orders(active_qs)
        approval_items = self._serialize_estimates(approval_estimate_qs)
        waiting_parts_items = self._serialize_orders(waiting_parts_qs)
        done_items = self._serialize_orders(done_qs, limit=30)
        return Response({
            "selected_technician": selected.id if selected else "",
            "technicians": technicians,
            "counts": {
                "queue": len(queue_items),
                "queue_work_orders": queue_qs.count(),
                "queue_estimates": estimate_queue_qs.count(),
                "active": len(active_items),
                "active_work_orders": active_qs.count(),
                "active_estimates": 0,
                "awaiting_approval": approval_estimate_qs.count(),
                "waiting_parts": waiting_parts_qs.count(),
                "done": WorkOrder.objects.filter(status=WorkOrder.Status.COMPLETED).count(),
                "late_promised_orders": qs.filter(status__in=[WorkOrder.Status.OPEN, WorkOrder.Status.WAITING_PARTS, WorkOrder.Status.IN_PROGRESS], promised_at__date__lt=today).count(),
            },
            "columns": {
                "queue": queue_items,
                "active": active_items,
                "approval": approval_items,
                "waiting_parts": waiting_parts_items,
                "done": done_items,
            },
            "services": WorkOrderServiceSerializer(WorkOrderService.objects.select_related("work_order", "service", "technician").filter(work_order__in=qs)[:100], many=True).data,
        })
