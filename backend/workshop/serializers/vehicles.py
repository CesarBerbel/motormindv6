from .common import *

class VehicleSerializer(serializers.ModelSerializer):
    customer_id = serializers.PrimaryKeyRelatedField(source="customer", queryset=Contact.objects.all(), write_only=True)
    customer = ContactSerializer(read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    display_name = serializers.CharField(read_only=True)
    has_fipe_link = serializers.BooleanField(read_only=True)
    steering_type_label = serializers.CharField(read_only=True)
    transmission_type_label = serializers.CharField(read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "customer",
            "customer_id",
            "customer_name",
            "plate",
            "make",
            "model",
            "version",
            "year",
            "color",
            "vin",
            "odometer_km",
            "steering_type",
            "steering_type_label",
            "has_air_conditioning",
            "door_count",
            "transmission_type",
            "transmission_type_label",
            "is_modified",
            "fipe_brand_code",
            "fipe_model_code",
            "fipe_year_code",
            "has_fipe_link",
            "notes",
            "is_active",
            "display_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "customer", "customer_name", "has_fipe_link", "steering_type_label", "transmission_type_label", "display_name", "created_at", "updated_at"]

    def validate_plate(self, value):
        return (value or "").strip().upper().replace("-", "").replace(" ", "")

    def validate_make(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Informe a marca do veículo.")
        return value

    def validate_model(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Informe o modelo do veículo.")
        return value

    def validate_vin(self, value):
        return (value or "").strip().upper()

    def validate_steering_type(self, value):
        return (value or "").strip()

    def validate_transmission_type(self, value):
        return (value or "").strip()

    def validate_door_count(self, value):
        if value in (None, ""):
            return None
        if int(value) < 0 or int(value) > 10:
            raise serializers.ValidationError("Informe uma quantidade de portas entre 0 e 10.")
        return value

    def validate_fipe_brand_code(self, value):
        return (value or "").strip()

    def validate_fipe_model_code(self, value):
        return (value or "").strip()

    def validate_fipe_year_code(self, value):
        return (value or "").strip()

    def validate(self, attrs):
        fipe_brand_code = attrs.get("fipe_brand_code", getattr(self.instance, "fipe_brand_code", ""))
        fipe_model_code = attrs.get("fipe_model_code", getattr(self.instance, "fipe_model_code", ""))
        fipe_year_code = attrs.get("fipe_year_code", getattr(self.instance, "fipe_year_code", ""))

        if fipe_model_code and not fipe_brand_code:
            raise serializers.ValidationError({"fipe_model_code": "Para salvar modelo FIPE, informe também a marca FIPE."})
        if fipe_year_code and not fipe_model_code:
            raise serializers.ValidationError({"fipe_year_code": "Para salvar ano/versão FIPE, informe também o modelo FIPE."})
        return attrs


