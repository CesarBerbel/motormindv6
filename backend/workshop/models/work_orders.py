
from .common import *
from .catalog import GeneralCategory, Part, ServiceDefaultPart, ServicePackage, WorkshopService, WorkshopServiceChecklistTemplate
from .profile import WorkshopProfile
from .vehicles import Vehicle

class WorkOrder(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Aberta"
        IN_PROGRESS = "in_progress", "Em execucao"
        WAITING_PARTS = "waiting_parts", "Aguardando pecas"
        COMPLETED = "completed", "Concluida"

    class Priority(models.TextChoices):
        LOW = "low", "Baixa"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Alta"
        URGENT = "urgent", "Urgente"

    class OrderType(models.TextChoices):
        STANDARD = "standard", "Normal"
        RETURN = "return", "Retorno"
        WARRANTY = "warranty", "Garantia"

    number = models.CharField(max_length=30, unique=True, blank=True)
    customer = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="work_orders")
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.PROTECT, related_name="work_orders")
    title = models.CharField(max_length=180, blank=True)
    complaint = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)
    solution = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    customer_notes = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN, db_index=True)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    order_type = models.CharField(max_length=20, choices=OrderType.choices, default=OrderType.STANDARD, db_index=True)
    reference_work_order = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="referenced_by_work_orders")
    source_estimate_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    source_estimate_number = models.CharField(max_length=30, blank=True)
    mileage_in = models.PositiveIntegerField(default=0)
    mileage_out = models.PositiveIntegerField(null=True, blank=True)
    promised_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_work_orders")
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_work_orders")
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_work_orders")
    subtotal_services = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    subtotal_parts = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    manual_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    paid_total = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    balance_due = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    inventory_consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"], name="wo_status_priority_idx"),
            models.Index(fields=["number"], name="workshop_wo_number_idx"),
        ]

    @property
    def status_label(self):
        return self.get_status_display()

    @property
    def priority_label(self):
        return self.get_priority_display()

    @property
    def order_type_label(self):
        return self.get_order_type_display()

    def clean(self):
        super().clean()
        if self.order_type == self.OrderType.WARRANTY and not self.reference_work_order_id:
            raise ValidationError({"reference_work_order": "Informe a OS de referencia quando o tipo for garantia."})
        if self.pk and self.reference_work_order_id == self.pk:
            raise ValidationError({"reference_work_order": "A OS de referencia nao pode ser a propria OS."})
        if self.reference_work_order_id:
            reference = self.reference_work_order
            if self.customer_id and reference.customer_id != self.customer_id:
                raise ValidationError({"reference_work_order": "A OS de referencia precisa pertencer ao mesmo cliente."})
            if self.vehicle_id and reference.vehicle_id and reference.vehicle_id != self.vehicle_id:
                raise ValidationError({"reference_work_order": "A OS de referencia precisa pertencer ao mesmo veiculo."})

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self.generate_number()
        super().save(*args, **kwargs)

    @classmethod
    def generate_number(cls):
        return next_formatted_sequence("work_order", "OS", cls)

    def recalculate_totals(self, save=True):
        services_subtotal = sum((line.subtotal_amount for line in self.services.all()), ZERO)
        parts_subtotal = sum((line.subtotal_amount for line in self.parts.all()), ZERO)
        service_discounts = sum((line.discount_amount or ZERO for line in self.services.all()), ZERO)
        part_discounts = sum((line.discount_amount or ZERO for line in self.parts.all()), ZERO)
        paid_total = sum((payment.amount or ZERO for payment in self.payments.filter(reversed_at__isnull=True)), ZERO)
        total_discount = service_discounts + part_discounts + (self.manual_discount_amount or ZERO)
        grand_total = services_subtotal + parts_subtotal - total_discount
        self.subtotal_services = services_subtotal
        self.subtotal_parts = parts_subtotal
        self.discount_total = total_discount
        self.grand_total = grand_total if grand_total > ZERO else ZERO
        self.paid_total = paid_total
        self.balance_due = self.grand_total - paid_total
        if save:
            self.save(update_fields=["subtotal_services", "subtotal_parts", "manual_discount_amount", "discount_total", "grand_total", "paid_total", "balance_due", "updated_at"])
        return self

    def __str__(self):
        return self.number or f"OS #{self.pk}"




class WorkOrderPhoto(TimeStampedModel):
    """Fotos de evidência vinculadas à OS, principalmente na abertura do veículo."""

    class PhotoType(models.TextChoices):
        OPENING = "opening", "Abertura / estado de entrada"
        DAMAGE = "damage", "Avaria pré-existente"
        ODOMETER = "odometer", "Hodômetro"
        DOCUMENT = "document", "Documento / etiqueta"
        DELIVERY = "delivery", "Entrega"
        OTHER = "other", "Outro"

    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="photos")
    image = models.FileField(
        upload_to=work_order_photo_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=IMAGE_EXTENSIONS)],
        verbose_name="Foto da OS",
    )
    photo_type = models.CharField(max_length=30, choices=PhotoType.choices, default=PhotoType.OPENING, db_index=True)
    caption = models.CharField(max_length=220, blank=True)
    taken_at = models.DateTimeField(default=timezone.now)
    uploaded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="uploaded_work_order_photos")
    original_filename = models.CharField(max_length=180, blank=True)
    content_type = models.CharField(max_length=80, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    is_customer_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ["-taken_at", "-created_at"]
        indexes = [models.Index(fields=["work_order", "photo_type"], name="wo_photo_type_idx")]
        verbose_name = "foto de OS"
        verbose_name_plural = "fotos de OS"

    @property
    def image_url(self):
        return self.image.url if self.image else ""

    @property
    def uploaded_by_name(self):
        return self.uploaded_by.get_full_name() or self.uploaded_by.username if self.uploaded_by else ""

    def clean(self):
        super().clean()
        validate_file_size(self.image, MAX_IMAGE_SIZE, "foto da OS")

    def save(self, *args, **kwargs):
        if self.image:
            self.original_filename = self.original_filename or os.path.basename(getattr(self.image, "name", ""))[:180]
            self.file_size = getattr(self.image, "size", self.file_size or 0) or 0
            self.content_type = getattr(self.image, "content_type", self.content_type or "") or ""
            if not self.sha256 and hasattr(self.image, "chunks"):
                digest = hashlib.sha256()
                for chunk in self.image.chunks():
                    digest.update(chunk)
                self.sha256 = digest.hexdigest()
                try:
                    self.image.seek(0)
                except Exception:
                    pass
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.work_order} - {self.get_photo_type_display()}"




class WorkOrderService(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        APPROVED = "approved", "Aprovado"
        IN_PROGRESS = "in_progress", "Em execucao"
        DONE = "done", "Concluido"
        CANCELLED = "cancelled", "Cancelado"

    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="services")
    service = models.ForeignKey(WorkshopService, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_order_lines")
    source_package = models.ForeignKey(ServicePackage, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_order_service_lines")
    description = models.CharField(max_length=220)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"), validators=[MinValueValidator(Decimal("0.01"))])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    technician = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_order_service_lines")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)
    technical_diagnosis = models.TextField(blank=True)
    execution_notes = models.TextField(blank=True)
    checklist = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    expected_minutes = models.PositiveIntegerField(default=0)
    actual_minutes = models.PositiveIntegerField(default=0)
    needs_quality_check = models.BooleanField(default=True)
    quality_checked_at = models.DateTimeField(null=True, blank=True)
    quality_check_notes = models.TextField(blank=True)
    quality_checked_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="quality_checked_service_lines")

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
        if self.service:
            if not self.description:
                self.description = self.service.name
            if not self.unit_price:
                self.unit_price = self.service.default_unit_price
        super().save(*args, **kwargs)
        if is_new:
            self.create_checklist_from_template()
            self.create_default_parts_from_template()
        self.work_order.recalculate_totals()

    def create_default_parts_from_template(self):
        if not self.service_id:
            return 0
        if self.linked_parts.exists():
            return 0
        defaults = ServiceDefaultPart.objects.filter(service=self.service, is_active=True).select_related("part").order_by("position", "id")
        created = 0
        for template in defaults:
            part = template.part
            WorkOrderPart.objects.create(
                work_order=self.work_order,
                linked_service=self,
                part=part,
                description=part.name,
                quantity=template.quantity,
                unit_price=template.effective_unit_price,
                cost_price=part.cost_price,
                discount_amount=template.discount_amount,
                consume_inventory=template.consume_inventory,
                notes=template.notes or f"Adicionada automaticamente pelo serviço {self.description}.",
            )
            created += 1
        return created

    def create_checklist_from_template(self):
        if not self.service_id:
            return 0
        profile = WorkshopProfile.get_solo()
        if not profile.technical_checklist_enabled:
            return 0
        if self.checklist_items.exists():
            return 0
        templates = self.service.checklist_templates.filter(is_active=True).order_by("sort_order", "id")
        items = [
            WorkOrderServiceChecklistItem(
                work_order=self.work_order,
                work_order_service=self,
                source_template=template,
                description=template.description,
                is_required=template.is_required,
                requires_photo=template.requires_photo,
                requires_note=template.requires_note,
                sort_order=template.sort_order,
            )
            for template in templates
        ]
        if items:
            WorkOrderServiceChecklistItem.objects.bulk_create(items)
        return len(items)

    def delete(self, *args, **kwargs):
        work_order = self.work_order
        result = super().delete(*args, **kwargs)
        work_order.recalculate_totals()
        return result

    def __str__(self):
        return self.description




class WorkOrderServiceChecklistItem(TimeStampedModel):
    """Snapshot do checklist técnico copiado para uma OS específica."""

    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="technical_checklist_items")
    work_order_service = models.ForeignKey(WorkOrderService, on_delete=models.CASCADE, related_name="checklist_items")
    source_template = models.ForeignKey(WorkshopServiceChecklistTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_order_items")
    description = models.CharField(max_length=220)
    is_required = models.BooleanField(default=True)
    requires_photo = models.BooleanField(default=False)
    requires_note = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    is_completed = models.BooleanField(default=False, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="completed_work_order_checklist_items")
    note = models.TextField(blank=True)
    photo = models.FileField(
        upload_to=work_order_checklist_photo_upload_path,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=IMAGE_EXTENSIONS)],
        verbose_name="Foto do checklist",
    )

    class Meta:
        ordering = ["work_order_service_id", "sort_order", "id"]
        indexes = [
            models.Index(fields=["work_order", "is_completed"], name="wo_chk_completed_idx"),
            models.Index(fields=["work_order_service", "sort_order"], name="wo_chk_service_order_idx"),
        ]
        verbose_name = "item de checklist da OS"
        verbose_name_plural = "itens de checklist da OS"

    @property
    def photo_url(self):
        return self.photo.url if self.photo else ""

    @property
    def completed_by_name(self):
        return self.completed_by.get_full_name() or self.completed_by.username if self.completed_by else ""

    @property
    def is_blocking_pending(self):
        if not self.is_required:
            return False
        if not self.is_completed:
            return True
        if self.requires_note and not (self.note or "").strip():
            return True
        if self.requires_photo and not self.photo:
            return True
        return False

    def clean(self):
        super().clean()
        self.description = (self.description or "").strip()
        if not self.description:
            raise ValidationError({"description": "Informe a descrição do item."})
        if self.is_completed and self.requires_note and not (self.note or "").strip():
            raise ValidationError({"note": "Este item exige observação antes de ser concluído."})
        if self.is_completed and self.requires_photo and not self.photo:
            raise ValidationError({"photo": "Este item exige foto antes de ser concluído."})

    def save(self, *args, **kwargs):
        if self.is_completed and not self.completed_at:
            self.completed_at = timezone.now()
        if not self.is_completed:
            self.completed_at = None
            self.completed_by = None
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.work_order} - {self.description}"




class WorkOrderPart(TimeStampedModel):
    class ReservationStatus(models.TextChoices):
        NOT_APPLICABLE = "not_applicable", "Não aplicável"
        PENDING = "pending", "Pendente"
        RESERVED = "reserved", "Reservada"
        PARTIAL = "partial", "Parcial"
        UNAVAILABLE = "unavailable", "Sem estoque"

    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="parts")
    part = models.ForeignKey(Part, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_order_lines")
    linked_service = models.ForeignKey(WorkOrderService, null=True, blank=True, on_delete=models.SET_NULL, related_name="linked_parts")
    description = models.CharField(max_length=220)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"), validators=[MinValueValidator(Decimal("0.01"))])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    consume_inventory = models.BooleanField(default=True)
    stock_consumed_at = models.DateTimeField(null=True, blank=True)
    stock_reserved_at = models.DateTimeField(null=True, blank=True)
    stock_reserved_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    stock_shortage_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    stock_reservation_status = models.CharField(max_length=30, choices=ReservationStatus.choices, default=ReservationStatus.PENDING, db_index=True)
    stock_reservation_notes = models.TextField(blank=True)
    stock_movement = models.ForeignKey("PartStockMovement", null=True, blank=True, on_delete=models.SET_NULL, related_name="work_order_part_lines")
    stock_reservation_movement = models.ForeignKey("PartStockMovement", null=True, blank=True, on_delete=models.SET_NULL, related_name="reserved_work_order_part_lines")
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
        if self.part:
            if not self.description:
                self.description = self.part.name
            if not self.unit_price:
                self.unit_price = self.part.sale_price
            if not self.cost_price:
                self.cost_price = self.part.cost_price
        super().save(*args, **kwargs)
        self.work_order.recalculate_totals()

    def delete(self, *args, **kwargs):
        work_order = self.work_order
        result = super().delete(*args, **kwargs)
        work_order.recalculate_totals()
        return result

    def __str__(self):
        return self.description




class WorkOrderPayment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Dinheiro"
        CARD = "card", "Cartao"
        BANK_TRANSFER = "bank_transfer", "Transferencia"
        MBWAY = "mbway", "MB Way"
        PIX = "pix", "Pix"
        OTHER = "other", "Outro"

    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField(max_length=30, choices=Method.choices, default=Method.CASH)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    paid_at = models.DateTimeField(default=timezone.now)
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_work_order_payments")
    reversed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    reversed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="reversed_work_order_payments")
    reversal_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-paid_at"]

    @property
    def is_reversed(self):
        return bool(self.reversed_at)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.work_order.recalculate_totals()

    def delete(self, *args, **kwargs):
        work_order = self.work_order
        result = super().delete(*args, **kwargs)
        work_order.recalculate_totals()
        return result

    def __str__(self):
        return f"{self.work_order} - {self.amount}"




class PartStockMovement(TimeStampedModel):
    class MovementType(models.TextChoices):
        PURCHASE = "purchase", "Entrada/compra"
        ADJUSTMENT = "adjustment", "Ajuste"
        RESERVATION = "reservation", "Reserva para OS"
        RESERVATION_RELEASE = "reservation_release", "Liberação de reserva"
        CONSUMPTION = "consumption", "Consumo em OS"
        REVERSAL = "reversal", "Estorno"

    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name="stock_movements")
    movement_type = models.CharField(max_length=30, choices=MovementType.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, help_text="Use positivo para entrada e negativo para saida.")
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    work_order = models.ForeignKey(WorkOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name="stock_movements")
    notes = models.TextField(blank=True)
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="stock_movements")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.part} {self.quantity}"




class WorkOrderEvent(TimeStampedModel):
    class EventType(models.TextChoices):
        CREATED = "created", "Criada"
        UPDATED = "updated", "Atualizada"
        STATUS_CHANGED = "status_changed", "Status alterado"
        MESSAGE_SENT = "message_sent", "Mensagem enviada"
        PAYMENT_ADDED = "payment_added", "Pagamento registrado"
        INVENTORY_RESERVED = "inventory_reserved", "Estoque reservado"
        INVENTORY_RESERVATION_RELEASED = "inventory_reservation_released", "Reserva liberada"
        INVENTORY_CONSUMED = "inventory_consumed", "Estoque consumido"
        PURCHASE_NEEDED = "purchase_needed", "Necessidade de compra"
        PHOTO_ADDED = "photo_added", "Foto adicionada"
        SERVICE_STARTED = "service_started", "Servico iniciado"
        SERVICE_FINISHED = "service_finished", "Servico concluido"
        SERVICE_QUALITY_CHECKED = "service_quality_checked", "Servico conferido"
        CHECKLIST_UPDATED = "checklist_updated", "Checklist atualizado"
        DELIVERY_SIGNED = "delivery_signed", "Entrega assinada"
        NOTE = "note", "Nota"
        ERROR = "error", "Erro"

    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    old_status = models.CharField(max_length=30, blank=True)
    new_status = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_order_events")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.work_order} - {self.event_type}"




class WorkOrderCustomerApproval(TimeStampedModel):
    """Link público e auditável para aprovação digital de OS/orçamento pelo cliente."""

    class DocumentType(models.TextChoices):
        ESTIMATE = "estimate", "Orçamento"
        WORK_ORDER = "work_order", "Ordem de serviço"
        RECEIPT = "receipt", "Recibo"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        APPROVED = "approved", "Aprovado"
        REJECTED = "rejected", "Recusado"
        EXPIRED = "expired", "Expirado"

    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="customer_approvals")
    document_type = models.CharField(max_length=20, choices=DocumentType.choices, default=DocumentType.ESTIMATE, db_index=True)
    token = models.UUIDField(default=uuid4, unique=True, editable=False, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    requested_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="requested_work_order_approvals")
    requested_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    customer_name_snapshot = models.CharField(max_length=180, blank=True)
    customer_email_snapshot = models.EmailField(blank=True)
    customer_phone_snapshot = models.CharField(max_length=30, blank=True)
    decision_name = models.CharField(max_length=180, blank=True)
    decision_document = models.CharField(max_length=30, blank=True)
    decision_notes = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_ip = models.GenericIPAddressField(null=True, blank=True)
    decision_user_agent = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-requested_at", "-id"]
        indexes = [
            models.Index(fields=["work_order", "status"], name="wo_approval_status_idx"),
            models.Index(fields=["token", "status"], name="wo_approval_token_idx"),
        ]
        verbose_name = "aprovação digital de OS"
        verbose_name_plural = "aprovações digitais de OS"

    @property
    def document_type_label(self):
        return self.get_document_type_display()

    @property
    def status_label(self):
        current_status = self.effective_status
        return dict(self.Status.choices).get(current_status, current_status)

    @property
    def public_url_path(self):
        return f"/aprovar-os/{self.token}"

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

    def mark_decision(self, status, name="", document="", notes="", ip_address=None, user_agent=""):
        if status not in {self.Status.APPROVED, self.Status.REJECTED}:
            raise ValidationError({"status": "Decisão inválida para aprovação digital."})
        if not self.can_decide:
            raise ValidationError({"status": "Este link não está mais disponível para decisão."})
        document = (document or "").strip()
        notes = (notes or "").strip()
        digits = "".join(ch for ch in document if ch.isdigit())
        if len(digits) not in (11, 14):
            raise ValidationError({"document": "Informe um CPF com 11 dígitos ou CNPJ com 14 dígitos."})
        if not notes:
            raise ValidationError({"notes": "Informe uma observação para registrar a decisão."})
        self.status = status
        self.decision_name = (name or "").strip()[:180]
        self.decision_document = document[:30]
        self.decision_notes = notes
        self.decision_ip = ip_address
        self.decision_user_agent = (user_agent or "")[:2000]
        self.decided_at = timezone.now()
        self.save(update_fields=["status", "decision_name", "decision_document", "decision_notes", "decision_ip", "decision_user_agent", "decided_at", "updated_at"])
        return self

    def save(self, *args, **kwargs):
        if self.work_order_id and not self.customer_name_snapshot:
            self.customer_name_snapshot = self.work_order.customer.full_name
        if self.work_order_id and not self.customer_email_snapshot:
            self.customer_email_snapshot = self.work_order.customer.email or ""
        if self.work_order_id and not self.customer_phone_snapshot:
            self.customer_phone_snapshot = self.work_order.customer.phone_e164 or self.work_order.customer.secondary_phone_e164 or ""
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_document_type_display()} {self.work_order.number} - {self.status_label}"




class WorkOrderDeliverySignature(TimeStampedModel):
    """Assinatura digital de entrega da OS."""

    work_order = models.OneToOneField(WorkOrder, on_delete=models.CASCADE, related_name="delivery_signature")
    recipient_name = models.CharField(max_length=180)
    recipient_document = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)
    signature_image = models.FileField(
        upload_to=work_order_signature_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=IMAGE_EXTENSIONS)],
        verbose_name="Imagem da assinatura",
    )
    signed_at = models.DateTimeField(default=timezone.now)
    signed_ip = models.GenericIPAddressField(null=True, blank=True)
    signed_user_agent = models.TextField(blank=True)
    signed_by_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="signed_work_order_deliveries")

    class Meta:
        ordering = ["-signed_at"]
        verbose_name = "assinatura de entrega da OS"
        verbose_name_plural = "assinaturas de entrega da OS"

    @property
    def signature_url(self):
        return self.signature_image.url if self.signature_image else ""

    @property
    def signed_by_name(self):
        return self.signed_by_user.get_full_name() or self.signed_by_user.username if self.signed_by_user else ""

    def clean(self):
        super().clean()
        self.recipient_name = (self.recipient_name or "").strip()
        if not self.recipient_name:
            raise ValidationError({"recipient_name": "Informe o nome de quem recebeu o veículo/serviço."})
        if not self.signature_image:
            raise ValidationError({"signature_image": "A assinatura digital é obrigatória."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Entrega {self.work_order.number} - {self.recipient_name}"




class WorkOrderNotificationRule(TimeStampedModel):
    class EntityType(models.TextChoices):
        WORK_ORDER = "work_order", "Ordem de serviço"
        ESTIMATE = "estimate", "Orçamento"

    class RecipientTarget(models.TextChoices):
        CUSTOMER = "customer", "Cliente"
        WORKSHOP = "workshop", "Oficina"
        BOTH = "both", "Cliente e oficina"

    name = models.CharField(max_length=160)
    entity_type = models.CharField(max_length=30, choices=EntityType.choices, default=EntityType.WORK_ORDER, db_index=True, verbose_name="Tipo de documento")
    trigger_status = models.CharField(max_length=30, verbose_name="Status gatilho")
    channel = models.CharField(max_length=20, choices=MessageTemplate.Channel.choices)
    template = models.ForeignKey(MessageTemplate, on_delete=models.PROTECT, related_name="work_order_notification_rules")
    recipient_target = models.CharField(max_length=20, choices=RecipientTarget.choices, default=RecipientTarget.CUSTOMER, verbose_name="Enviar para")
    is_active = models.BooleanField(default=True)
    send_once_per_status = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_work_order_notification_rules")

    class Meta:
        ordering = ["entity_type", "trigger_status", "channel", "name"]

    @property
    def entity_type_label(self):
        return self.get_entity_type_display()

    @property
    def trigger_status_label(self):
        if self.entity_type == self.EntityType.WORK_ORDER:
            return dict(WorkOrder.Status.choices).get(self.trigger_status, self.trigger_status)
        if self.entity_type == self.EntityType.ESTIMATE:
            estimate_statuses = {
                "open": "Aberto",
                "diagnosis": "Em diagnostico",
                "awaiting_approval": "Aguardando aprovacao",
                "approved": "Aprovado",
                "partially_approved": "Aprovado parcialmente",
                "rejected": "Rejeitado",
                "expired": "Expirado",
                "converted": "Convertido em OS",
                "cancelled": "Cancelado",
            }
            return estimate_statuses.get(self.trigger_status, self.trigger_status)
        return self.trigger_status

    def clean(self):
        super().clean()
        if self.template_id and self.channel and self.template.channel != self.channel:
            raise ValidationError({"channel": "O canal da regra precisa ser igual ao canal do template."})
        if self.entity_type == self.EntityType.WORK_ORDER:
            valid_statuses = {value for value, _label in WorkOrder.Status.choices}
            if self.trigger_status not in valid_statuses:
                raise ValidationError({"trigger_status": "Status gatilho inválido para ordem de serviço."})
        elif self.entity_type == self.EntityType.ESTIMATE:
            valid_statuses = {"open", "diagnosis", "awaiting_approval", "approved", "partially_approved", "rejected", "expired", "converted", "cancelled"}
            if self.trigger_status not in valid_statuses:
                raise ValidationError({"trigger_status": "Status gatilho inválido para orçamento."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name




class WorkOrderMessage(TimeStampedModel):
    class TriggerType(models.TextChoices):
        MANUAL = "manual", "Manual"
        STATUS_AUTO = "status_auto", "Automatico por status"

    work_order = models.ForeignKey(WorkOrder, null=True, blank=True, on_delete=models.CASCADE, related_name="messages")
    estimate = models.ForeignKey("attendance.Estimate", null=True, blank=True, on_delete=models.CASCADE, related_name="messages")
    trigger_type = models.CharField(max_length=30, choices=TriggerType.choices, default=TriggerType.MANUAL)
    trigger_status = models.CharField(max_length=30, blank=True)
    channel = models.CharField(max_length=20, choices=MessageTemplate.Channel.choices)
    recipient_target = models.CharField(max_length=20, blank=True)
    template = models.ForeignKey(MessageTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_order_messages")
    notification_rule = models.ForeignKey(WorkOrderNotificationRule, null=True, blank=True, on_delete=models.SET_NULL, related_name="messages")
    message_log = models.ForeignKey(MessageLog, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_order_messages")
    status = models.CharField(max_length=20, blank=True)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_work_order_messages")

    class Meta:
        ordering = ["-created_at"]

    @property
    def document_type(self):
        return WorkOrderNotificationRule.EntityType.ESTIMATE if self.estimate_id else WorkOrderNotificationRule.EntityType.WORK_ORDER

    @property
    def document_number(self):
        if self.work_order_id:
            return self.work_order.number
        if self.estimate_id:
            return self.estimate.number
        return ""

    def clean(self):
        super().clean()
        if bool(self.work_order_id) == bool(self.estimate_id):
            raise ValidationError("A mensagem deve estar vinculada a uma OS ou a um orçamento, mas não aos dois ao mesmo tempo.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        document = self.work_order or self.estimate or "mensagem"
        return f"{document} - {self.channel} - {self.status}"
