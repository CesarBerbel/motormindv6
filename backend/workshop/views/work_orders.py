from .common import *

WORK_ORDER_AUDIT_FIELDS = ["number", "status", "financial_status", "priority", "manual_discount_amount", "discount_total", "grand_total", "paid_total", "balance_due", "mileage_in", "mileage_out", "promised_at", "assigned_to_id"]
WORK_ORDER_SERVICE_AUDIT_FIELDS = ["description", "quantity", "unit_price", "discount_amount", "status", "technician_id", "notes", "technical_diagnosis", "execution_notes"]
WORK_ORDER_PART_AUDIT_FIELDS = ["description", "quantity", "unit_price", "cost_price", "discount_amount", "consume_inventory", "notes"]
WORK_ORDER_PAYMENT_AUDIT_FIELDS = ["method", "amount", "paid_at", "reference", "notes", "reversed_at", "reversal_reason"]


class WorkOrderViewSet(viewsets.ModelViewSet):
    permission_classes = [HasViewPermission]
    permission_code_map = {"read": "work_orders.view", "create": "work_orders.create", "update": "work_orders.edit", "partial_update": "work_orders.edit", "destroy": "work_orders.edit", "change_status": "work_orders.status", "cancel": "work_orders.status", "technical_action": "technical.execute", "send_message": "messages.send", "recalculate": ["work_orders.edit", "payments.manage"], "trigger_notifications": "messages.send", "document": "work_orders.view", "customer_approvals": "work_orders.view", "create_customer_approval": "work_orders.edit", "manual_approval": "work_orders.edit", "create_revision_estimate": "work_orders.edit", "delivery_signature": "work_orders.view", "create_delivery_signature": "work_orders.edit", "delivery_receipt": "work_orders.view"}
    queryset = WorkOrder.objects.select_related("customer", "vehicle", "assigned_to", "created_by", "updated_by").prefetch_related("services__service", "services__source_package", "services__checklist_items", "parts__part", "payments", "photos__uploaded_by", "events__actor", "messages__template", "messages__message_log")

    def get_serializer_class(self):
        if self.action == "list":
            return WorkOrderListSerializer
        if self.action == "retrieve":
            return WorkOrderDetailSerializer
        return WorkOrderSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        status_value = self.request.query_params.get("status")
        customer_id = self.request.query_params.get("customer")
        vehicle_id = self.request.query_params.get("vehicle")
        priority = self.request.query_params.get("priority")
        assigned_to = self.request.query_params.get("assigned_to")
        if search:
            qs = qs.filter(Q(number__icontains=search) | Q(title__icontains=search) | Q(complaint__icontains=search) | Q(customer__first_name__icontains=search) | Q(customer__last_name__icontains=search) | Q(vehicle__plate__icontains=search))
        if status_value:
            qs = qs.filter(status=status_value)
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if vehicle_id:
            qs = qs.filter(vehicle_id=vehicle_id)
        if priority:
            qs = qs.filter(priority=priority)
        if assigned_to:
            qs = qs.filter(assigned_to_id=assigned_to)
        if get_user_role(self.request.user) == ROLE_TECHNICIAN:
            qs = qs.filter(Q(assigned_to=self.request.user) | Q(services__technician=self.request.user))
        return qs.distinct()

    def perform_create(self, serializer):
        work_order = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        record_event(work_order, WorkOrderEvent.EventType.CREATED, actor=self.request.user, description="Ordem de servico criada.", new_status=work_order.status)

    def perform_update(self, serializer):
        instance = self.get_object()
        before = model_snapshot(instance, WORK_ORDER_AUDIT_FIELDS)
        old_status = instance.status
        old_discount = instance.manual_discount_amount
        work_order = serializer.save(updated_by=self.request.user)
        work_order.refresh_from_db()
        after = model_snapshot(work_order, WORK_ORDER_AUDIT_FIELDS)
        status_changed = old_status != work_order.status
        if status_changed:
            record_event(
                work_order,
                WorkOrderEvent.EventType.STATUS_CHANGED,
                actor=self.request.user,
                description=f"Status alterado para {work_order.status_label} pela edicao da OS.",
                old_status=old_status,
                new_status=work_order.status,
            )
            audit_financial_event(
                event_type=AuditLog.Action.FINANCIAL_STATUS,
                instance=work_order,
                user=self.request.user,
                request=self.request,
                description="Status da OS alterado por edição direta.",
                before=before,
                after=after,
                metadata={"old_status": old_status, "new_status": work_order.status},
            )
            trigger_status_notifications(work_order, actor=self.request.user)
        else:
            record_event(work_order, WorkOrderEvent.EventType.UPDATED, actor=self.request.user, description="Ordem de servico atualizada.")
            audit_change(
                action=AuditLog.Action.CRITICAL_UPDATE,
                instance=work_order,
                user=self.request.user,
                request=self.request,
                description="Ordem de serviço atualizada.",
                before=before,
                after=after,
                metadata={"domain": "workshop"},
            )
        if old_discount != work_order.manual_discount_amount:
            audit_financial_event(
                event_type=AuditLog.Action.FINANCIAL_DISCOUNT,
                instance=work_order,
                user=self.request.user,
                request=self.request,
                description="Desconto manual da OS alterado.",
                before={"manual_discount_amount": old_discount},
                after={"manual_discount_amount": work_order.manual_discount_amount},
                metadata={"work_order_id": work_order.id, "work_order_number": work_order.number},
            )

    @action(detail=True, methods=["post"])
    def change_status(self, request, pk=None):
        serializer = ChangeWorkOrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated, message_ids = change_work_order_status(self.get_object(), serializer.validated_data["status"], actor=request.user, note=serializer.validated_data.get("note", ""), send_notifications=serializer.validated_data.get("send_notifications", True))
        except DjangoValidationError as exc:
            raise drf_validation_from_django(exc) from exc
        return Response({"work_order": WorkOrderDetailSerializer(updated).data, "work_order_message_ids": message_ids})

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        serializer = CancelWorkOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated, message_ids = cancel_work_order(
                self.get_object(),
                actor=request.user,
                reason=serializer.validated_data["reason"],
                send_notifications=serializer.validated_data.get("send_notifications", True),
            )
        except DjangoValidationError as exc:
            raise drf_validation_from_django(exc) from exc
        return Response({"work_order": WorkOrderDetailSerializer(updated, context={"request": request}).data, "work_order_message_ids": message_ids})

    @action(detail=True, methods=["post"], url_path="technical-action")
    def technical_action(self, request, pk=None):
        action_name = request.data.get("action")
        note = request.data.get("note", "")
        try:
            updated, message_ids = technical_move_work_order(
                self.get_object(),
                action_name,
                actor=request.user,
                note=note,
                send_notifications=request.data.get("send_notifications", True) is not False,
                diagnosis_description=request.data.get("diagnosis_description", request.data.get("diagnosis", "")),
            )
        except DjangoValidationError as exc:
            raise drf_validation_from_django(exc) from exc
        return Response({"work_order": WorkOrderDetailSerializer(updated, context={"request": request}).data, "work_order_message_ids": message_ids})

    @action(detail=True, methods=["post"])
    def send_message(self, request, pk=None):
        serializer = SendWorkOrderMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            relation = send_work_order_message(self.get_object(), serializer.validated_data["template"], actor=request.user)
        except DjangoValidationError as exc:
            raise drf_validation_from_django(exc) from exc
        return Response(WorkOrderMessageSerializer(relation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def recalculate(self, request, pk=None):
        work_order = self.get_object()
        work_order.recalculate_totals()
        return Response(WorkOrderDetailSerializer(work_order).data)

    @action(detail=True, methods=["get"])
    def document(self, request, pk=None):
        document_type = request.query_params.get("type") or WorkOrderCustomerApproval.DocumentType.WORK_ORDER
        if document_type not in dict(WorkOrderCustomerApproval.DocumentType.choices):
            raise ValidationError({"type": "Tipo de documento inválido."})
        return pdf_response(self.get_object(), document_type)

    @action(detail=True, methods=["get"])
    def customer_approvals(self, request, pk=None):
        approvals = self.get_object().customer_approvals.select_related("requested_by").all()
        return Response(WorkOrderCustomerApprovalSerializer(approvals, many=True).data)

    @action(detail=True, methods=["post"])
    def create_customer_approval(self, request, pk=None):
        serializer = WorkOrderCustomerApprovalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        work_order = self.get_object()
        expires_days = serializer.validated_data.get("expires_days") or 7
        approval = WorkOrderCustomerApproval.objects.create(
            work_order=work_order,
            document_type=serializer.validated_data["document_type"],
            requested_by=request.user,
            expires_at=timezone.now() + timezone.timedelta(days=expires_days),
        )
        public_url = build_customer_approval_public_url(request, approval)
        email_info = {}
        try:
            email_info = send_customer_approval_email(approval, public_url)
        except Exception as exc:  # noqa: BLE001 - retorna erro claro sem perder o link gerado
            email_info = {
                "email_sent": False,
                "email_to": approval.customer_email_snapshot or "",
                "email_backend": settings.EMAIL_BACKEND,
                "console_logged": True,
                "email_error": f"Link gerado e impresso no console do backend, mas houve falha ao enviar e-mail: {exc}",
            }

        event_description = f"Link de aprovação digital gerado para {approval.document_type_label}."
        if email_info.get("email_sent"):
            event_description += f" E-mail enviado para {email_info.get('email_to')}."
        elif email_info.get("email_error"):
            event_description += f" {email_info.get('email_error')}"
        record_event(
            work_order,
            WorkOrderEvent.EventType.UPDATED,
            actor=request.user,
            description=event_description,
            data={
                "approval_id": approval.id,
                "document_type": approval.document_type,
                "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
                "public_url": public_url,
                **email_info,
            },
        )
        data = WorkOrderCustomerApprovalSerializer(approval).data
        data["public_url"] = public_url
        data.update(email_info)
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="manual-approval")
    def manual_approval(self, request, pk=None):
        serializer = WorkOrderManualApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        work_order = self.get_object()
        now = timezone.now()
        actor_name = (request.user.get_full_name() or request.user.get_username() or str(request.user)).strip()
        signature_name = serializer.validated_data.get("signature_name", "").strip()
        approval_type = serializer.validated_data.get("approval_type", "total")
        decision_name = (signature_name or actor_name or "Aprovação manual")[:180]
        audit_note = f"Aprovação manual {'parcial' if approval_type == 'partial' else 'total'} registrada"
        if actor_name:
            audit_note += f" por {actor_name} em {timezone.localtime(now).strftime('%d/%m/%Y %H:%M')}"
        if signature_name:
            audit_note += f" com assinatura/confirmação do cliente {signature_name}"
        notes = f"{serializer.validated_data['notes']}\n{audit_note}".strip()
        approval = WorkOrderCustomerApproval.objects.create(
            work_order=work_order,
            document_type=WorkOrderCustomerApproval.DocumentType.WORK_ORDER,
            requested_by=request.user,
            requested_at=now,
            expires_at=now,
            status=WorkOrderCustomerApproval.Status.APPROVED,
            decision_name=decision_name,
            decision_document=serializer.validated_data.get("signature_document", ""),
            decision_notes=notes,
            decided_at=now,
            decision_ip=get_client_ip(request),
            decision_user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        if not work_order.approved_at:
            work_order.approved_at = now
            work_order.updated_by = request.user
            work_order.save(update_fields=["approved_at", "updated_by", "updated_at"])
        record_event(
            work_order,
            WorkOrderEvent.EventType.UPDATED,
            actor=request.user,
            description=f"Aprovação manual {'parcial' if approval_type == 'partial' else 'total'} registrada para a OS.",
            data={"approval_id": approval.id, "approval_type": approval_type, "decision_name": decision_name},
        )
        return Response(WorkOrderCustomerApprovalSerializer(approval).data, status=status.HTTP_201_CREATED)


    @action(detail=True, methods=["post"], url_path="create-revision-estimate")
    def create_revision_estimate(self, request, pk=None):
        work_order = self.get_object()
        from attendance.serializers import EstimateSerializer
        from attendance.services import create_revision_estimate_from_work_order

        try:
            estimate = create_revision_estimate_from_work_order(work_order, payload=request.data, actor=request.user)
        except DjangoValidationError as exc:
            raise drf_validation_from_django(exc) from exc
        data = EstimateSerializer(estimate, context={"request": request}).data
        return Response({
            "detail": "OS já aprovada. Foi gerado um novo orçamento de revisão para aprovação do cliente.",
            "estimate": data,
        }, status=status.HTTP_201_CREATED)


    @action(detail=True, methods=["post"])
    def trigger_notifications(self, request, pk=None):
        return Response({"work_order_message_ids": trigger_status_notifications(self.get_object(), actor=request.user)})

    @action(detail=True, methods=["get"], url_path="delivery-signature")
    def delivery_signature(self, request, pk=None):
        work_order = self.get_object()
        try:
            signature = work_order.delivery_signature
        except WorkOrderDeliverySignature.DoesNotExist:
            return Response(None)
        return Response(WorkOrderDeliverySignatureSerializer(signature, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="delivery-signature")
    def create_delivery_signature(self, request, pk=None):
        work_order = self.get_object()
        profile = WorkshopProfile.get_solo()
        if not profile.delivery_signature_enabled:
            raise ValidationError({"detail": "Assinatura digital de entrega está desativada nas configurações administrativas."})
        serializer = WorkOrderDeliverySignatureCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        signature, _created = WorkOrderDeliverySignature.objects.update_or_create(
            work_order=work_order,
            defaults={
                "recipient_name": serializer.validated_data["recipient_name"],
                "recipient_document": serializer.validated_data.get("recipient_document", ""),
                "notes": serializer.validated_data.get("notes", ""),
                "signature_image": serializer.validated_data["signature_data_url"],
                "signed_ip": get_client_ip(request),
                "signed_user_agent": request.META.get("HTTP_USER_AGENT", ""),
                "signed_by_user": request.user,
                "signed_at": timezone.now(),
            },
        )
        if work_order.status != WorkOrder.Status.DELIVERED:
            try:
                work_order, _message_ids = change_work_order_status(
                    work_order,
                    WorkOrder.Status.DELIVERED,
                    actor=request.user,
                    note=serializer.validated_data.get("notes", "") or f"Entrega assinada por {signature.recipient_name}.",
                    send_notifications=True,
                )
            except DjangoValidationError as exc:
                raise drf_validation_from_django(exc) from exc
        record_event(
            work_order,
            WorkOrderEvent.EventType.DELIVERY_SIGNED,
            actor=request.user,
            description=f"Entrega assinada digitalmente por {signature.recipient_name}.",
            data={"delivery_signature_id": signature.id, "recipient_document": signature.recipient_document},
        )
        return Response(WorkOrderDeliverySignatureSerializer(signature, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="delivery-receipt")
    def delivery_receipt(self, request, pk=None):
        return pdf_response(self.get_object(), "delivery_receipt")

class WorkOrderServiceChecklistItemViewSet(viewsets.ModelViewSet):
    serializer_class = WorkOrderServiceChecklistItemSerializer
    permission_classes = [HasViewPermission]
    permission_code_map = {"read": "work_orders.view", "write": ["technical.execute", "work_orders.edit"]}
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    queryset = WorkOrderServiceChecklistItem.objects.select_related("work_order", "work_order_service", "completed_by", "source_template").all()

    def get_queryset(self):
        qs = super().get_queryset()
        work_order_id = self.request.query_params.get("work_order")
        service_line_id = self.request.query_params.get("work_order_service")
        if work_order_id:
            qs = qs.filter(work_order_id=work_order_id)
        if service_line_id:
            qs = qs.filter(work_order_service_id=service_line_id)
        return qs.order_by("work_order_service_id", "sort_order", "id")

    def perform_update(self, serializer):
        instance = serializer.save(completed_by=self.request.user if serializer.validated_data.get("is_completed") else None)
        record_event(
            instance.work_order,
            WorkOrderEvent.EventType.CHECKLIST_UPDATED,
            actor=self.request.user,
            description=f"Checklist técnico atualizado: {instance.description}.",
            data={"checklist_item_id": instance.id, "completed": instance.is_completed},
        )

class WorkOrderServiceViewSet(viewsets.ModelViewSet):
    serializer_class = WorkOrderServiceSerializer
    permission_classes = [HasViewPermission]
    permission_code_map = {
        "read": "work_order_services.view",
        "write": "work_order_services.manage",
        "start_execution": "technical.execute",
        "complete_execution": "technical.execute",
        "quality_check": ["technical.quality_check", "work_orders.edit"],
    }
    queryset = WorkOrderService.objects.select_related("work_order", "work_order__customer", "work_order__vehicle", "service", "source_package", "technician", "quality_checked_by").all()

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("work_order"):
            qs = qs.filter(work_order_id=self.request.query_params["work_order"])
        if self.request.query_params.get("status"):
            qs = qs.filter(status=self.request.query_params["status"])
        if self.request.query_params.get("technician"):
            qs = qs.filter(technician_id=self.request.query_params["technician"])
        if self.request.query_params.get("mine") == "true":
            qs = qs.filter(Q(technician=self.request.user) | Q(work_order__assigned_to=self.request.user))
        if get_user_role(self.request.user) == ROLE_TECHNICIAN:
            qs = qs.filter(Q(technician=self.request.user) | Q(work_order__assigned_to=self.request.user))
        return qs.distinct()

    def perform_create(self, serializer):
        line = serializer.save()
        audit_financial_event(
            event_type=AuditLog.Action.FINANCIAL_UPDATE,
            instance=line.work_order,
            user=self.request.user,
            request=self.request,
            description="Serviço financeiro adicionado à OS.",
            before={},
            after=model_snapshot(line, WORK_ORDER_SERVICE_AUDIT_FIELDS),
            metadata={"work_order_id": line.work_order_id, "work_order_service_id": line.id},
        )
        if line.discount_amount:
            audit_financial_event(
                event_type=AuditLog.Action.FINANCIAL_DISCOUNT,
                instance=line.work_order,
                user=self.request.user,
                request=self.request,
                description="Desconto aplicado em serviço da OS.",
                before={"discount_amount": "0.00"},
                after={"discount_amount": line.discount_amount},
                metadata={"work_order_id": line.work_order_id, "work_order_service_id": line.id},
            )

    def perform_update(self, serializer):
        instance = self.get_object()
        before = model_snapshot(instance, WORK_ORDER_SERVICE_AUDIT_FIELDS)
        old_discount = instance.discount_amount
        line = serializer.save()
        after = model_snapshot(line, WORK_ORDER_SERVICE_AUDIT_FIELDS)
        audit_financial_event(
            event_type=AuditLog.Action.FINANCIAL_UPDATE,
            instance=line.work_order,
            user=self.request.user,
            request=self.request,
            description="Serviço financeiro da OS atualizado.",
            before=before,
            after=after,
            metadata={"work_order_id": line.work_order_id, "work_order_service_id": line.id},
        )
        if old_discount != line.discount_amount:
            audit_financial_event(
                event_type=AuditLog.Action.FINANCIAL_DISCOUNT,
                instance=line.work_order,
                user=self.request.user,
                request=self.request,
                description="Desconto em serviço da OS alterado.",
                before={"discount_amount": old_discount},
                after={"discount_amount": line.discount_amount},
                metadata={"work_order_id": line.work_order_id, "work_order_service_id": line.id},
            )

    @action(detail=True, methods=["post"], url_path="start-execution")
    def start_execution(self, request, pk=None):
        serializer = StartWorkOrderServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            service_line = start_work_order_service(self.get_object(), actor=request.user, note=serializer.validated_data.get("note", ""))
        except DjangoValidationError as exc:
            raise drf_validation_from_django(exc) from exc
        return Response(WorkOrderServiceSerializer(service_line).data)

    @action(detail=True, methods=["post"], url_path="complete-execution")
    def complete_execution(self, request, pk=None):
        serializer = CompleteWorkOrderServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            service_line = complete_work_order_service(
                self.get_object(),
                actor=request.user,
                technical_diagnosis=serializer.validated_data.get("technical_diagnosis", ""),
                execution_notes=serializer.validated_data.get("execution_notes", ""),
                checklist=serializer.validated_data.get("checklist", {}),
                mark_order_quality_check=serializer.validated_data.get("mark_order_quality_check", True),
            )
        except DjangoValidationError as exc:
            raise drf_validation_from_django(exc) from exc
        return Response(WorkOrderServiceSerializer(service_line).data)

    @action(detail=True, methods=["post"], url_path="quality-check")
    def quality_check(self, request, pk=None):
        serializer = QualityCheckWorkOrderServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            service_line = quality_check_work_order_service(self.get_object(), actor=request.user, approved=serializer.validated_data.get("approved", True), notes=serializer.validated_data.get("notes", ""))
        except DjangoValidationError as exc:
            raise drf_validation_from_django(exc) from exc
        return Response(WorkOrderServiceSerializer(service_line).data)

class WorkOrderPartViewSet(viewsets.ModelViewSet):
    serializer_class = WorkOrderPartSerializer
    permission_classes = [HasViewPermission]
    permission_code_map = {"read": "work_order_parts.view", "write": "work_order_parts.manage"}
    queryset = WorkOrderPart.objects.select_related("work_order", "part", "stock_movement").all()

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("work_order"):
            qs = qs.filter(work_order_id=self.request.query_params["work_order"])
        return qs

    def perform_create(self, serializer):
        line = serializer.save()
        audit_financial_event(
            event_type=AuditLog.Action.FINANCIAL_UPDATE,
            instance=line.work_order,
            user=self.request.user,
            request=self.request,
            description="Peça financeira adicionada à OS.",
            before={},
            after=model_snapshot(line, WORK_ORDER_PART_AUDIT_FIELDS),
            metadata={"work_order_id": line.work_order_id, "work_order_part_id": line.id, "part_id": line.part_id},
        )
        if line.discount_amount:
            audit_financial_event(
                event_type=AuditLog.Action.FINANCIAL_DISCOUNT,
                instance=line.work_order,
                user=self.request.user,
                request=self.request,
                description="Desconto aplicado em peça da OS.",
                before={"discount_amount": "0.00"},
                after={"discount_amount": line.discount_amount},
                metadata={"work_order_id": line.work_order_id, "work_order_part_id": line.id, "part_id": line.part_id},
            )
        from purchasing.services import ensure_purchase_for_work_order_part

        ensure_purchase_for_work_order_part(line, actor=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        before = model_snapshot(instance, WORK_ORDER_PART_AUDIT_FIELDS)
        old_discount = instance.discount_amount
        line = serializer.save()
        audit_financial_event(
            event_type=AuditLog.Action.FINANCIAL_UPDATE,
            instance=line.work_order,
            user=self.request.user,
            request=self.request,
            description="Peça financeira da OS atualizada.",
            before=before,
            after=model_snapshot(line, WORK_ORDER_PART_AUDIT_FIELDS),
            metadata={"work_order_id": line.work_order_id, "work_order_part_id": line.id, "part_id": line.part_id},
        )
        if old_discount != line.discount_amount:
            audit_financial_event(
                event_type=AuditLog.Action.FINANCIAL_DISCOUNT,
                instance=line.work_order,
                user=self.request.user,
                request=self.request,
                description="Desconto em peça da OS alterado.",
                before={"discount_amount": old_discount},
                after={"discount_amount": line.discount_amount},
                metadata={"work_order_id": line.work_order_id, "work_order_part_id": line.id, "part_id": line.part_id},
            )
        from purchasing.services import ensure_purchase_for_work_order_part

        ensure_purchase_for_work_order_part(line, actor=self.request.user)

class WorkOrderPaymentViewSet(viewsets.ModelViewSet):
    serializer_class = WorkOrderPaymentSerializer
    permission_classes = [HasViewPermission]
    permission_code_map = {"read": "payments.view", "write": "payments.manage", "reverse": "payments.manage"}
    queryset = WorkOrderPayment.objects.select_related("work_order", "created_by", "reversed_by").all()

    def perform_create(self, serializer):
        work_order = serializer.validated_data["work_order"]
        before_order = model_snapshot(work_order, WORK_ORDER_AUDIT_FIELDS)
        payment = serializer.save(created_by=self.request.user)
        payment.work_order.refresh_from_db()
        ledger_entry = record_ledger_entry(
            entry_type=FinancialLedgerEntry.EntryType.CREDIT,
            origin=FinancialLedgerEntry.Origin.WORK_ORDER,
            origin_instance=payment,
            description=f"Recebimento direto da {payment.work_order.number}",
            amount=payment.amount,
            occurred_at=payment.paid_at,
            competence_date=payment.paid_at.date(),
            payment_method=payment.method,
            reference=payment.reference,
            notes=payment.notes,
            actor=self.request.user,
        )
        audit_financial_event(
            event_type=AuditLog.Action.FINANCIAL_PAYMENT,
            instance=payment,
            user=self.request.user,
            request=self.request,
            description=f"Pagamento direto da OS registrado: {payment.amount}.",
            before={},
            after=model_snapshot(payment, WORK_ORDER_PAYMENT_AUDIT_FIELDS),
            metadata={"work_order_id": payment.work_order_id, "work_order_number": payment.work_order.number, "ledger_entry_id": ledger_entry.id if ledger_entry else None},
        )
        audit_financial_event(
            event_type=AuditLog.Action.FINANCIAL_PAYMENT,
            instance=payment.work_order,
            user=self.request.user,
            request=self.request,
            description="Totais financeiros da OS atualizados por pagamento direto.",
            before=before_order,
            after=model_snapshot(payment.work_order, WORK_ORDER_AUDIT_FIELDS),
            metadata={"payment_id": payment.id, "ledger_entry_id": ledger_entry.id if ledger_entry else None},
        )
        record_event(payment.work_order, WorkOrderEvent.EventType.PAYMENT_ADDED, actor=self.request.user, description=f"Pagamento registrado: {payment.amount}.", data={"payment_id": payment.id, "method": payment.method, "amount": str(payment.amount), "ledger_entry_id": ledger_entry.id if ledger_entry else None})

    def perform_update(self, serializer):
        instance = self.get_object()
        before = model_snapshot(instance, WORK_ORDER_PAYMENT_AUDIT_FIELDS)
        payment = serializer.save()
        audit_financial_event(
            event_type=AuditLog.Action.FINANCIAL_UPDATE,
            instance=payment,
            user=self.request.user,
            request=self.request,
            description="Metadados do pagamento da OS atualizados.",
            before=before,
            after=model_snapshot(payment, WORK_ORDER_PAYMENT_AUDIT_FIELDS),
            metadata={"work_order_id": payment.work_order_id},
        )

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "Pagamentos não devem ser excluídos. Use a ação reverse com justificativa para preservar a rastreabilidade."}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse(self, request, pk=None):
        serializer = PaymentReversalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            from finance.services import reverse_work_order_payment

            payment, work_order = reverse_work_order_payment(self.get_object(), reason=serializer.validated_data["reason"], actor=request.user)
        except DjangoValidationError as exc:
            raise drf_validation_from_django(exc) from exc
        return Response({"payment": WorkOrderPaymentSerializer(payment).data, "work_order": WorkOrderDetailSerializer(work_order, context={"request": request}).data})

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("work_order"):
            qs = qs.filter(work_order_id=self.request.query_params["work_order"])
        return qs

class WorkOrderPhotoViewSet(viewsets.ModelViewSet):
    serializer_class = WorkOrderPhotoSerializer
    permission_classes = [HasViewPermission]
    permission_code_map = {"read": "work_orders.view", "write": ["work_orders.edit", "work_orders.create"]}
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    queryset = WorkOrderPhoto.objects.select_related("work_order", "uploaded_by").all()

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("work_order"):
            qs = qs.filter(work_order_id=self.request.query_params["work_order"])
        if self.request.query_params.get("photo_type"):
            qs = qs.filter(photo_type=self.request.query_params["photo_type"])
        return qs

    def perform_create(self, serializer):
        photo = serializer.save(uploaded_by=self.request.user)
        record_event(
            photo.work_order,
            WorkOrderEvent.EventType.PHOTO_ADDED,
            actor=self.request.user,
            description=f"Foto adicionada: {photo.get_photo_type_display()}.",
            data={"photo_id": photo.id, "photo_type": photo.photo_type, "caption": photo.caption, "sha256": photo.sha256},
        )

class WorkOrderEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WorkOrderEventSerializer
    permission_classes = [HasViewPermission]
    permission_code = "work_orders.view"
    queryset = WorkOrderEvent.objects.select_related("work_order", "actor").all()

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("work_order"):
            qs = qs.filter(work_order_id=self.request.query_params["work_order"])
        return qs

class WorkOrderMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WorkOrderMessageSerializer
    permission_classes = [HasViewPermission]
    permission_code = "work_orders.view"
    queryset = WorkOrderMessage.objects.select_related("work_order", "estimate", "template", "notification_rule", "message_log", "created_by").all()

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("work_order"):
            qs = qs.filter(work_order_id=self.request.query_params["work_order"])
        if self.request.query_params.get("estimate"):
            qs = qs.filter(estimate_id=self.request.query_params["estimate"])
        document_type = self.request.query_params.get("document_type") or self.request.query_params.get("entity_type")
        if document_type == WorkOrderNotificationRule.EntityType.WORK_ORDER:
            qs = qs.filter(work_order__isnull=False)
        elif document_type == WorkOrderNotificationRule.EntityType.ESTIMATE:
            qs = qs.filter(estimate__isnull=False)
        return qs

class WorkOrderNotificationRuleViewSet(viewsets.ModelViewSet):
    serializer_class = WorkOrderNotificationRuleSerializer
    permission_classes = [HasViewPermission]
    permission_code = "messaging.manage"
    queryset = WorkOrderNotificationRule.objects.select_related("template", "created_by").all()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("entity_type"):
            qs = qs.filter(entity_type=self.request.query_params["entity_type"])
        if self.request.query_params.get("trigger_status"):
            qs = qs.filter(trigger_status=self.request.query_params["trigger_status"])
        if self.request.query_params.get("channel"):
            qs = qs.filter(channel=self.request.query_params["channel"])
        active = self.request.query_params.get("active")
        search = self.request.query_params.get("search")
        if active in {"true", "false"}:
            qs = qs.filter(is_active=(active == "true"))
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(template__name__icontains=search))
        return qs

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except OperationalError as exc:
            message = str(exc)
            if "workshop_workordernotificationrule" in message or "workshop_workordermessage" in message:
                return Response(
                    {
                        "detail": "O banco de dados está desatualizado para as notificações de OS. Execute as migrações do backend: python manage.py migrate.",
                        "technical_detail": message,
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            raise
