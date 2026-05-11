from django import forms
from django.contrib import admin

from .models import AIProviderConfiguration, AIPrompt


class AIProviderConfigurationAdminForm(forms.ModelForm):
    api_key = forms.CharField(
        label="API key",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text=(
            "Informe uma nova chave para substituir a atual. "
            "Deixe em branco para manter a chave existente."
        ),
    )
    clear_api_key = forms.BooleanField(
        label="Remover API key atual",
        required=False,
        help_text="Marque apenas se deseja apagar a chave salva.",
    )

    class Meta:
        model = AIProviderConfiguration
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_api_key = self.instance.api_key if self.instance and self.instance.pk else ""

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("clear_api_key") and cleaned_data.get("api_key"):
            raise forms.ValidationError("Escolha remover a chave atual ou informar uma nova chave, não ambos.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        new_api_key = self.cleaned_data.get("api_key") or ""
        if self.cleaned_data.get("clear_api_key"):
            instance.api_key = ""
        elif new_api_key:
            instance.api_key = new_api_key
        elif self.instance and self.instance.pk:
            instance.api_key = self._original_api_key
        if commit:
            instance.save()
            self.save_m2m()
        return instance


@admin.register(AIProviderConfiguration)
class AIProviderConfigurationAdmin(admin.ModelAdmin):
    form = AIProviderConfigurationAdminForm
    list_display = ('provider', 'display_name', 'model_name', 'is_enabled', 'is_default', 'api_key_configured', 'max_tokens', 'updated_at')
    list_filter = ('provider', 'is_enabled', 'is_default')
    search_fields = ('display_name', 'model_name')
    readonly_fields = ('api_key_configured',)
    fieldsets = (
        ('Provedor', {'fields': ('provider', 'display_name', 'is_enabled', 'is_default')}),
        ('Credenciais e modelo', {'fields': ('api_key_configured', 'api_key', 'clear_api_key', 'model_name', 'base_url')}),
        ('Comportamento', {'fields': ('temperature', 'max_tokens', 'system_prompt')}),
    )

    @admin.display(description='API key configurada')
    def api_key_configured(self, obj):
        return bool(obj and obj.api_key)


@admin.register(AIPrompt)
class AIPromptAdmin(admin.ModelAdmin):
    list_display = ('name', 'task', 'is_active', 'is_default', 'updated_at')
    list_filter = ('task', 'is_active', 'is_default')
    search_fields = ('name', 'description', 'prompt')
    fieldsets = (
        ('Identificação', {'fields': ('name', 'task', 'description', 'is_active', 'is_default')}),
        ('Prompt', {'fields': ('prompt',)}),
    )
