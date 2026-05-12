from .common import *

class GeneralCategory(TimeStampedModel):
    class CategoryType(models.TextChoices):
        GENERAL = "general", "Geral"
        SERVICE = "service", "Serviço"
        PART = "part", "Peça / estoque"
        VEHICLE = "vehicle", "Veículo"
        WORK_ORDER = "work_order", "Ordem de serviço"

    type = models.CharField(max_length=40, choices=CategoryType.choices, default=CategoryType.GENERAL, db_index=True)
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["type", "name"]
        constraints = [
            models.UniqueConstraint(fields=["type", "name"], name="general_category_type_name_uniq"),
            models.UniqueConstraint(fields=["type", "code"], condition=~models.Q(code=""), name="general_category_type_code_uniq"),
        ]

    @property
    def type_label(self):
        return self.get_type_display()

    def __str__(self):
        return f"{self.get_type_display()} - {self.name}"




class PartBrand(TimeStampedModel):
    class Source(models.TextChoices):
        SEED = "seed", "Carga inicial"
        MANUAL = "manual", "Cadastro manual"

    name = models.CharField(max_length=120)
    normalized_name = models.CharField(max_length=120, unique=True, editable=False, db_index=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "marca de peça"
        verbose_name_plural = "marcas de peças"

    @classmethod
    def get_or_create_from_name(cls, name, source=None):
        clean_name = (name or "").strip()
        if not clean_name:
            return None, False
        normalized = normalize_lookup_name(clean_name)
        defaults = {"name": clean_name, "source": source or cls.Source.MANUAL, "is_active": True}
        brand, created = cls.objects.get_or_create(normalized_name=normalized, defaults=defaults)
        if not brand.is_active:
            brand.is_active = True
            brand.save(update_fields=["is_active", "updated_at"])
        return brand, created

    def clean(self):
        super().clean()
        self.name = (self.name or "").strip()
        self.normalized_name = normalize_lookup_name(self.name)
        if not self.name:
            raise ValidationError({"name": "Informe o nome da marca."})
        if not self.normalized_name:
            raise ValidationError({"name": "Informe uma marca válida."})

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip()
        self.normalized_name = normalize_lookup_name(self.name)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name




class WorkshopService(TimeStampedModel):
    code = models.CharField(max_length=40, unique=True, blank=True, null=True)
    name = models.CharField(max_length=160)
    category = models.ForeignKey(GeneralCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="workshop_services", limit_choices_to={"type": GeneralCategory.CategoryType.SERVICE})
    legacy_category_name = models.CharField(max_length=100, blank=True)
    photo = models.FileField(
        upload_to=service_photo_upload_path,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=IMAGE_EXTENSIONS)],
        verbose_name="Foto/thumbnail do serviço",
    )
    description = models.TextField(blank=True)
    default_unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    is_featured = models.BooleanField(default=False, db_index=True, verbose_name="Mais usado/preferido na OS")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category__name", "name"]

    @property
    def category_name(self):
        return self.category.name if self.category else self.legacy_category_name

    @property
    def photo_url(self):
        return self.photo.url if self.photo else ""

    @classmethod
    def generate_code(cls):
        return generate_prefixed_sequence_code(cls, "SRV")

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_code()
        else:
            self.code = str(self.code).strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name






class WorkshopServiceChecklistTemplate(TimeStampedModel):
    """Checklist padrão configurado no cadastro de um serviço."""

    service = models.ForeignKey(WorkshopService, on_delete=models.CASCADE, related_name="checklist_templates")
    description = models.CharField(max_length=220)
    is_required = models.BooleanField(default=True)
    requires_photo = models.BooleanField(default=False)
    requires_note = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "item de checklist padrão"
        verbose_name_plural = "itens de checklist padrão"

    def clean(self):
        super().clean()
        self.description = (self.description or "").strip()
        if not self.description:
            raise ValidationError({"description": "Informe a descrição do item do checklist."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.service} - {self.description}"




class ServicePackage(TimeStampedModel):
    code = models.CharField(max_length=40, unique=True, blank=True, null=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    @property
    def subtotal_amount(self):
        return sum((item.subtotal_amount for item in self.items.all()), ZERO)

    @property
    def total_amount(self):
        total = self.subtotal_amount - (self.discount_amount or ZERO)
        return total if total > ZERO else ZERO

    @classmethod
    def generate_code(cls):
        return generate_prefixed_sequence_code(cls, "PCT")

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_code()
        else:
            self.code = str(self.code).strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name




class ServicePackageItem(TimeStampedModel):
    service_package = models.ForeignKey(ServicePackage, on_delete=models.CASCADE, related_name="items")
    service = models.ForeignKey(WorkshopService, null=True, blank=True, on_delete=models.SET_NULL, related_name="package_items")
    description = models.CharField(max_length=220)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"), validators=[MinValueValidator(Decimal("0.01"))])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    @property
    def subtotal_amount(self):
        return (self.quantity or ZERO) * (self.unit_price or ZERO)

    @property
    def total_amount(self):
        return self.subtotal_amount

    def save(self, *args, **kwargs):
        if self.service:
            if not self.description:
                self.description = self.service.name
            if not self.unit_price:
                self.unit_price = self.service.default_unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.service_package} - {self.description}"




class Part(TimeStampedModel):
    sku = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=160)
    category = models.ForeignKey(GeneralCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="parts", limit_choices_to={"type": GeneralCategory.CategoryType.PART})
    brand = models.CharField(max_length=100, blank=True)
    photo = models.FileField(
        upload_to=part_photo_upload_path,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=IMAGE_EXTENSIONS)],
        verbose_name="Foto da peça",
    )
    location = models.CharField(max_length=80, blank=True)
    unit = models.CharField(max_length=20, default="un", verbose_name="Unidade de medida")
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    stock_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    reserved_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    minimum_stock = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    is_featured = models.BooleanField(default=False, db_index=True, verbose_name="Mais usada/preferida na OS")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["category__name", "name", "sku"]

    @property
    def category_name(self):
        return self.category.name if self.category else ""

    @property
    def is_low_stock(self):
        return self.available_quantity <= self.minimum_stock

    @property
    def available_quantity(self):
        available = (self.stock_quantity or ZERO) - (self.reserved_quantity or ZERO)
        return available if available > ZERO else ZERO

    @property
    def stock_value(self):
        return (self.stock_quantity or ZERO) * (self.cost_price or ZERO)

    @classmethod
    def generate_sku(cls):
        existing = cls.objects.filter(sku__startswith="PCA-").values_list("sku", flat=True)
        last_number = 0
        pattern = re.compile(r"^PCA-(\d+)$", re.IGNORECASE)
        for sku in existing:
            match = pattern.match(str(sku or "").strip())
            if not match:
                continue
            try:
                last_number = max(last_number, int(match.group(1)))
            except ValueError:
                continue
        return f"PCA-{last_number + 1:05d}"

    def clean(self):
        super().clean()
        self.unit = normalize_part_unit(self.unit)
        allowed_units = {value for value, _label in PART_UNIT_CHOICES}
        if self.unit not in allowed_units:
            raise ValidationError({"unit": "Selecione uma unidade cadastrada na lista controlada."})

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = self.generate_sku()
        else:
            self.sku = str(self.sku).strip().upper()
        self.unit = normalize_part_unit(self.unit)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sku} - {self.name}"


class ServiceDefaultPart(TimeStampedModel):
    """Peça padrão sugerida automaticamente quando um serviço é usado em OS ou orçamento."""

    service = models.ForeignKey(WorkshopService, on_delete=models.CASCADE, related_name="default_parts")
    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name="default_service_links")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"), validators=[MinValueValidator(Decimal("0.01"))])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    consume_inventory = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["service", "part"], name="service_default_part_unique"),
        ]
        verbose_name = "peça padrão do serviço"
        verbose_name_plural = "peças padrão dos serviços"

    @property
    def part_name(self):
        return self.part.name if self.part_id else ""

    @property
    def part_sku(self):
        return self.part.sku if self.part_id else ""

    @property
    def effective_unit_price(self):
        return self.unit_price if self.unit_price else self.part.sale_price

    @property
    def total_amount(self):
        total = (self.quantity or ZERO) * (self.effective_unit_price or ZERO) - (self.discount_amount or ZERO)
        return total if total > ZERO else ZERO

    def clean(self):
        super().clean()
        if self.discount_amount and self.discount_amount > (self.quantity or ZERO) * (self.effective_unit_price or ZERO):
            raise ValidationError({"discount_amount": "Desconto da peça padrão não pode ser maior que o subtotal."})

    def save(self, *args, **kwargs):
        if self.part_id and not self.unit_price:
            self.unit_price = self.part.sale_price
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.service} -> {self.part} ({self.quantity})"

