from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from messaging.models import Contact
from messaging.serializers import ContactSerializer
from workshop.models import Part, ServicePackage, Vehicle, WorkshopProfile, WorkshopService
from workshop.serializers import PartSerializer, VehicleSerializer, WorkOrderDetailSerializer

from .models import CounterSale, CounterSaleItem, CounterSalePayment, Estimate, EstimateCustomerApproval, EstimatePartItem, EstimateServiceItem, EstimateStatusHistory
from .services import ESTIMATE_EDITABLE_STATUSES, cancel_counter_sale, cancel_estimate, change_estimate_status, convert_estimate_to_work_order, decide_estimate_approval, finalize_counter_sale, manually_approve_estimate, register_counter_sale_payment

User = get_user_model()


class CounterSaleItemSerializer(serializers.ModelSerializer):
    part_id = serializers.PrimaryKeyRelatedField(source="part", queryset=Part.objects.filter(is_active=True), required=False, allow_null=True, write_only=True)
    part_name = serializers.CharField(source="part.name", read_only=True)
    part_sku = serializers.CharField(source="part.sku", read_only=True)
    stock_available = serializers.DecimalField(source="part.stock_quantity", max_digits=12, decimal_places=2, read_only=True)
    subtotal_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CounterSaleItem
        fields = [
            "id",
            "counter_sale",
            "part",
            "part_id",
            "part_name",
            "part_sku",
            "stock_available",
            "description",
            "quantity",
            "unit_price",
            "cost_price",
            "discount_amount",
            "stock_movement",
            "notes",
            "subtotal_amount",
            "total_amount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "counter_sale", "part", "part_name", "part_sku", "stock_available", "stock_movement", "subtotal_amount", "total_amount", "created_at", "updated_at"]

    def validate(self, attrs):
        part = attrs.get("part")
        if part:
            attrs.setdefault("description", part.name)
            attrs.setdefault("unit_price", part.sale_price)
            attrs.setdefault("cost_price", part.cost_price)
        if not attrs.get("description") and not getattr(self.instance, "description", ""):
            raise serializers.ValidationError({"description": "Informe a descrição da peça vendida."})
        quantity = attrs.get("quantity", getattr(self.instance, "quantity", Decimal("1.00")))
        if quantity <= Decimal("0.00"):
            raise serializers.ValidationError({"quantity": "Quantidade precisa ser maior que zero."})
        return attrs


class CounterSalePaymentSerializer(serializers.ModelSerializer):
    method_label = serializers.CharField(read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CounterSalePayment
        fields = ["id", "counter_sale", "method", "method_label", "amount", "paid_at", "reference", "notes", "created_by_name", "created_at", "updated_at"]
        read_only_fields = ["id", "counter_sale", "method_label", "created_by_name", "created_at", "updated_at"]

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() or obj.created_by.username if obj.created_by else ""


class CounterSaleSerializer(serializers.ModelSerializer):
    customer_id = serializers.PrimaryKeyRelatedField(source="customer", queryset=Contact.objects.filter(is_active=True), required=False, allow_null=True, write_only=True)
    customer = ContactSerializer(read_only=True)
    customer_display_name = serializers.CharField(source="effective_customer_name", read_only=True)
    status_label = serializers.CharField(read_only=True)
    items = CounterSaleItemSerializer(many=True, required=False)
    payments = CounterSalePaymentSerializer(many=True, read_only=True)
    account_receivable_summary = serializers.SerializerMethodField()

    class Meta:
        model = CounterSale
        fields = [
            "id",
            "number",
            "customer",
            "customer_id",
            "customer_name",
            "customer_display_name",
            "status",
            "status_label",
            "sold_at",
            "due_date",
            "subtotal_amount",
            "discount_amount",
            "total_amount",
            "paid_amount",
            "balance_amount",
            "notes",
            "items",
            "payments",
            "account_receivable_summary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "number", "customer", "customer_display_name", "status", "status_label", "sold_at", "subtotal_amount", "total_amount", "paid_amount", "balance_amount", "payments", "account_receivable_summary", "created_at", "updated_at"]

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

    def get_can_edit(self, obj):
        return obj.status in ESTIMATE_EDITABLE_STATUSES

    def validate(self, attrs):
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        customer_name = attrs.get("customer_name", getattr(self.instance, "customer_name", ""))
        if not customer and not (customer_name or "").strip():
            attrs["customer_name"] = "Cliente balcão"
        if self.instance and self.instance.status != CounterSale.Status.DRAFT:
            blocked = set(attrs.keys()) - {"notes"}
            if blocked:
                raise serializers.ValidationError("Venda finalizada ou cancelada não pode ser editada, exceto observações.")
        return attrs

    def _sync_items(self, sale, items_data):
        sale.items.all().delete()
        for item in items_data:
            CounterSaleItem.objects.create(counter_sale=sale, **item)
        sale.recalculate_totals(save=True)

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        actor = self.context.get("actor")
        sale = CounterSale.objects.create(created_by=actor if getattr(actor, "is_authenticated", False) else None, updated_by=actor if getattr(actor, "is_authenticated", False) else None, **validated_data)
        self._sync_items(sale, items_data)
        return sale

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        actor = self.context.get("actor")
        if getattr(actor, "is_authenticated", False):
            instance.updated_by = actor
        instance.save()
        if items_data is not None:
            self._sync_items(instance, items_data)
        else:
            instance.recalculate_totals(save=True)
        return instance


class FinalizeCounterSaleSerializer(serializers.Serializer):
    payment_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.00"), required=False, default=Decimal("0.00"))
    payment_method = serializers.ChoiceField(choices=CounterSalePayment.Method.choices, required=False, default=CounterSalePayment.Method.CASH)
    payment_reference = serializers.CharField(required=False, allow_blank=True, max_length=120)
    payment_notes = serializers.CharField(required=False, allow_blank=True)

    def save(self, **kwargs):
        try:
            return finalize_counter_sale(self.context["counter_sale"], actor=self.context.get("actor"), **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class RegisterCounterSalePaymentSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=CounterSalePayment.Method.choices, default=CounterSalePayment.Method.CASH)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    paid_at = serializers.DateTimeField(required=False, default=timezone.now)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=120)
    notes = serializers.CharField(required=False, allow_blank=True)

    def save(self, **kwargs):
        try:
            return register_counter_sale_payment(self.context["counter_sale"], actor=self.context.get("actor"), **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class CancelCounterSaleSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)

    def save(self, **kwargs):
        try:
            return cancel_counter_sale(self.context["counter_sale"], actor=self.context.get("actor"), reason=self.validated_data.get("reason", ""))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class EstimateServiceItemSerializer(serializers.ModelSerializer):
    local_id = serializers.CharField(required=False, allow_blank=True, write_only=True)
    service_id = serializers.PrimaryKeyRelatedField(source="service", queryset=WorkshopService.objects.filter(is_active=True), required=False, allow_null=True, write_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    source_package_id = serializers.PrimaryKeyRelatedField(source="source_package", queryset=ServicePackage.objects.filter(is_active=True), required=False, allow_null=True, write_only=True)
    source_package_name = serializers.CharField(source="source_package.name", read_only=True)
    subtotal_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = EstimateServiceItem
        fields = ["id", "estimate", "local_id", "service", "service_id", "service_name", "source_package", "source_package_id", "source_package_name", "description", "quantity", "unit_price", "discount_amount", "notes", "approved_by_customer", "customer_decided_at", "subtotal_amount", "total_amount", "created_at", "updated_at"]
        read_only_fields = ["id", "estimate", "service", "service_name", "source_package", "source_package_name", "approved_by_customer", "customer_decided_at", "subtotal_amount", "total_amount", "created_at", "updated_at"]

    def validate(self, attrs):
        service = attrs.get("service")
        if service:
            attrs.setdefault("description", service.name)
            attrs.setdefault("unit_price", service.default_unit_price)
        if not attrs.get("description") and not getattr(self.instance, "description", ""):
            raise serializers.ValidationError({"description": "Informe a descrição do serviço do orçamento."})
        return attrs


class EstimatePartItemSerializer(serializers.ModelSerializer):
    local_id = serializers.CharField(required=False, allow_blank=True, write_only=True)
    service_local_id = serializers.CharField(required=False, allow_blank=True, write_only=True)
    service_item_id = serializers.PrimaryKeyRelatedField(source="service_item", queryset=EstimateServiceItem.objects.all(), required=False, allow_null=True, write_only=True)
    service_item_description = serializers.CharField(source="service_item.description", read_only=True)
    part_id = serializers.PrimaryKeyRelatedField(source="part", queryset=Part.objects.filter(is_active=True), required=False, allow_null=True, write_only=True)
    part_name = serializers.CharField(source="part.name", read_only=True)
    part_sku = serializers.CharField(source="part.sku", read_only=True)
    stock_available = serializers.DecimalField(source="part.stock_quantity", max_digits=12, decimal_places=2, read_only=True)
    subtotal_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = EstimatePartItem
        fields = ["id", "estimate", "local_id", "service_local_id", "service_item", "service_item_id", "service_item_description", "part", "part_id", "part_name", "part_sku", "stock_available", "description", "quantity", "unit_price", "cost_price", "discount_amount", "notes", "approved_by_customer", "customer_decided_at", "subtotal_amount", "total_amount", "created_at", "updated_at"]
        read_only_fields = ["id", "estimate", "service_item", "service_item_description", "part", "part_name", "part_sku", "stock_available", "approved_by_customer", "customer_decided_at", "subtotal_amount", "total_amount", "created_at", "updated_at"]

    def validate(self, attrs):
        part = attrs.get("part")
        if part:
            attrs.setdefault("description", part.name)
            attrs.setdefault("unit_price", part.sale_price)
            attrs.setdefault("cost_price", part.cost_price)
        if not attrs.get("description") and not getattr(self.instance, "description", ""):
            raise serializers.ValidationError({"description": "Informe a descrição da peça do orçamento."})
        return attrs


class EstimateStatusHistorySerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = EstimateStatusHistory
        fields = ["id", "estimate", "old_status", "new_status", "description", "data", "actor_name", "created_at"]
        read_only_fields = fields

    def get_actor_name(self, obj):
        return obj.actor.get_full_name() or obj.actor.username if obj.actor else ""


class EstimateSerializer(serializers.ModelSerializer):
    customer_id = serializers.PrimaryKeyRelatedField(source="customer", queryset=Contact.objects.filter(is_active=True), write_only=True)
    vehicle_id = serializers.PrimaryKeyRelatedField(source="vehicle", queryset=Vehicle.objects.filter(is_active=True), required=True, allow_null=False, write_only=True)
    customer = ContactSerializer(read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    vehicle = VehicleSerializer(read_only=True)
    vehicle_display = serializers.CharField(source="vehicle.display_name", read_only=True)
    status_label = serializers.CharField(read_only=True)
    tank_level_label = serializers.CharField(read_only=True)
    services = EstimateServiceItemSerializer(many=True, required=False)
    parts = EstimatePartItemSerializer(many=True, required=False)
    converted_work_order_detail = WorkOrderDetailSerializer(source="converted_work_order", read_only=True)
    revision_work_order_detail = WorkOrderDetailSerializer(source="revision_work_order", read_only=True)
    can_edit = serializers.SerializerMethodField()
    status_history = EstimateStatusHistorySerializer(many=True, read_only=True)
    cliente_id = serializers.IntegerField(source="customer_id", read_only=True)
    veiculo_id = serializers.IntegerField(source="vehicle_id", read_only=True)
    ordem_servico_id = serializers.IntegerField(read_only=True)
    data_criacao = serializers.DateTimeField(read_only=True)
    data_envio = serializers.DateTimeField(read_only=True)
    data_validade = serializers.DateField(read_only=True)
    data_aprovacao = serializers.DateTimeField(read_only=True)
    data_cancelamento = serializers.DateTimeField(read_only=True)
    motivo_cancelamento = serializers.CharField(read_only=True)
    motivo_recusa = serializers.CharField(read_only=True)
    forma_aprovacao = serializers.CharField(read_only=True)
    valor_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    observacoes = serializers.CharField(read_only=True)

    class Meta:
        model = Estimate
        fields = [
            "id",
            "number",
            "customer",
            "customer_id",
            "cliente_id",
            "customer_name",
            "vehicle",
            "vehicle_id",
            "veiculo_id",
            "vehicle_display",
            "title",
            "complaint",
            "diagnosis",
            "internal_notes",
            "customer_notes",
            "status",
            "status_label",
            "valid_until",
            "data_criacao",
            "data_envio",
            "data_validade",
            "data_aprovacao",
            "data_cancelamento",
            "tank_level_percent",
            "tank_level_label",
            "sent_at",
            "approved_at",
            "rejected_at",
            "converted_at",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
            "motivo_cancelamento",
            "rejection_reason",
            "motivo_recusa",
            "approved_by",
            "approval_method",
            "forma_aprovacao",
            "converted_work_order",
            "ordem_servico_id",
            "converted_work_order_detail",
            "revision_work_order",
            "revision_work_order_detail",
            "can_edit",
            "status_history",
            "subtotal_services",
            "subtotal_parts",
            "discount_amount",
            "total_amount",
            "valor_total",
            "observacoes",
            "services",
            "parts",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "number", "customer", "cliente_id", "customer_name", "vehicle", "veiculo_id", "vehicle_display", "status", "status_label", "tank_level_label", "sent_at", "data_criacao", "data_envio", "data_validade", "approved_at", "data_aprovacao", "rejected_at", "converted_at", "cancelled_at", "data_cancelamento", "cancelled_by", "cancellation_reason", "motivo_cancelamento", "rejection_reason", "motivo_recusa", "approved_by", "approval_method", "forma_aprovacao", "converted_work_order", "ordem_servico_id", "converted_work_order_detail", "revision_work_order", "revision_work_order_detail", "can_edit", "status_history", "subtotal_services", "subtotal_parts", "total_amount", "valor_total", "observacoes", "created_at", "updated_at"]

    def get_can_edit(self, obj):
        return obj.status in ESTIMATE_EDITABLE_STATUSES

    def validate(self, attrs):
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        vehicle = attrs.get("vehicle", getattr(self.instance, "vehicle", None))
        if not customer:
            raise serializers.ValidationError({"customer_id": "Informe o cliente do orçamento."})
        if not vehicle:
            raise serializers.ValidationError({"vehicle_id": "Informe o veículo do orçamento."})
        if vehicle and customer and vehicle.customer_id != customer.id:
            raise serializers.ValidationError({"vehicle_id": "O veículo informado pertence a outro cliente."})
        if self.instance and self.instance.status not in ESTIMATE_EDITABLE_STATUSES:
            raise serializers.ValidationError("Orçamento só pode ser editado enquanto estiver em rascunho. Orçamentos enviados, aprovados, recusados, expirados, cancelados ou convertidos ficam bloqueados operacionalmente.")
        return attrs

    def _sync_services(self, estimate, services_data):
        estimate.services.all().delete()
        service_map = {}
        for index, item in enumerate(services_data, start=1):
            local_id = item.pop("local_id", "") or f"service-{index}"
            service_item = EstimateServiceItem.objects.create(estimate=estimate, **item)
            service_map[str(local_id)] = service_item
            service_map[str(service_item.id)] = service_item
        return service_map

    def _sync_parts(self, estimate, parts_data, service_map=None):
        service_map = service_map or {}
        estimate.parts.all().delete()
        for item in parts_data:
            item.pop("local_id", None)
            service_local_id = str(item.pop("service_local_id", "") or "")
            if service_local_id and service_local_id in service_map:
                item["service_item"] = service_map[service_local_id]
            EstimatePartItem.objects.create(estimate=estimate, **item)

    def create(self, validated_data):
        parts_provided = isinstance(getattr(self, "initial_data", None), dict) and "parts" in self.initial_data
        services_data = validated_data.pop("services", [])
        parts_data = validated_data.pop("parts", [] if parts_provided else None)
        actor = self.context.get("actor")
        estimate = Estimate.objects.create(created_by=actor if getattr(actor, "is_authenticated", False) else None, updated_by=actor if getattr(actor, "is_authenticated", False) else None, **validated_data)
        service_map = self._sync_services(estimate, services_data)
        if parts_provided:
            self._sync_parts(estimate, parts_data or [], service_map)
        estimate.recalculate_totals(save=True)
        return estimate

    def update(self, instance, validated_data):
        services_data = validated_data.pop("services", None)
        parts_data = validated_data.pop("parts", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        actor = self.context.get("actor")
        if getattr(actor, "is_authenticated", False):
            instance.updated_by = actor
        instance.save()
        service_map = None
        if services_data is not None:
            service_map = self._sync_services(instance, services_data)
        if parts_data is not None:
            self._sync_parts(instance, parts_data, service_map)
        instance.recalculate_totals(save=True)
        return instance


class ChangeEstimateStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Estimate.Status.choices)
    note = serializers.CharField(required=False, allow_blank=True)
    send_notifications = serializers.BooleanField(default=True)

    def save(self, **kwargs):
        try:
            return change_estimate_status(
                self.context["estimate"],
                self.validated_data["status"],
                actor=self.context.get("actor"),
                note=self.validated_data.get("note", ""),
                send_notifications=self.validated_data.get("send_notifications", True),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class CancelEstimateSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=5, max_length=1000, trim_whitespace=True)
    send_notifications = serializers.BooleanField(default=True)

    def save(self, **kwargs):
        try:
            return cancel_estimate(
                self.context["estimate"],
                actor=self.context.get("actor"),
                reason=self.validated_data["reason"],
                send_notifications=self.validated_data.get("send_notifications", True),
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise serializers.ValidationError(exc.message_dict)
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class ConvertEstimateSerializer(serializers.Serializer):
    def save(self, **kwargs):
        try:
            return convert_estimate_to_work_order(self.context["estimate"], actor=self.context.get("actor"))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class ManualEstimateApprovalSerializer(serializers.Serializer):
    approval_type = serializers.ChoiceField(choices=[("total", "Total"), ("partial", "Parcial")], default="total")
    selected_service_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, allow_empty=True)
    selected_part_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, allow_empty=True)
    notes = serializers.CharField(required=True, allow_blank=False)
    signature_name = serializers.CharField(required=False, allow_blank=True, max_length=180)
    signature_document = serializers.CharField(required=False, allow_blank=True, max_length=30)

    def validate_notes(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Informe uma observação para registrar a aprovação manual.")
        return value

    def save(self, **kwargs):
        try:
            return manually_approve_estimate(
                self.context["estimate"],
                actor=self.context.get("actor"),
                approval_type=self.validated_data.get("approval_type", "total"),
                selected_service_ids=self.validated_data.get("selected_service_ids"),
                selected_part_ids=self.validated_data.get("selected_part_ids"),
                notes=self.validated_data.get("notes", ""),
                signature_name=self.validated_data.get("signature_name", ""),
                signature_document=self.validated_data.get("signature_document", ""),
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise serializers.ValidationError(exc.message_dict)
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class EstimateCustomerApprovalCreateSerializer(serializers.Serializer):
    expires_days = serializers.IntegerField(required=False, min_value=1, max_value=60, default=7)
    frontend_base_url = serializers.URLField(required=False, allow_blank=True)


class EstimateCustomerApprovalSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(read_only=True)
    effective_status = serializers.CharField(read_only=True)
    can_decide = serializers.BooleanField(read_only=True)
    public_url_path = serializers.CharField(read_only=True)
    requested_by_name = serializers.SerializerMethodField()
    generated_work_order_number = serializers.CharField(source="generated_work_order.number", read_only=True)

    class Meta:
        model = EstimateCustomerApproval
        fields = [
            "id",
            "estimate",
            "token",
            "status",
            "status_label",
            "effective_status",
            "requested_by_name",
            "requested_at",
            "expires_at",
            "customer_name_snapshot",
            "customer_email_snapshot",
            "customer_phone_snapshot",
            "decision_name",
            "decision_document",
            "decision_notes",
            "decision_selected_services",
            "decision_selected_parts",
            "decided_at",
            "generated_work_order",
            "generated_work_order_number",
            "public_url_path",
            "can_decide",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_requested_by_name(self, obj):
        return obj.requested_by.get_full_name() or obj.requested_by.username if obj.requested_by else ""


class EstimateCustomerApprovalPublicSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(read_only=True)
    effective_status = serializers.CharField(read_only=True)
    can_decide = serializers.BooleanField(read_only=True)
    document_type_label = serializers.CharField(read_only=True)
    estimate = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()
    parts = serializers.SerializerMethodField()
    totals = serializers.SerializerMethodField()
    workshop = serializers.SerializerMethodField()

    class Meta:
        model = EstimateCustomerApproval
        fields = [
            "id",
            "token",
            "status",
            "status_label",
            "effective_status",
            "document_type_label",
            "requested_at",
            "expires_at",
            "customer_name_snapshot",
            "customer_email_snapshot",
            "customer_phone_snapshot",
            "decision_name",
            "decision_notes",
            "decision_selected_services",
            "decision_selected_parts",
            "decided_at",
            "can_decide",
            "estimate",
            "services",
            "parts",
            "totals",
            "workshop",
        ]
        read_only_fields = fields

    def get_estimate(self, obj):
        estimate = obj.estimate
        return {
            "id": estimate.id,
            "number": estimate.number,
            "title": estimate.title,
            "customer_name": estimate.customer.full_name,
            "vehicle_display": estimate.vehicle.display_name if estimate.vehicle_id else "",
            "status": estimate.status,
            "status_label": estimate.status_label,
            "valid_until": estimate.valid_until,
            "tank_level_percent": estimate.tank_level_percent,
            "tank_level_label": estimate.tank_level_label,
            "complaint": estimate.complaint,
            "diagnosis": estimate.diagnosis,
            "customer_notes": estimate.customer_notes,
        }

    def get_services(self, obj):
        return [
            {
                "id": item.id,
                "description": item.description,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "discount_amount": item.discount_amount,
                "subtotal_amount": item.subtotal_amount,
                "total_amount": item.total_amount,
                "approved_by_customer": item.approved_by_customer,
            }
            for item in obj.estimate.services.all()
        ]

    def get_parts(self, obj):
        return [
            {
                "id": item.id,
                "service_item": item.service_item_id,
                "service_item_description": item.service_item.description if item.service_item_id else "",
                "sku": item.part.sku if item.part_id else "",
                "description": item.description,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "discount_amount": item.discount_amount,
                "subtotal_amount": item.subtotal_amount,
                "total_amount": item.total_amount,
                "approved_by_customer": item.approved_by_customer,
            }
            for item in obj.estimate.parts.all()
        ]

    def get_totals(self, obj):
        estimate = obj.estimate
        item_discounts = sum((item.discount_amount or Decimal("0.00") for item in estimate.services.all()), Decimal("0.00")) + sum((item.discount_amount or Decimal("0.00") for item in estimate.parts.all()), Decimal("0.00"))
        return {
            "subtotal_services": estimate.subtotal_services,
            "subtotal_parts": estimate.subtotal_parts,
            "discount_total": item_discounts + (estimate.discount_amount or Decimal("0.00")),
            "total_amount": estimate.total_amount,
        }

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


class EstimateCustomerApprovalDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=[("approved", "Aprovar"), ("rejected", "Rejeitar")])
    name = serializers.CharField(required=False, allow_blank=True, max_length=180)
    document = serializers.CharField(required=True, allow_blank=False, max_length=30)
    notes = serializers.CharField(required=True, allow_blank=False)
    selected_service_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, allow_empty=True)
    selected_part_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, allow_empty=True)
    confirm_partial = serializers.BooleanField(default=False)

    def save(self, **kwargs):
        try:
            return decide_estimate_approval(
                self.context["approval"],
                self.validated_data["decision"],
                self.validated_data.get("selected_service_ids", []),
                self.validated_data.get("selected_part_ids", []),
                name=self.validated_data.get("name", ""),
                document=self.validated_data.get("document", ""),
                notes=self.validated_data.get("notes", ""),
                confirm_partial=self.validated_data.get("confirm_partial", False),
                ip_address=self.context.get("ip_address"),
                user_agent=self.context.get("user_agent", ""),
                actor=self.context.get("actor"),
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise serializers.ValidationError(exc.message_dict)
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))
