
from .common import *
from .catalog import PartSerializer, WorkshopServiceSerializer
from .vehicles import VehicleSerializer



WORK_ORDER_DIRECT_EDIT_STATUSES = {WorkOrder.Status.OPEN, WorkOrder.Status.IN_PROGRESS, WorkOrder.Status.WAITING_PARTS}


def work_order_has_pending_approval(work_order):
    if not getattr(work_order, "pk", None):
        return False
    return work_order.customer_approvals.filter(
        status=WorkOrderCustomerApproval.Status.PENDING,
        is_active=True,
    ).exists()


def work_order_requires_revision_estimate(work_order):
    return bool(getattr(work_order, "approved_at", None))


def work_order_can_be_edited_directly(work_order):
    if not work_order:
        return True
    if work_order.status not in WORK_ORDER_DIRECT_EDIT_STATUSES:
        return False
    if work_order_has_pending_approval(work_order):
        return False
    if work_order_requires_revision_estimate(work_order):
        return False
    return True


def validate_work_order_direct_edit_allowed(work_order):
    if not work_order:
        return
    if work_order.status not in WORK_ORDER_DIRECT_EDIT_STATUSES:
        raise serializers.ValidationError({
            "status": "A OS só pode ser alterada quando estiver aberta, em execução ou aguardando peças."
        })
    if work_order_has_pending_approval(work_order):
        raise serializers.ValidationError({
            "status": "A OS está aguardando aprovação e não pode ser alterada. Aguarde a decisão do cliente ou cancele o link de aprovação."
        })
    if work_order_requires_revision_estimate(work_order):
        raise serializers.ValidationError({
            "status": "Esta OS já foi aprovada. Para alterar valores, serviços ou peças, gere um novo orçamento de revisão para aprovação do cliente."
        })

class WorkOrderServiceChecklistItemSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()
    completed_by_name = serializers.CharField(read_only=True)
    work_order_service_description = serializers.CharField(source="work_order_service.description", read_only=True)

    class Meta:
        model = WorkOrderServiceChecklistItem
        fields = [
            "id",
            "work_order",
            "work_order_service",
            "work_order_service_description",
            "source_template",
            "description",
            "is_required",
            "requires_photo",
            "requires_note",
            "sort_order",
            "is_completed",
            "completed_at",
            "completed_by",
            "completed_by_name",
            "note",
            "photo",
            "photo_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "work_order",
            "source_template",
            "completed_at",
            "completed_by",
            "completed_by_name",
            "photo_url",
            "created_at",
            "updated_at",
        ]

    def get_photo_url(self, obj):
        if not obj.photo:
            return ""
        return obj.photo.url

    def validate(self, attrs):
        is_completed = attrs.get("is_completed", getattr(self.instance, "is_completed", False))
        requires_note = attrs.get("requires_note", getattr(self.instance, "requires_note", False))
        requires_photo = attrs.get("requires_photo", getattr(self.instance, "requires_photo", False))
        note = attrs.get("note", getattr(self.instance, "note", ""))
        photo = attrs.get("photo", getattr(self.instance, "photo", None))
        if is_completed and requires_note and not (note or "").strip():
            raise serializers.ValidationError({"note": "Este item exige observação antes de ser concluído."})
        if is_completed and requires_photo and not photo:
            raise serializers.ValidationError({"photo": "Este item exige foto antes de ser concluído."})
        return attrs




class WorkOrderServiceSerializer(serializers.ModelSerializer):
    checklist_items = WorkOrderServiceChecklistItemSerializer(many=True, read_only=True)
    work_order_number = serializers.CharField(source="work_order.number", read_only=True)
    work_order_title = serializers.CharField(source="work_order.title", read_only=True)
    work_order_status = serializers.CharField(source="work_order.status", read_only=True)
    work_order_status_label = serializers.CharField(source="work_order.status_label", read_only=True)
    customer_name = serializers.CharField(source="work_order.customer.full_name", read_only=True)
    vehicle_display = serializers.CharField(source="work_order.vehicle.display_name", read_only=True)
    service_id = serializers.PrimaryKeyRelatedField(source="service", queryset=WorkshopService.objects.all(), required=False, allow_null=True, write_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    source_package_id = serializers.PrimaryKeyRelatedField(source="source_package", queryset=ServicePackage.objects.all(), required=False, allow_null=True, write_only=True)
    source_package_name = serializers.CharField(source="source_package.name", read_only=True)
    technician_id = serializers.PrimaryKeyRelatedField(source="technician", queryset=User.objects.all(), required=False, allow_null=True, write_only=True)
    technician_name = serializers.SerializerMethodField()
    subtotal_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    duration_label = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrderService
        fields = [
            "id",
            "work_order",
            "work_order_number",
            "work_order_title",
            "work_order_status",
            "work_order_status_label",
            "customer_name",
            "vehicle_display",
            "service",
            "service_id",
            "service_name",
            "source_package",
            "source_package_id",
            "source_package_name",
            "description",
            "quantity",
            "unit_price",
            "discount_amount",
            "technician",
            "technician_id",
            "technician_name",
            "status",
            "notes",
            "technical_diagnosis",
            "execution_notes",
            "checklist",
            "checklist_items",
            "started_at",
            "finished_at",
            "expected_minutes",
            "actual_minutes",
            "duration_label",
            "needs_quality_check",
            "quality_checked_at",
            "quality_check_notes",
            "quality_checked_by",
            "subtotal_amount",
            "total_amount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "service",
            "source_package",
            "technician",
            "work_order_number",
            "work_order_title",
            "work_order_status",
            "work_order_status_label",
            "customer_name",
            "vehicle_display",
            "service_name",
            "source_package_name",
            "technician_name",
            "started_at",
            "finished_at",
            "actual_minutes",
            "duration_label",
            "checklist_items",
            "quality_checked_at",
            "quality_checked_by",
            "subtotal_amount",
            "total_amount",
            "created_at",
            "updated_at",
        ]

    def get_technician_name(self, obj):
        return obj.technician.get_full_name() or obj.technician.username if obj.technician else ""

    def get_duration_label(self, obj):
        minutes = obj.actual_minutes or 0
        if not minutes and obj.started_at and not obj.finished_at:
            from django.utils import timezone

            minutes = max(int((timezone.now() - obj.started_at).total_seconds() // 60), 0)
        if not minutes:
            return ""
        hours, remaining = divmod(minutes, 60)
        return f"{hours}h {remaining:02d}min" if hours else f"{remaining}min"

    def validate(self, attrs):
        work_order = attrs.get("work_order", getattr(self.instance, "work_order", None))
        validate_work_order_direct_edit_allowed(work_order)
        service = attrs.get("service")
        if service:
            attrs.setdefault("description", service.name)
            attrs.setdefault("unit_price", service.default_unit_price)
        if not attrs.get("description") and not getattr(self.instance, "description", ""):
            raise serializers.ValidationError({"description": "Informe a descricao do servico."})
        checklist = attrs.get("checklist")
        if checklist is not None and not isinstance(checklist, dict):
            raise serializers.ValidationError({"checklist": "O checklist tecnico deve ser um objeto JSON."})
        quantity = attrs.get("quantity", getattr(self.instance, "quantity", Decimal("1.00")))
        unit_price = attrs.get("unit_price", getattr(self.instance, "unit_price", Decimal("0.00")))
        discount_amount = attrs.get("discount_amount", getattr(self.instance, "discount_amount", Decimal("0.00")))
        if discount_amount and discount_amount > (quantity or ZERO) * (unit_price or ZERO):
            raise serializers.ValidationError({"discount_amount": "Desconto do serviço não pode ser maior que o subtotal da linha."})
        return attrs




class StartWorkOrderServiceSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True)




class CompleteWorkOrderServiceSerializer(serializers.Serializer):
    technical_diagnosis = serializers.CharField(required=False, allow_blank=True)
    execution_notes = serializers.CharField(required=True, allow_blank=False)
    checklist = serializers.JSONField(required=False)
    mark_order_quality_check = serializers.BooleanField(default=True)

    def validate_checklist(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Informe o checklist como objeto JSON.")
        return value




class QualityCheckWorkOrderServiceSerializer(serializers.Serializer):
    approved = serializers.BooleanField(default=True)
    notes = serializers.CharField(required=False, allow_blank=True)




class WorkOrderPartSerializer(serializers.ModelSerializer):
    work_order_number = serializers.CharField(source="work_order.number", read_only=True)
    part_id = serializers.PrimaryKeyRelatedField(source="part", queryset=Part.objects.all(), required=False, allow_null=True, write_only=True)
    linked_service_id = serializers.PrimaryKeyRelatedField(source="linked_service", queryset=WorkOrderService.objects.all(), required=False, allow_null=True, write_only=True)
    linked_service_description = serializers.CharField(source="linked_service.description", read_only=True)
    part_name = serializers.CharField(source="part.name", read_only=True)
    part_sku = serializers.CharField(source="part.sku", read_only=True)
    subtotal_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    stock_consumed = serializers.SerializerMethodField()
    stock_reservation_status_label = serializers.CharField(source="get_stock_reservation_status_display", read_only=True)

    class Meta:
        model = WorkOrderPart
        fields = ["id", "work_order", "work_order_number", "part", "part_id", "linked_service", "linked_service_id", "linked_service_description", "part_name", "part_sku", "description", "quantity", "unit_price", "cost_price", "discount_amount", "consume_inventory", "stock_reserved_at", "stock_reserved_quantity", "stock_shortage_quantity", "stock_reservation_status", "stock_reservation_status_label", "stock_reservation_notes", "stock_reservation_movement", "stock_consumed_at", "stock_consumed", "stock_movement", "notes", "subtotal_amount", "total_amount", "created_at", "updated_at"]
        read_only_fields = ["id", "part", "linked_service", "linked_service_description", "work_order_number", "part_name", "part_sku", "stock_reserved_at", "stock_reserved_quantity", "stock_shortage_quantity", "stock_reservation_status", "stock_reservation_status_label", "stock_reservation_notes", "stock_reservation_movement", "stock_consumed_at", "stock_consumed", "stock_movement", "subtotal_amount", "total_amount", "created_at", "updated_at"]

    def get_stock_consumed(self, obj):
        return bool(obj.stock_consumed_at)

    def validate(self, attrs):
        work_order = attrs.get("work_order", getattr(self.instance, "work_order", None))
        validate_work_order_direct_edit_allowed(work_order)
        part = attrs.get("part")
        if part:
            attrs.setdefault("description", part.name)
            attrs.setdefault("unit_price", part.sale_price)
            attrs.setdefault("cost_price", part.cost_price)
        if not attrs.get("description") and not getattr(self.instance, "description", ""):
            raise serializers.ValidationError({"description": "Informe a descricao da peca."})
        quantity = attrs.get("quantity", getattr(self.instance, "quantity", Decimal("1.00")))
        unit_price = attrs.get("unit_price", getattr(self.instance, "unit_price", Decimal("0.00")))
        discount_amount = attrs.get("discount_amount", getattr(self.instance, "discount_amount", Decimal("0.00")))
        if discount_amount and discount_amount > (quantity or ZERO) * (unit_price or ZERO):
            raise serializers.ValidationError({"discount_amount": "Desconto da peça não pode ser maior que o subtotal da linha."})
        return attrs




class WorkOrderPaymentSerializer(serializers.ModelSerializer):
    work_order_number = serializers.CharField(source="work_order.number", read_only=True)
    method_label = serializers.CharField(source="get_method_display", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrderPayment
        fields = ["id", "work_order", "work_order_number", "method", "method_label", "amount", "paid_at", "reference", "notes", "created_by_name", "reversed_at", "reversed_by", "reversal_reason", "is_reversed", "created_at", "updated_at"]
        read_only_fields = ["id", "work_order_number", "method_label", "created_by_name", "reversed_at", "reversed_by", "reversal_reason", "is_reversed", "created_at", "updated_at"]

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() or obj.created_by.username if obj.created_by else ""

    def validate(self, attrs):
        if self.instance:
            blocked = {"work_order", "method", "amount", "paid_at"} & set(attrs.keys())
            if blocked:
                raise serializers.ValidationError("Pagamento financeiro não deve ser editado em valor, método, data ou origem. Faça o estorno e registre um novo pagamento.")
            if self.instance.is_reversed:
                raise serializers.ValidationError("Pagamento estornado não pode ser alterado.")
            return attrs
        work_order = attrs.get("work_order") or getattr(self.instance, "work_order", None)
        amount = attrs.get("amount", getattr(self.instance, "amount", None))
        if work_order and amount is not None:
            work_order.recalculate_totals(save=True)
            current_amount = getattr(self.instance, "amount", ZERO) if self.instance and getattr(self.instance, "work_order_id", None) == work_order.id else ZERO
            available_balance = (work_order.balance_due or ZERO) + (current_amount or ZERO)
            if amount > available_balance:
                raise serializers.ValidationError({"amount": "O valor pago não pode ser maior que o saldo em aberto da OS."})
        return attrs


class PaymentReversalSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=5, max_length=500, trim_whitespace=True)

class WorkOrderPhotoSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    photo_type_label = serializers.CharField(source="get_photo_type_display", read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrderPhoto
        fields = [
            "id",
            "work_order",
            "image",
            "image_url",
            "photo_type",
            "photo_type_label",
            "caption",
            "taken_at",
            "uploaded_by_name",
            "original_filename",
            "content_type",
            "file_size",
            "sha256",
            "is_customer_visible",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "image_url", "photo_type_label", "uploaded_by_name", "original_filename", "content_type", "file_size", "sha256", "created_at", "updated_at"]

    def get_image_url(self, obj):
        if not obj.image:
            return ""
        return obj.image.url

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.get_full_name() or obj.uploaded_by.username if obj.uploaded_by else ""

    def validate_image(self, value):
        if value and value.size > 8 * 1024 * 1024:
            raise serializers.ValidationError("A foto da OS deve ter no máximo 8 MB.")
        return value

    def validate_caption(self, value):
        return (value or "").strip()




class WorkOrderEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrderEvent
        fields = ["id", "work_order", "event_type", "old_status", "new_status", "description", "data", "actor_name", "created_at"]
        read_only_fields = fields

    def get_actor_name(self, obj):
        return obj.actor.get_full_name() or obj.actor.username if obj.actor else ""




class WorkOrderMessageSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    message_log_status = serializers.CharField(source="message_log.status", read_only=True)
    message_log_detail = MessageLogSerializer(source="message_log", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    document_type = serializers.CharField(read_only=True)
    document_number = serializers.CharField(read_only=True)

    class Meta:
        model = WorkOrderMessage
        fields = ["id", "work_order", "estimate", "document_type", "document_number", "trigger_type", "trigger_status", "channel", "recipient_target", "template", "template_name", "notification_rule", "message_log", "message_log_status", "message_log_detail", "status", "error_message", "created_by_name", "created_at"]
        read_only_fields = fields

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() or obj.created_by.username if obj.created_by else ""

    def validate(self, attrs):
        if self.instance:
            blocked = {"work_order", "method", "amount", "paid_at"} & set(attrs.keys())
            if blocked:
                raise serializers.ValidationError("Pagamento financeiro não deve ser editado em valor, método, data ou origem. Faça o estorno e registre um novo pagamento.")
            if self.instance.is_reversed:
                raise serializers.ValidationError("Pagamento estornado não pode ser alterado.")
            return attrs
        work_order = attrs.get("work_order") or getattr(self.instance, "work_order", None)
        amount = attrs.get("amount", getattr(self.instance, "amount", None))
        if work_order and amount is not None:
            work_order.recalculate_totals(save=True)
            current_amount = getattr(self.instance, "amount", ZERO) if self.instance and getattr(self.instance, "work_order_id", None) == work_order.id else ZERO
            available_balance = (work_order.balance_due or ZERO) + (current_amount or ZERO)
            if amount > available_balance:
                raise serializers.ValidationError({"amount": "O valor pago não pode ser maior que o saldo em aberto da OS."})
        return attrs




class WorkOrderNotificationRuleSerializer(serializers.ModelSerializer):
    template_id = serializers.PrimaryKeyRelatedField(source="template", queryset=MessageTemplate.objects.all(), write_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True)
    entity_type_label = serializers.CharField(read_only=True)
    trigger_status_label = serializers.CharField(read_only=True)

    class Meta:
        model = WorkOrderNotificationRule
        fields = ["id", "name", "entity_type", "entity_type_label", "trigger_status", "trigger_status_label", "channel", "template", "template_id", "template_name", "recipient_target", "is_active", "send_once_per_status", "created_at", "updated_at"]
        read_only_fields = ["id", "template", "template_name", "entity_type_label", "trigger_status_label", "created_at", "updated_at"]

    def validate(self, attrs):
        template = attrs.get("template", getattr(self.instance, "template", None))
        channel = attrs.get("channel", getattr(self.instance, "channel", None))
        entity_type = attrs.get("entity_type", getattr(self.instance, "entity_type", WorkOrderNotificationRule.EntityType.WORK_ORDER))
        trigger_status = attrs.get("trigger_status", getattr(self.instance, "trigger_status", ""))
        if template and channel and template.channel != channel:
            raise serializers.ValidationError({"channel": "O canal da regra precisa ser igual ao canal do template."})
        if entity_type == WorkOrderNotificationRule.EntityType.WORK_ORDER:
            valid_statuses = {value for value, _label in WorkOrder.Status.choices}
            if trigger_status not in valid_statuses:
                raise serializers.ValidationError({"trigger_status": "Status gatilho inválido para ordem de serviço."})
        elif entity_type == WorkOrderNotificationRule.EntityType.ESTIMATE:
            valid_statuses = {"open", "diagnosis", "awaiting_approval", "approved", "partially_approved", "rejected", "expired", "converted", "cancelled"}
            if trigger_status not in valid_statuses:
                raise serializers.ValidationError({"trigger_status": "Status gatilho inválido para orçamento."})
        return attrs






class InitialWorkOrderServiceItemSerializer(serializers.Serializer):
    service_id = serializers.PrimaryKeyRelatedField(source="service", queryset=WorkshopService.objects.filter(is_active=True), required=False, allow_null=True)
    source_package_id = serializers.PrimaryKeyRelatedField(source="source_package", queryset=ServicePackage.objects.filter(is_active=True), required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, max_length=220)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"), default=Decimal("1.00"))
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.00"), default=Decimal("0.00"))
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.00"), default=Decimal("0.00"))
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        work_order = attrs.get("work_order", getattr(self.instance, "work_order", None))
        validate_work_order_direct_edit_allowed(work_order)
        service = attrs.get("service")
        if service:
            attrs.setdefault("description", service.name)
            attrs.setdefault("unit_price", service.default_unit_price)
        if not attrs.get("description"):
            raise serializers.ValidationError({"description": "Informe a descricao do servico inicial."})
        subtotal = (attrs.get("quantity") or ZERO) * (attrs.get("unit_price") or ZERO)
        if attrs.get("discount_amount") and attrs["discount_amount"] > subtotal:
            raise serializers.ValidationError({"discount_amount": "Desconto do serviço inicial não pode ser maior que o subtotal."})
        return attrs




class CancelWorkOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=5, max_length=1000, trim_whitespace=True)
    send_notifications = serializers.BooleanField(default=True)


class WorkOrderSerializer(serializers.ModelSerializer):
    customer_id = serializers.PrimaryKeyRelatedField(source="customer", queryset=Contact.objects.all(), write_only=True)
    vehicle_id = serializers.PrimaryKeyRelatedField(source="vehicle", queryset=Vehicle.objects.all(), required=False, allow_null=True, write_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(source="assigned_to", queryset=User.objects.all(), required=False, allow_null=True, write_only=True)
    reference_work_order_id = serializers.PrimaryKeyRelatedField(source="reference_work_order", queryset=WorkOrder.objects.all(), required=False, allow_null=True, write_only=True)
    customer = ContactSerializer(read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    vehicle = VehicleSerializer(read_only=True)
    vehicle_display = serializers.CharField(source="vehicle.display_name", read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    reference_work_order = serializers.PrimaryKeyRelatedField(read_only=True)
    reference_work_order_number = serializers.CharField(source="reference_work_order.number", read_only=True)
    status_label = serializers.CharField(read_only=True)
    priority_label = serializers.CharField(read_only=True)
    order_type_label = serializers.CharField(read_only=True)
    initial_service_items = InitialWorkOrderServiceItemSerializer(many=True, write_only=True, required=False)
    account_receivable_summary = serializers.SerializerMethodField()
    purchase_orders_summary = serializers.SerializerMethodField()
    available_status_transitions = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    has_pending_approval = serializers.SerializerMethodField()
    requires_revision_estimate = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrder
        fields = ["id", "number", "customer", "customer_id", "customer_name", "vehicle", "vehicle_id", "vehicle_display", "title", "complaint", "diagnosis", "solution", "internal_notes", "customer_notes", "status", "status_label", "priority", "priority_label", "order_type", "order_type_label", "reference_work_order", "reference_work_order_id", "reference_work_order_number", "mileage_in", "mileage_out", "promised_at", "opened_at", "approved_at", "started_at", "completed_at", "delivered_at", "cancelled_at", "cancelled_by", "cancellation_reason", "assigned_to", "assigned_to_id", "assigned_to_name", "subtotal_services", "subtotal_parts", "manual_discount_amount", "discount_total", "grand_total", "paid_total", "balance_due", "inventory_consumed_at", "account_receivable_summary", "purchase_orders_summary", "available_status_transitions", "can_edit", "has_pending_approval", "requires_revision_estimate", "created_at", "updated_at", "initial_service_items"]
        read_only_fields = ["id", "number", "customer", "customer_name", "vehicle", "vehicle_display", "assigned_to", "assigned_to_name", "reference_work_order", "reference_work_order_number", "status", "status_label", "priority_label", "order_type_label", "opened_at", "approved_at", "started_at", "completed_at", "delivered_at", "cancelled_at", "cancelled_by", "cancellation_reason", "subtotal_services", "subtotal_parts", "discount_total", "grand_total", "paid_total", "balance_due", "inventory_consumed_at", "account_receivable_summary", "purchase_orders_summary", "available_status_transitions", "can_edit", "has_pending_approval", "requires_revision_estimate", "created_at", "updated_at"]

    def get_assigned_to_name(self, obj):
        return obj.assigned_to.get_full_name() or obj.assigned_to.username if obj.assigned_to else ""


    def get_purchase_orders_summary(self, obj):
        orders = getattr(obj, "purchase_orders", None)
        if orders is None:
            return []
        return [
            {
                "id": order.id,
                "number": order.number,
                "status": order.status,
                "status_label": order.status_label,
                "origin": order.origin,
                "origin_label": order.origin_label,
                "total_amount": order.total_amount,
                "items_count": order.items.count(),
            }
            for order in orders.all().order_by("-created_at")[:10]
        ]

    def get_account_receivable_summary(self, obj):
        receivable = getattr(obj, "account_receivable", None)
        if not receivable:
            return None
        return {
            "id": receivable.id,
            "number": receivable.number,
            "status": receivable.status,
            "status_label": receivable.status_label,
            "amount": receivable.amount,
            "paid_amount": receivable.paid_amount,
            "balance_amount": receivable.balance_amount,
            "due_date": receivable.due_date,
        }

    def get_available_status_transitions(self, obj):
        request = self.context.get("request")
        actor = getattr(request, "user", None) if request else None
        return available_status_transitions(obj, actor=actor)

    def get_can_edit(self, obj):
        return work_order_can_be_edited_directly(obj)

    def get_has_pending_approval(self, obj):
        return work_order_has_pending_approval(obj)

    def get_requires_revision_estimate(self, obj):
        return work_order_requires_revision_estimate(obj)

    def _create_initial_service_items(self, work_order, items):
        for item in items:
            WorkOrderService.objects.create(work_order=work_order, status=WorkOrderService.Status.PENDING, **item)
        work_order.recalculate_totals()

    def create(self, validated_data):
        initial_service_items = validated_data.pop("initial_service_items", [])
        work_order = WorkOrder.objects.create(**validated_data)
        if initial_service_items:
            self._create_initial_service_items(work_order, initial_service_items)
        else:
            work_order.recalculate_totals()
        return work_order

    def update(self, instance, validated_data):
        validated_data.pop("initial_service_items", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        instance.recalculate_totals()
        return instance

    def validate(self, attrs):
        if self.instance is not None:
            validate_work_order_direct_edit_allowed(self.instance)
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        vehicle = attrs.get("vehicle", getattr(self.instance, "vehicle", None))
        order_type = attrs.get("order_type", getattr(self.instance, "order_type", WorkOrder.OrderType.STANDARD))
        reference_work_order = attrs.get("reference_work_order", getattr(self.instance, "reference_work_order", None))
        if vehicle and customer and vehicle.customer_id != customer.id:
            raise serializers.ValidationError({"vehicle_id": "O veiculo informado pertence a outro cliente."})
        if self.instance is None and customer:
            from attendance.models import Estimate
            has_active_estimate = Estimate.objects.filter(
                customer=customer,
                status__in=[Estimate.Status.OPEN, Estimate.Status.DIAGNOSIS, Estimate.Status.AWAITING_APPROVAL],
            ).exists()
            if has_active_estimate:
                raise serializers.ValidationError({
                    "customer_id": "Este cliente já possui orçamento em andamento (aberto, em diagnóstico ou aguardando aprovação). Converta ou finalize o orçamento antes de abrir uma OS avulsa."
                })
        if order_type == WorkOrder.OrderType.WARRANTY and not reference_work_order:
            raise serializers.ValidationError({"reference_work_order_id": "Informe a OS de referencia quando o tipo for garantia."})
        if reference_work_order:
            if self.instance and reference_work_order.id == self.instance.id:
                raise serializers.ValidationError({"reference_work_order_id": "A OS de referencia nao pode ser a propria OS."})
            if customer and reference_work_order.customer_id != customer.id:
                raise serializers.ValidationError({"reference_work_order_id": "A OS de referencia precisa pertencer ao mesmo cliente."})
            if vehicle and reference_work_order.vehicle_id and reference_work_order.vehicle_id != vehicle.id:
                raise serializers.ValidationError({"reference_work_order_id": "A OS de referencia precisa pertencer ao mesmo veiculo."})
        manual_discount = attrs.get("manual_discount_amount", getattr(self.instance, "manual_discount_amount", ZERO))
        if manual_discount and self.instance:
            current_line_discount = sum((line.discount_amount or ZERO for line in self.instance.services.all()), ZERO) + sum((line.discount_amount or ZERO for line in self.instance.parts.all()), ZERO)
            subtotal = (self.instance.subtotal_services or ZERO) + (self.instance.subtotal_parts or ZERO)
            if manual_discount + current_line_discount > subtotal:
                raise serializers.ValidationError({"manual_discount_amount": "Desconto total da OS não pode ser maior que o subtotal."})
        return attrs




class WorkOrderListSerializer(WorkOrderSerializer):
    class Meta(WorkOrderSerializer.Meta):
        fields = ["id", "number", "customer_name", "vehicle_display", "title", "status", "status_label", "priority", "priority_label", "promised_at", "assigned_to_name", "grand_total", "paid_total", "balance_due", "available_status_transitions", "can_edit", "has_pending_approval", "requires_revision_estimate", "approved_at", "cancelled_at", "cancellation_reason", "created_at", "updated_at"]
        read_only_fields = fields




class WorkOrderDetailSerializer(WorkOrderSerializer):
    services = WorkOrderServiceSerializer(many=True, read_only=True)
    parts = WorkOrderPartSerializer(many=True, read_only=True)
    payments = WorkOrderPaymentSerializer(many=True, read_only=True)
    photos = WorkOrderPhotoSerializer(many=True, read_only=True)
    events = WorkOrderEventSerializer(many=True, read_only=True)
    messages = WorkOrderMessageSerializer(many=True, read_only=True)

    class Meta(WorkOrderSerializer.Meta):
        fields = WorkOrderSerializer.Meta.fields + ["services", "parts", "payments", "photos", "events", "messages"]
        read_only_fields = WorkOrderSerializer.Meta.read_only_fields + ["services", "parts", "payments", "photos", "events", "messages"]




class WorkOrderDeliverySignatureSerializer(serializers.ModelSerializer):
    signature_url = serializers.SerializerMethodField()
    signed_by_name = serializers.CharField(read_only=True)

    class Meta:
        model = WorkOrderDeliverySignature
        fields = [
            "id",
            "work_order",
            "recipient_name",
            "recipient_document",
            "notes",
            "signature_image",
            "signature_url",
            "signed_at",
            "signed_ip",
            "signed_user_agent",
            "signed_by_user",
            "signed_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "work_order", "signature_url", "signed_at", "signed_ip", "signed_user_agent", "signed_by_user", "signed_by_name", "created_at", "updated_at"]

    def get_signature_url(self, obj):
        if not obj.signature_image:
            return ""
        return obj.signature_image.url




class WorkOrderDeliverySignatureCreateSerializer(serializers.Serializer):
    recipient_name = serializers.CharField(max_length=180)
    recipient_document = serializers.CharField(max_length=30, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    signature_data_url = serializers.CharField(write_only=True)

    def validate_recipient_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Informe o nome de quem recebeu.")
        return value

    def validate_signature_data_url(self, value):
        if not value or "," not in value:
            raise serializers.ValidationError("Informe a assinatura digital desenhada na tela.")
        header, data = value.split(",", 1)
        if "image/png" not in header and "image/jpeg" not in header and "image/webp" not in header:
            raise serializers.ValidationError("A assinatura precisa ser uma imagem PNG, JPEG ou WEBP.")
        try:
            decoded = base64.b64decode(data)
        except (binascii.Error, ValueError) as exc:
            raise serializers.ValidationError("Assinatura digital inválida.") from exc
        if len(decoded) > 2 * 1024 * 1024:
            raise serializers.ValidationError("A assinatura deve ter no máximo 2 MB.")
        extension = "jpg" if "image/jpeg" in header else "webp" if "image/webp" in header else "png"
        return ContentFile(decoded, name=f"assinatura-{uuid4().hex}.{extension}")




class WorkOrderCustomerApprovalSerializer(serializers.ModelSerializer):
    work_order_number = serializers.CharField(source="work_order.number", read_only=True)
    document_type_label = serializers.CharField(read_only=True)
    status_label = serializers.CharField(read_only=True)
    effective_status = serializers.CharField(read_only=True)
    can_decide = serializers.BooleanField(read_only=True)
    public_url_path = serializers.CharField(read_only=True)
    requested_by_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrderCustomerApproval
        fields = [
            "id",
            "work_order",
            "work_order_number",
            "document_type",
            "document_type_label",
            "token",
            "status",
            "status_label",
            "effective_status",
            "can_decide",
            "public_url_path",
            "requested_by_name",
            "requested_at",
            "expires_at",
            "customer_name_snapshot",
            "customer_email_snapshot",
            "customer_phone_snapshot",
            "decision_name",
            "decision_document",
            "decision_notes",
            "decided_at",
            "decision_ip",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_requested_by_name(self, obj):
        return obj.requested_by.get_full_name() or obj.requested_by.username if obj.requested_by else ""




class WorkOrderCustomerApprovalCreateSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=WorkOrderCustomerApproval.DocumentType.choices, default=WorkOrderCustomerApproval.DocumentType.ESTIMATE)
    expires_days = serializers.IntegerField(required=False, min_value=1, max_value=90, default=7)




class WorkOrderManualApprovalSerializer(serializers.Serializer):
    approval_type = serializers.ChoiceField(choices=[("total", "Total"), ("partial", "Parcial")], default="total")
    notes = serializers.CharField(required=True, allow_blank=False)
    signature_name = serializers.CharField(required=False, allow_blank=True, max_length=180)
    signature_document = serializers.CharField(required=False, allow_blank=True, max_length=30)

    def validate_notes(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Informe uma observação para registrar a aprovação manual.")
        return value

    def validate_signature_document(self, value):
        value = (value or "").strip()
        if not value:
            return value
        digits = only_digits(value)
        if len(digits) not in (11, 14):
            raise serializers.ValidationError("Informe um CPF com 11 dígitos ou CNPJ com 14 dígitos.")
        return format_cpf_cnpj(digits)


class WorkOrderCustomerApprovalDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=[("approved", "Aprovar"), ("rejected", "Recusar")])
    name = serializers.CharField(required=False, allow_blank=True, max_length=180)
    document = serializers.CharField(required=True, allow_blank=False, max_length=30)
    notes = serializers.CharField(required=True, allow_blank=False)

    def validate_document(self, value):
        digits = only_digits(value)
        if len(digits) not in (11, 14):
            raise serializers.ValidationError("Informe um CPF com 11 dígitos ou CNPJ com 14 dígitos.")
        return format_cpf_cnpj(digits)

    def validate_notes(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Informe uma observação para registrar a decisão.")
        return value

    def validate_name(self, value):
        return (value or "").strip()




class WorkOrderCustomerApprovalPublicSerializer(serializers.ModelSerializer):
    document_type_label = serializers.CharField(read_only=True)
    status_label = serializers.CharField(read_only=True)
    effective_status = serializers.CharField(read_only=True)
    can_decide = serializers.BooleanField(read_only=True)
    work_order = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()
    parts = serializers.SerializerMethodField()
    totals = serializers.SerializerMethodField()
    workshop = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrderCustomerApproval
        fields = [
            "token",
            "document_type",
            "document_type_label",
            "status",
            "status_label",
            "effective_status",
            "can_decide",
            "requested_at",
            "expires_at",
            "customer_name_snapshot",
            "decision_name",
            "decision_document",
            "decision_notes",
            "decided_at",
            "workshop",
            "work_order",
            "services",
            "parts",
            "totals",
        ]
        read_only_fields = fields

    def get_workshop(self, obj):
        profile = WorkshopProfile.get_solo()
        return {
            "display_name": profile.display_name,
            "legal_name": profile.legal_name,
            "document_number": profile.document_number,
            "phone": profile.phone_e164,
            "email": profile.email,
            "address": profile.address_display,
            "logo_url": profile.logo.url if profile.logo else "",
        }

    def get_work_order(self, obj):
        order = obj.work_order
        return {
            "id": order.id,
            "number": order.number,
            "title": order.title,
            "status": order.status,
            "status_label": order.status_label,
            "priority_label": order.priority_label,
            "customer_name": order.customer.full_name,
            "vehicle_display": order.vehicle.display_name if order.vehicle else "",
            "mileage_in": order.mileage_in,
            "complaint": order.complaint,
            "diagnosis": order.diagnosis,
            "solution": order.solution,
            "customer_notes": order.customer_notes,
            "opened_at": order.opened_at,
            "promised_at": order.promised_at,
        }

    def get_services(self, obj):
        return [
            {
                "description": line.description,
                "quantity": line.quantity,
                "unit_price": line.unit_price,
                "discount_amount": line.discount_amount,
                "total_amount": line.total_amount,
            }
            for line in obj.work_order.services.all()
        ]

    def get_parts(self, obj):
        return [
            {
                "sku": line.part.sku if line.part else "",
                "description": line.description,
                "quantity": line.quantity,
                "unit_price": line.unit_price,
                "discount_amount": line.discount_amount,
                "total_amount": line.total_amount,
            }
            for line in obj.work_order.parts.all()
        ]

    def get_totals(self, obj):
        order = obj.work_order
        return {
            "subtotal_services": order.subtotal_services,
            "subtotal_parts": order.subtotal_parts,
            "discount_total": order.discount_total,
            "grand_total": order.grand_total,
            "paid_total": order.paid_total,
            "balance_due": order.balance_due,
        }




class ChangeWorkOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=WorkOrder.Status.choices)
    note = serializers.CharField(required=False, allow_blank=True)
    send_notifications = serializers.BooleanField(default=True)




class SendWorkOrderMessageSerializer(serializers.Serializer):
    template_id = serializers.PrimaryKeyRelatedField(source="template", queryset=MessageTemplate.objects.filter(is_active=True))
