from django import forms
from django.contrib import admin

from .models import Automation, ChannelConfiguration, Contact, ContactGroup, MessageLog, MessageTemplate


class ChannelConfigurationAdminForm(forms.ModelForm):
    whatsapp_access_token = forms.CharField(
        label="Token de acesso WhatsApp",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text=(
            "Informe um novo token para substituir o atual. "
            "Deixe em branco para manter o token existente."
        ),
    )
    clear_whatsapp_access_token = forms.BooleanField(
        label="Remover token WhatsApp atual",
        required=False,
        help_text="Marque apenas se deseja apagar o token salvo.",
    )

    class Meta:
        model = ChannelConfiguration
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_whatsapp_access_token = self.instance.whatsapp_access_token if self.instance and self.instance.pk else ""

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("clear_whatsapp_access_token") and cleaned_data.get("whatsapp_access_token"):
            raise forms.ValidationError("Escolha remover o token atual ou informar um novo token, não ambos.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        new_token = self.cleaned_data.get("whatsapp_access_token") or ""
        if self.cleaned_data.get("clear_whatsapp_access_token"):
            instance.whatsapp_access_token = ""
        elif new_token:
            instance.whatsapp_access_token = new_token
        elif self.instance and self.instance.pk:
            instance.whatsapp_access_token = self._original_whatsapp_access_token
        if commit:
            instance.save()
            self.save_m2m()
        return instance


@admin.register(ChannelConfiguration)
class ChannelConfigurationAdmin(admin.ModelAdmin):
    form = ChannelConfigurationAdminForm
    readonly_fields = ("whatsapp_token_configured",)
    fieldsets = (
        ("Email", {"fields": ("email_enabled", "default_from_email")}),
        (
            "WhatsApp",
            {
                "fields": (
                    "whatsapp_enabled",
                    "whatsapp_provider",
                    "whatsapp_token_configured",
                    "whatsapp_access_token",
                    "clear_whatsapp_access_token",
                    "whatsapp_phone_number_id",
                    "whatsapp_api_version",
                    "whatsapp_preview_url",
                )
            },
        ),
    )

    @admin.display(description="Token WhatsApp configurado")
    def whatsapp_token_configured(self, obj):
        return bool(obj and obj.whatsapp_access_token)

    def has_add_permission(self, request):
        return not ChannelConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "channel", "is_active", "updated_at")
    list_filter = ("channel", "is_active")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ("channel", "recipient_name", "to_email", "to_phone", "status", "sent_at", "created_at")
    list_filter = ("channel", "status")
    search_fields = ("recipient_name", "to_email", "to_phone", "rendered_subject", "error_message")
    readonly_fields = [field.name for field in MessageLog._meta.fields]


admin.site.register(Contact)
admin.site.register(ContactGroup)
admin.site.register(Automation)
