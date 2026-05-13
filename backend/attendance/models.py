from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from uuid import uuid4

from accounts.numbering import next_formatted_sequence

from messaging.models import Contact, TimeStampedModel
from workshop.models import Part, PartStockMovement, ServiceDefaultPart, ServicePackage, Vehicle, WorkOrder, WorkshopService

ZERO = Decimal("0.00")


class CounterSale(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        FINALIZED = "finalized", "Finalizada"
        CANCELLED = "cancelled", "Cancelada"

    number = models.CharField(max_length=30, unique=True, blank=True)
    customer = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.PROTECT, related_name="counter_sales")
    customer_name = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    sold_at = models.DateTimeField(null=True, blank=True, db_index=True)
    due_date = models.DateField(default=timezone.localdate, db_index=True)
    subtotal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_counter_sales")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_counter_sales")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "sold_at"], name="attsale_status_sold_idx"),
            models.Index(fields=["number"], name="attsale_number_idx"),
        ]

    @property
    def status_label(self):
        return self.get_status_display()

    @property
    def effective_customer_name(self):
        if self.customer_id:
            return self.customer.full_name
        return self.customer_name or "Cliente balcão"

    @classmethod
    def generate_number(cls):
        return next_formatted_sequence("counter_sale", "VA", cls)

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self.generate_number()
        super().save(*args, **kwargs)

    def recalculate_totals(self, save=True):
        if self.pk:
            subtotal = sum((item.subtotal_amount for item in self.items.all()), ZERO)
            item_discounts = sum((item.discount_amount or ZERO for item in self.items.all()), ZERO)
            payments = sum((payment.amount or ZERO for payment in self.payments.all()), ZERO)
        else:
            subtotal = self.subtotal_amount or ZERO
            item_discounts = ZERO
            payments = self.paid_amount or ZERO
        total_discount = item_discounts + (self.discount_amount or ZERO)
        total = subtotal - total_discount
        self.subtotal_amount = subtotal
        self.total_amount = total if total > ZERO else ZERO
        self.paid_amount = payments
        balance = self.total_amount - self.paid_amount
        self.balance_amount = balance if balance > ZERO else ZERO
        if save:
            self.save(update_fields=["subtotal_amount", "discount_amount", "total_amount", "paid_amount", "balance_amount", "updated_at"])
        return self

    def __str__(self):
        return self.number or f"Venda avulsa #{self.pk}"


class CounterSaleItem(TimeStampedModel):
    counter_sale = models.ForeignKey(CounterSale, on_delete=models.CASCADE, related_name="items")
    part = models.ForeignKey(Part, null=True, blank=True, on_delete=models.SET_NULL, related_name="counter_sale_items")
    description = models.CharField(max_length=220)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1.00"), validators=[MinValueValidator(Decimal("0.01"))])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    stock_movement = models.ForeignKey(PartStockMovement, null=True, blank=True, on_delete=models.SET_NULL, related_name="counter_sale_items")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["id"]

    @property
    def subtotal_amount(self):
        return (self.quantity or ZERO) * (self.unit_price or ZERO)

    @property
    def total_amount(self):
        total = self.subtotal_amount - (self.discount_amount or ZERO)
        return total if total > ZERO else ZERO

    def save(self, *args, **kwargs):
        if self.counter_sale_id and self.counter_sale.status != CounterSale.Status.DRAFT:
            raise ValidationError("Itens de venda finalizada ou cancelada não podem ser alterados.")
        if self.part:
            if not self.description:
                self.description = self.part.name
            if not self.unit_price:
                self.unit_price = self.part.sale_price
            if not self.cost_price:
                self.cost_price = self.part.cost_price
        super().save(*args, **kwargs)
        self.counter_sale.recalculate_totals()

    def delete(self, *args, **kwargs):
        if self.counter_sale.status != CounterSale.Status.DRAFT:
            raise ValidationError("Itens de venda finalizada ou cancelada não podem ser excluídos.")
        sale = self.counter_sale
        result = super().delete(*args, **kwargs)
        sale.recalculate_totals()
        return result

    def __str__(self):
        return self.description


class CounterSalePayment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Dinheiro"
        CARD = "card", "Cartão"
        BANK_TRANSFER = "bank_transfer", "Transferência"
        MBWAY = "mbway", "MB Way"
        PIX = "pix", "Pix"
        OTHER = "other", "Outro"

    counter_sale = models.ForeignKey(CounterSale, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField(max_length=30, choices=Method.choices, default=Method.CASH)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    paid_at = models.DateTimeField(default=timezone.now, db_index=True)
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_counter_sale_payments")

    class Meta:
        ordering = ["-paid_at", "-id"]

    @property
    def method_label(self):
        return self.get_method_display()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.counter_sale.recalculate_totals()

    def delete(self, *args, **kwargs):
        sale = self.counter_sale
        result = super().delete(*args, **kwargs)
        sale.recalculate_totals()
        return result

    def __str__(self):
        return f"{self.counter_sale.number} - {self.amount}"


class Estimate(TimeStampedModel):
    class TankLevel(models.IntegerChoices):
        EMPTY = 0, "0%"
        QUARTER = 25, "25%"
        HALF = 50, "50%"
        THREE_QUARTERS = 75, "75%"
        FULL = 100, "100%"

    class Status(models.TextChoices):
        OPEN = "open", "Aberto"
        DIAGNOSIS = "diagnosis", "Em diagnostico"
        AWAITING_APPROVAL = "awaiting_approval", "Aguardando aprovacao"
        APPROVED = "approved", "Aprovado"
        PARTIALLY_APPROVED = "partially_approved", "Aprovado parcialmente"
        REJECTED = "rejected", "Rejeitado"
        EXPIRED = "expired", "Expirado"
        CONVERTED = "converted", "Convertido em OS"
        CANCELLED = "cancelled", "Cancelado"

    number = models.CharField(max_length=30, unique=True, blank=True)
    customer = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="estimates")
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.PROTECT, related_name="estimates")
    title = models.CharField(max_length=180)
    complaint = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    customer_notes = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN, db_index=True)
    valid_until = models.DateField(null=True, blank=True, db_index=True)
    tank_level_percent = models.PositiveSmallIntegerField(choices=TankLevel.choices, default=TankLevel.EMPTY)
    sent_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="cancelled_estimates")
    converted_work_order = models.OneToOneField(WorkOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name="source_estimate")
    revision_work_order = models.ForeignKey(WorkOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name="revision_estimates")
    subtotal_services = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    subtotal_parts = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_estimates")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_estimates")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "valid_until"], name="estimate_status_valid_idx"),
            models.Index(fields=["number"], name="estimate_number_idx"),
        ]

    @property
    def status_label(self):
        return self.get_status_display()

    @property
    def tank_level_label(self):
        return self.get_tank_level_percent_display()

    @classmethod
    def generate_number(cls):
        return next_formatted_sequence("estimate", "ORC", cls)

    def clean(self):
        super().clean()
        if self.vehicle_id and self.customer_id and self.vehicle.customer_id != self.customer_id:
            raise ValidationError({"vehicle": "O veículo informado pertence a outro cliente."})

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self.generate_number()
        super().save(*args, **kwargs)

    def recalculate_totals(self, save=True):
        if self.pk:
            service_subtotal = sum((item.subtotal_amount for item in self.services.all()), ZERO)
            part_subtotal = sum((item.subtotal_amount for item in self.parts.all()), ZERO)
            item_discounts = sum((item.discount_amount or ZERO for item in self.services.all()), ZERO) + sum((item.discount_amount or ZERO for item in self.parts.all()), ZERO)
        else:
            service_subtotal = self.subtotal_services or ZERO
            part_subtotal = self.subtotal_parts or ZERO
            item_discounts = ZERO
        total_discount = item_discounts + (self.discount_amount or ZERO)
        total = service_subtotal + part_subtotal - total_discount
        self.subtotal_services = service_subtotal
        self.subtotal_parts = part_subtotal
        self.total_amount = total if total > ZERO else ZERO
        if save:
            self.save(update_fields=["subtotal_services", "subtotal_parts", "discount_amount", "total_amount", "updated_at"])
        return self

    def __str__(self):
        return self.number or f"Orçamento #{self.pk}"


class EstimateServiceItem(TimeStampedModel):
    estimate = models.ForeignKey(Estimate, on_delete=models.CASCADE, related_name="services")
    service = models.ForeignKey(WorkshopService, null=True, blank=True, on_delete=models.SET_NULL, related_name="estimate_items")
    source_package = models.ForeignKey(ServicePackage, null=True, blank=True, on_delete=models.SET_NULL, related_name="estimate_service_lines")
    description = models.CharField(max_length=220)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"), validators=[MinValueValidator(Decimal("0.01"))])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    notes = models.TextField(blank=True)
    approved_by_customer = models.BooleanField(default=True, db_index=True)
    customer_decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    @property
    def subtotal_amount(self):
        return (self.quantity or ZERO) * (self.unit_price or ZERO)

    @property
    def total_amount(self):
        total = self.subtotal_amount - (self.discount_amount or ZERO)
        return total if total > ZERO else ZERO

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if self.estimate_id and self.estimate.status not in {Estimate.Status.OPEN, Estimate.Status.REJECTED}:
            raise ValidationError("Itens só podem ser alterados em orçamento aberto ou recusado.")
        if self.service:
            if not self.description:
                self.description = self.service.name
            if not self.unit_price:
                self.unit_price = self.service.default_unit_price
        super().save(*args, **kwargs)
        if is_new:
            self.create_default_parts_from_template()
        self.estimate.recalculate_totals()

    def create_default_parts_from_template(self):
        if not self.service_id:
            return 0
        if self.parts.exists():
            return 0
        defaults = ServiceDefaultPart.objects.filter(service=self.service, is_active=True).select_related("part").order_by("position", "id")
        created = 0
        for template in defaults:
            part = template.part
            EstimatePartItem.objects.create(
                estimate=self.estimate,
                service_item=self,
                part=part,
                description=part.name,
                quantity=template.quantity,
                unit_price=template.effective_unit_price,
                cost_price=part.cost_price,
                discount_amount=template.discount_amount,
                notes=template.notes or f"Adicionada automaticamente pelo serviço {self.description}.",
            )
            created += 1
        return created

    def delete(self, *args, **kwargs):
        if self.estimate.status not in {Estimate.Status.OPEN, Estimate.Status.REJECTED}:
            raise ValidationError("Itens só podem ser excluídos em orçamento aberto ou recusado.")
        estimate = self.estimate
        result = super().delete(*args, **kwargs)
        estimate.recalculate_totals()
        return result

    def __str__(self):
        return self.description


class EstimatePartItem(TimeStampedModel):
    estimate = models.ForeignKey(Estimate, on_delete=models.CASCADE, related_name="parts")
    service_item = models.ForeignKey(EstimateServiceItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="parts")
    part = models.ForeignKey(Part, null=True, blank=True, on_delete=models.SET_NULL, related_name="estimate_items")
    description = models.CharField(max_length=220)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"), validators=[MinValueValidator(Decimal("0.01"))])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    notes = models.TextField(blank=True)
    approved_by_customer = models.BooleanField(default=True, db_index=True)
    customer_decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    @property
    def subtotal_amount(self):
        return (self.quantity or ZERO) * (self.unit_price or ZERO)

    @property
    def total_amount(self):
        total = self.subtotal_amount - (self.discount_amount or ZERO)
        return total if total > ZERO else ZERO

    def save(self, *args, **kwargs):
        if self.estimate_id and self.estimate.status not in {Estimate.Status.OPEN, Estimate.Status.REJECTED}:
            raise ValidationError("Itens só podem ser alterados em orçamento aberto ou recusado.")
        if self.part:
            if not self.description:
                self.description = self.part.name
            if not self.unit_price:
                self.unit_price = self.part.sale_price
            if not self.cost_price:
                self.cost_price = self.part.cost_price
        super().save(*args, **kwargs)
        self.estimate.recalculate_totals()

    def delete(self, *args, **kwargs):
        if self.estimate.status not in {Estimate.Status.OPEN, Estimate.Status.REJECTED}:
            raise ValidationError("Itens só podem ser excluídos em orçamento aberto ou recusado.")
        estimate = self.estimate
        result = super().delete(*args, **kwargs)
        estimate.recalculate_totals()
        return result

    def __str__(self):
        return self.description


class EstimateCustomerApproval(TimeStampedModel):
    """Link publico e auditavel para aprovacao digital de orcamento pelo cliente."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        APPROVED = "approved", "Aprovado"
        PARTIALLY_APPROVED = "partially_approved", "Aprovado parcialmente"
        REJECTED = "rejected", "Rejeitado"
        EXPIRED = "expired", "Expirado"

    estimate = models.ForeignKey(Estimate, on_delete=models.CASCADE, related_name="customer_approvals")
    token = models.UUIDField(default=uuid4, unique=True, editable=False, db_index=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING, db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="requested_estimate_approvals")
    requested_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    customer_name_snapshot = models.CharField(max_length=180, blank=True)
    customer_email_snapshot = models.EmailField(blank=True)
    customer_phone_snapshot = models.CharField(max_length=30, blank=True)
    decision_name = models.CharField(max_length=180, blank=True)
    decision_document = models.CharField(max_length=30, blank=True)
    decision_notes = models.TextField(blank=True)
    decision_selected_services = models.JSONField(default=list, blank=True)
    decision_selected_parts = models.JSONField(default=list, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_ip = models.GenericIPAddressField(null=True, blank=True)
    decision_user_agent = models.TextField(blank=True)
    generated_work_order = models.OneToOneField(WorkOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name="source_estimate_approval")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-requested_at", "-id"]
        indexes = [
            models.Index(fields=["estimate", "status"], name="est_approval_status_idx"),
            models.Index(fields=["token", "status"], name="est_approval_token_idx"),
        ]
        verbose_name = "aprovação digital de orçamento"
        verbose_name_plural = "aprovações digitais de orçamento"

    @property
    def status_label(self):
        current_status = self.effective_status
        return dict(self.Status.choices).get(current_status, current_status)

    @property
    def document_type_label(self):
        return "Orçamento"

    @property
    def public_url_path(self):
        return f"/aprovar-orcamento/{self.token}"

    @property
    def is_expired(self):
        return bool(self.expires_at and timezone.now() > self.expires_at and self.status == self.Status.PENDING)

    @property
    def effective_status(self):
        if self.is_expired:
            return self.Status.EXPIRED
        return self.status

    @property
    def can_decide(self):
        return self.is_active and self.effective_status == self.Status.PENDING

    def save(self, *args, **kwargs):
        if self.estimate_id and not self.customer_name_snapshot:
            self.customer_name_snapshot = self.estimate.customer.full_name
        if self.estimate_id and not self.customer_email_snapshot:
            self.customer_email_snapshot = self.estimate.customer.email or ""
        if self.estimate_id and not self.customer_phone_snapshot:
            self.customer_phone_snapshot = self.estimate.customer.phone_e164 or self.estimate.customer.secondary_phone_e164 or ""
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Orçamento {self.estimate.number} - {self.status_label}"
