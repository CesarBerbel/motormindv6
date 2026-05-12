from .common import *

class WorkshopServiceChecklistTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkshopServiceChecklistTemplate
        fields = ["id", "service", "description", "is_required", "requires_photo", "requires_note", "sort_order", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_description(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Informe a descrição do item do checklist.")
        return value




class GeneralCategorySerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(read_only=True)

    class Meta:
        model = GeneralCategory
        fields = ["id", "type", "type_label", "code", "name", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "type_label", "created_at", "updated_at"]

    def validate_code(self, value):
        return (value or "").strip().upper()

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Informe o nome da categoria.")
        return value




class PartBrandSerializer(serializers.ModelSerializer):
    source_label = serializers.CharField(source="get_source_display", read_only=True)

    class Meta:
        model = PartBrand
        fields = ["id", "name", "normalized_name", "source", "source_label", "is_active", "notes", "created_at", "updated_at"]
        read_only_fields = ["id", "normalized_name", "source_label", "created_at", "updated_at"]

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Informe o nome da marca.")
        normalized = normalize_lookup_name(value)
        queryset = PartBrand.objects.filter(normalized_name=normalized)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Já existe uma marca com este nome normalizado.")
        return value




class ServiceDefaultPartSerializer(serializers.ModelSerializer):
    part_id = serializers.PrimaryKeyRelatedField(source="part", queryset=Part.objects.filter(is_active=True), required=True, write_only=True)
    part_name = serializers.CharField(read_only=True)
    part_sku = serializers.CharField(read_only=True)
    part_unit = serializers.CharField(source="part.unit", read_only=True)
    part_brand = serializers.CharField(source="part.brand", read_only=True)
    part_sale_price = serializers.DecimalField(source="part.sale_price", max_digits=12, decimal_places=2, read_only=True)
    part_cost_price = serializers.DecimalField(source="part.cost_price", max_digits=12, decimal_places=2, read_only=True)
    part_stock_quantity = serializers.DecimalField(source="part.stock_quantity", max_digits=12, decimal_places=2, read_only=True)
    effective_unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ServiceDefaultPart
        fields = [
            "id",
            "service",
            "part",
            "part_id",
            "part_name",
            "part_sku",
            "part_unit",
            "part_brand",
            "part_sale_price",
            "part_cost_price",
            "part_stock_quantity",
            "quantity",
            "unit_price",
            "effective_unit_price",
            "discount_amount",
            "consume_inventory",
            "notes",
            "position",
            "is_active",
            "total_amount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "part",
            "part_name",
            "part_sku",
            "part_unit",
            "part_brand",
            "part_sale_price",
            "part_cost_price",
            "part_stock_quantity",
            "effective_unit_price",
            "total_amount",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        service = attrs.get("service", getattr(self.instance, "service", None))
        part = attrs.get("part", getattr(self.instance, "part", None))
        if service and part:
            queryset = ServiceDefaultPart.objects.filter(service=service, part=part)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({"part_id": "Esta peça já está vinculada como padrão deste serviço."})
        quantity = attrs.get("quantity", getattr(self.instance, "quantity", Decimal("1.00")))
        unit_price = attrs.get("unit_price", getattr(self.instance, "unit_price", ZERO))
        discount_amount = attrs.get("discount_amount", getattr(self.instance, "discount_amount", ZERO))
        if part and not unit_price:
            unit_price = part.sale_price
        if discount_amount and discount_amount > (quantity or ZERO) * (unit_price or ZERO):
            raise serializers.ValidationError({"discount_amount": "Desconto da peça padrão não pode ser maior que o subtotal."})
        return attrs



class WorkshopServiceSerializer(serializers.ModelSerializer):
    checklist_templates = WorkshopServiceChecklistTemplateSerializer(many=True, read_only=True)
    default_parts = ServiceDefaultPartSerializer(many=True, read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(source="category", queryset=GeneralCategory.objects.filter(type=GeneralCategory.CategoryType.SERVICE, is_active=True), required=False, allow_null=True, write_only=True)
    category_name = serializers.CharField(read_only=True)
    photo_url = serializers.SerializerMethodField()
    remove_photo = serializers.BooleanField(write_only=True, required=False, default=False)
    usage_count = serializers.SerializerMethodField()

    def get_photo_url(self, obj):
        if not obj.photo:
            return ""
        return obj.photo.url

    def get_usage_count(self, obj):
        return int(getattr(obj, "usage_count", 0) or 0)

    def validate_code(self, value):
        value = (value or "").strip().upper()
        return value or None

    def validate_photo(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("A foto do serviço deve ter no máximo 5 MB.")
        return value

    def validate_is_featured(self, value):
        return bool(value)

    def create(self, validated_data):
        validated_data.pop("remove_photo", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        remove_photo = validated_data.pop("remove_photo", False)
        if remove_photo and instance.photo:
            instance.photo.delete(save=False)
            validated_data["photo"] = ""
        return super().update(instance, validated_data)

    class Meta:
        model = WorkshopService
        fields = ["id", "code", "name", "category", "category_id", "category_name", "legacy_category_name", "photo", "photo_url", "remove_photo", "description", "default_unit_price", "estimated_hours", "is_featured", "usage_count", "checklist_templates", "default_parts", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "category", "category_name", "photo_url", "usage_count", "checklist_templates", "default_parts", "created_at", "updated_at"]






class ServicePackageItemSerializer(serializers.ModelSerializer):
    service_id = serializers.PrimaryKeyRelatedField(source="service", queryset=WorkshopService.objects.all(), required=False, allow_null=True, write_only=True)
    service_code = serializers.CharField(source="service.code", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    service_category_name = serializers.CharField(source="service.category_name", read_only=True)
    subtotal_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ServicePackageItem
        fields = ["id", "service", "service_id", "service_code", "service_name", "service_category_name", "description", "quantity", "unit_price", "position", "subtotal_amount", "total_amount", "created_at", "updated_at"]
        read_only_fields = ["id", "service", "service_code", "service_name", "service_category_name", "subtotal_amount", "total_amount", "created_at", "updated_at"]

    def validate(self, attrs):
        service = attrs.get("service")
        if service:
            attrs.setdefault("description", service.name)
            attrs.setdefault("unit_price", service.default_unit_price)
        if not attrs.get("description") and not getattr(self.instance, "description", ""):
            raise serializers.ValidationError({"description": "Informe a descricao do item do pacote."})
        return attrs




class ServicePackageSerializer(serializers.ModelSerializer):
    items = ServicePackageItemSerializer(many=True, required=False)
    subtotal_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.00"), default=Decimal("0.00"), required=False)
    discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0.00"), max_value=Decimal("100.00"), required=False, default=Decimal("0.00"))
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ServicePackage
        fields = ["id", "code", "name", "description", "is_active", "items", "subtotal_amount", "discount_amount", "discount_percent", "total_amount", "created_at", "updated_at"]
        read_only_fields = ["id", "subtotal_amount", "total_amount", "created_at", "updated_at"]

    def validate_code(self, value):
        value = (value or "").strip().upper()
        return value or None

    def _discount_amount_from_percent(self, package, percent):
        percent = Decimal(str(percent or "0"))
        subtotal = package.subtotal_amount or ZERO
        return (subtotal * percent / Decimal("100")).quantize(Decimal("0.01"))

    def _apply_discount_percent(self, package, percent):
        package.discount_amount = self._discount_amount_from_percent(package, percent)
        package.save(update_fields=["discount_amount", "updated_at"])

    def to_representation(self, instance):
        data = super().to_representation(instance)
        subtotal = instance.subtotal_amount or ZERO
        if subtotal > ZERO:
            percent = ((instance.discount_amount or ZERO) * Decimal("100") / subtotal).quantize(Decimal("0.01"))
        else:
            percent = ZERO
        data["discount_percent"] = str(percent)
        return data

    def _sync_items(self, package, items_data):
        package.items.all().delete()
        for index, item_data in enumerate(items_data, start=1):
            position = item_data.pop("position", None) or index
            ServicePackageItem.objects.create(service_package=package, position=position, **item_data)

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        discount_percent = validated_data.pop("discount_percent", None)
        if discount_percent is not None:
            validated_data.pop("discount_amount", None)
        package = ServicePackage.objects.create(**validated_data)
        self._sync_items(package, items_data)
        if discount_percent is not None:
            self._apply_discount_percent(package, discount_percent)
        return package

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        discount_percent = validated_data.pop("discount_percent", None)
        if discount_percent is not None:
            validated_data.pop("discount_amount", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if items_data is not None:
            self._sync_items(instance, items_data)
        if discount_percent is not None:
            self._apply_discount_percent(instance, discount_percent)
        return instance




class PartSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(source="category", queryset=GeneralCategory.objects.filter(type=GeneralCategory.CategoryType.PART, is_active=True), required=False, allow_null=True, write_only=True)
    category_name = serializers.CharField(read_only=True)
    brand_normalized_name = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    remove_photo = serializers.BooleanField(write_only=True, required=False, default=False)
    is_low_stock = serializers.BooleanField(read_only=True)
    available_quantity = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    stock_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    usage_count = serializers.SerializerMethodField()
    unit_label = serializers.SerializerMethodField()

    def get_usage_count(self, obj):
        return int(getattr(obj, "usage_count", 0) or 0)

    def get_unit_label(self, obj):
        unit = normalize_part_unit(obj.unit)
        labels = dict(PART_UNIT_CHOICES)
        return labels.get(unit, unit)

    class Meta:
        model = Part
        fields = ["id", "sku", "name", "category", "category_id", "category_name", "brand", "brand_normalized_name", "photo", "photo_url", "remove_photo", "location", "unit", "unit_label", "cost_price", "sale_price", "stock_quantity", "reserved_quantity", "available_quantity", "minimum_stock", "is_low_stock", "stock_value", "is_featured", "usage_count", "is_active", "notes", "created_at", "updated_at"]
        read_only_fields = ["id", "category", "category_name", "brand_normalized_name", "photo_url", "unit_label", "stock_quantity", "reserved_quantity", "available_quantity", "minimum_stock", "is_low_stock", "stock_value", "usage_count", "created_at", "updated_at"]
        extra_kwargs = {"sku": {"required": False, "allow_blank": True}}

    def get_brand_normalized_name(self, obj):
        return normalize_lookup_name(obj.brand) if obj.brand else ""

    def get_photo_url(self, obj):
        if not obj.photo:
            return ""
        return obj.photo.url

    def validate_photo(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("A foto da peça deve ter no máximo 5 MB.")
        return value

    def validate_sku(self, value):
        return (value or "").strip().upper()

    def validate_unit(self, value):
        normalized = normalize_part_unit(value)
        allowed_units = {unit_value for unit_value, _label in PART_UNIT_CHOICES}
        if normalized not in allowed_units:
            raise serializers.ValidationError("Selecione uma unidade cadastrada na lista controlada.")
        return normalized

    def validate_is_featured(self, value):
        return bool(value)

    def validate_brand(self, value):
        return (value or "").strip()

    def _sync_brand(self, validated_data):
        if "brand" not in validated_data:
            return
        brand_name = (validated_data.get("brand") or "").strip()
        if not brand_name:
            validated_data["brand"] = ""
            return
        brand, _ = PartBrand.get_or_create_from_name(brand_name)
        validated_data["brand"] = brand.name

    def create(self, validated_data):
        validated_data.pop("remove_photo", None)
        if not validated_data.get("sku"):
            validated_data["sku"] = Part.generate_sku()
        self._sync_brand(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        remove_photo = validated_data.pop("remove_photo", False)
        if remove_photo and instance.photo:
            instance.photo.delete(save=False)
            validated_data["photo"] = ""
        self._sync_brand(validated_data)
        return super().update(instance, validated_data)




class PartStockMovementSerializer(serializers.ModelSerializer):
    part_name = serializers.CharField(source="part.name", read_only=True)
    work_order_number = serializers.CharField(source="work_order.number", read_only=True)
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = PartStockMovement
        fields = ["id", "part", "part_name", "movement_type", "quantity", "unit_cost", "work_order", "work_order_number", "notes", "actor_name", "created_at"]
        read_only_fields = fields

    def get_actor_name(self, obj):
        return obj.actor.get_full_name() or obj.actor.username if obj.actor else ""




class StockAdjustmentSerializer(serializers.Serializer):
    movement_type = serializers.ChoiceField(choices=[(PartStockMovement.MovementType.PURCHASE, "Entrada/compra"), (PartStockMovement.MovementType.ADJUSTMENT, "Ajuste"), (PartStockMovement.MovementType.REVERSAL, "Estorno")], default=PartStockMovement.MovementType.ADJUSTMENT)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_quantity(self, value):
        if value == Decimal("0.00"):
            raise serializers.ValidationError("Quantidade nao pode ser zero.")
        return value


