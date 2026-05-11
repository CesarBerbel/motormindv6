from .common import *
from .catalog import WorkshopServiceSerializer

class WorkshopProfileSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    address_display = serializers.CharField(read_only=True)
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = WorkshopProfile
        fields = [
            "id",
            "legal_name",
            "trade_name",
            "display_name",
            "document_number",
            "state_registration",
            "municipal_registration",
            "logo",
            "logo_url",
            "email",
            "phone_e164",
            "secondary_phone_e164",
            "website",
            "zip_code",
            "address_line",
            "address_number",
            "address_complement",
            "district",
            "city",
            "state",
            "country",
            "address_display",
            "responsible_name",
            "print_header_text",
            "print_footer_text",
            "estimate_terms",
            "work_order_terms",
            "purchase_order_terms",
            "bank_info",
            "pix_key",
            "technical_checklist_enabled",
            "delivery_signature_enabled",
            "landing_enabled",
            "landing_headline",
            "landing_subheadline",
            "landing_cta_label",
            "landing_highlight_text",
            "ui_theme_mode",
            "ui_primary_color",
            "ui_accent_color",
            "ui_sidebar_color",
            "ui_form_density",
            "ui_table_density",
            "ui_card_radius",
            "ui_button_style",
            "ui_form_layout",
            "ui_show_required_hint",
            "ui_enable_motion",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "display_name", "address_display", "logo_url", "created_at", "updated_at"]

    def get_logo_url(self, obj):
        if not obj.logo:
            return ""
        return obj.logo.url

    def validate_legal_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Informe a razão social ou nome principal da oficina.")
        return value

    def validate_document_number(self, value):
        digits = "".join(ch for ch in (value or "") if ch.isdigit())
        if digits and len(digits) not in (11, 14):
            raise serializers.ValidationError("Informe CPF com 11 dígitos ou CNPJ com 14 dígitos.")
        return format_cpf_cnpj(digits) if digits else ""

    def validate_zip_code(self, value):
        digits = "".join(ch for ch in (value or "") if ch.isdigit())
        if digits and len(digits) != 8:
            raise serializers.ValidationError("Informe CEP com 8 dígitos.")
        return format_cep(digits) if digits else ""

    def validate_phone_e164(self, value):
        return normalize_br_phone_e164(value) if value else ""

    def validate_secondary_phone_e164(self, value):
        return normalize_br_phone_e164(value) if value else ""

    def validate_state(self, value):
        return (value or "").strip().upper()[:2]

    def validate_logo(self, value):
        if value and value.size > 3 * 1024 * 1024:
            raise serializers.ValidationError("A logomarca deve ter no máximo 3 MB.")
        return value

    def _validate_hex_color(self, value, field_label):
        import re
        value = (value or "").strip()
        if not value:
            return ""
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise serializers.ValidationError(f"{field_label} deve estar no formato hexadecimal #RRGGBB.")
        return value.upper()

    def validate_ui_primary_color(self, value):
        return self._validate_hex_color(value, "Cor primária") or "#0D6EFD"

    def validate_ui_accent_color(self, value):
        return self._validate_hex_color(value, "Cor de destaque") or "#FD7E14"

    def validate_ui_sidebar_color(self, value):
        return self._validate_hex_color(value, "Cor do menu lateral") or "#172033"


class PublicLandingSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    address_display = serializers.CharField(read_only=True)
    logo_url = serializers.SerializerMethodField()
    featured_services = serializers.SerializerMethodField()

    class Meta:
        model = WorkshopProfile
        fields = [
            "display_name",
            "legal_name",
            "trade_name",
            "logo_url",
            "email",
            "phone_e164",
            "secondary_phone_e164",
            "website",
            "address_display",
            "landing_enabled",
            "landing_headline",
            "landing_subheadline",
            "landing_cta_label",
            "landing_highlight_text",
            "featured_services",
        ]

    def get_logo_url(self, obj):
        if not obj.logo:
            return ""
        return obj.logo.url

    def get_featured_services(self, obj):
        request = self.context.get("request")
        services = WorkshopService.objects.filter(is_active=True, is_featured=True).order_by("name")[:6]
        return WorkshopServiceSerializer(services, many=True, context={"request": request}).data


