from .common import *

class WorkshopProfile(TimeStampedModel):
    """Cadastro singleton da oficina usado no layout e em documentos imprimíveis."""

    legal_name = models.CharField(max_length=180, verbose_name="Razão social")
    trade_name = models.CharField(max_length=180, blank=True, verbose_name="Nome fantasia")
    document_number = models.CharField(max_length=18, blank=True, db_index=True, verbose_name="CNPJ/CPF")
    state_registration = models.CharField(max_length=40, blank=True, verbose_name="Inscrição estadual")
    municipal_registration = models.CharField(max_length=40, blank=True, verbose_name="Inscrição municipal")
    logo = models.FileField(
        upload_to=workshop_logo_upload_path,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=IMAGE_EXTENSIONS_WITH_SVG)],
        verbose_name="Logomarca",
    )
    email = models.EmailField(blank=True)
    phone_e164 = models.CharField(max_length=20, blank=True, verbose_name="Telefone principal / WhatsApp")
    secondary_phone_e164 = models.CharField(max_length=20, blank=True, verbose_name="Telefone secundário")
    website = models.URLField(blank=True)
    zip_code = models.CharField(max_length=9, blank=True, verbose_name="CEP")
    address_line = models.CharField(max_length=180, blank=True, verbose_name="Endereço")
    address_number = models.CharField(max_length=20, blank=True, verbose_name="Número")
    address_complement = models.CharField(max_length=120, blank=True, verbose_name="Complemento")
    district = models.CharField(max_length=120, blank=True, verbose_name="Bairro")
    city = models.CharField(max_length=120, blank=True, verbose_name="Cidade")
    state = models.CharField(max_length=2, blank=True, verbose_name="UF")
    country = models.CharField(max_length=80, default="Brasil", blank=True, verbose_name="País")
    responsible_name = models.CharField(max_length=120, blank=True, verbose_name="Responsável técnico/administrativo")
    print_header_text = models.CharField(max_length=220, blank=True, verbose_name="Texto do cabeçalho de impressão")
    print_footer_text = models.TextField(blank=True, verbose_name="Rodapé padrão de impressão")
    estimate_terms = models.TextField(blank=True, verbose_name="Condições padrão para orçamentos")
    work_order_terms = models.TextField(blank=True, verbose_name="Condições padrão para ordens de serviço")
    purchase_order_terms = models.TextField(blank=True, verbose_name="Condições padrão para pedidos de compra")
    bank_info = models.TextField(blank=True, verbose_name="Dados bancários para impressão")
    pix_key = models.CharField(max_length=120, blank=True, verbose_name="Chave Pix")
    technical_checklist_enabled = models.BooleanField(default=False, verbose_name="Usar checklist técnico nas OS")
    delivery_signature_enabled = models.BooleanField(default=True, verbose_name="Usar assinatura digital na entrega")
    delivery_with_pending_payment_allowed = models.BooleanField(default=False, verbose_name="Permitir entrega de veículo com pagamento pendente")
    landing_enabled = models.BooleanField(default=True, verbose_name="Landing page pública habilitada")
    landing_headline = models.CharField(max_length=180, blank=True, verbose_name="Título da landing page")
    landing_subheadline = models.TextField(blank=True, verbose_name="Subtítulo da landing page")
    landing_cta_label = models.CharField(max_length=80, default="Solicitar atendimento", blank=True, verbose_name="Texto do botão principal")
    landing_highlight_text = models.CharField(max_length=180, blank=True, verbose_name="Destaque curto da landing page")

    # Design system controlado pela área administrativa própria do React.
    ui_theme_mode = models.CharField(max_length=20, default="light", choices=[("light", "Claro"), ("dark", "Escuro"), ("auto", "Automático")], verbose_name="Tema da interface")
    ui_primary_color = models.CharField(max_length=20, default="#0d6efd", verbose_name="Cor primária")
    ui_accent_color = models.CharField(max_length=20, default="#fd7e14", verbose_name="Cor de destaque")
    ui_sidebar_color = models.CharField(max_length=20, default="#172033", verbose_name="Cor do menu lateral")
    ui_form_density = models.CharField(max_length=20, default="comfortable", choices=[("compact", "Compacto"), ("comfortable", "Confortável"), ("spacious", "Espaçoso")], verbose_name="Densidade dos formulários")
    ui_table_density = models.CharField(max_length=20, default="comfortable", choices=[("compact", "Compacto"), ("comfortable", "Confortável")], verbose_name="Densidade das tabelas")
    ui_card_radius = models.CharField(max_length=20, default="rounded", choices=[("soft", "Suave"), ("rounded", "Arredondado"), ("pill", "Muito arredondado")], verbose_name="Raio dos cards e campos")
    ui_button_style = models.CharField(max_length=20, default="solid", choices=[("solid", "Preenchido"), ("soft", "Suave"), ("outline", "Contorno")], verbose_name="Estilo dos botões primários")
    ui_form_layout = models.CharField(max_length=20, default="grouped", choices=[("grouped", "Agrupado por seções"), ("flat", "Plano"), ("wizard", "Abas/etapas")], verbose_name="Layout padrão dos formulários")
    ui_show_required_hint = models.BooleanField(default=True, verbose_name="Exibir dica em campos obrigatórios")
    ui_enable_motion = models.BooleanField(default=True, verbose_name="Ativar microinterações")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "cadastro da oficina"
        verbose_name_plural = "cadastro da oficina"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={"legal_name": "Minha Oficina", "trade_name": "Oficina Admin"})
        return obj

    @property
    def display_name(self):
        return self.trade_name or self.legal_name or "Oficina Admin"

    @property
    def document_digits(self):
        return "".join(ch for ch in (self.document_number or "") if ch.isdigit())

    @property
    def address_display(self):
        parts = []
        if self.address_line:
            line = self.address_line
            if self.address_number:
                line = f"{line}, {self.address_number}"
            if self.address_complement:
                line = f"{line} - {self.address_complement}"
            parts.append(line)
        if self.district:
            parts.append(self.district)
        city_state = " / ".join([p for p in [self.city, self.state] if p])
        if city_state:
            parts.append(city_state)
        if self.zip_code:
            parts.append(f"CEP {self.zip_code}")
        return " - ".join(parts)

    def clean(self):
        super().clean()
        self.legal_name = (self.legal_name or "").strip() or "Minha Oficina"
        self.trade_name = (self.trade_name or "").strip()
        self.state = (self.state or "").strip().upper()[:2]

    def save(self, *args, **kwargs):
        self.pk = 1
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.save(update_fields=["is_active", "updated_at"])

    def __str__(self):
        return self.display_name

class BottomNavigationItem(TimeStampedModel):
    """Botão configurável do menu inferior mobile exibido no frontend administrativo."""

    ICON_CHOICES = [
        ("attendance", "Atendimento"),
        ("wrench", "Chave / Oficina"),
        ("receipt", "Ordem / Recibo"),
        ("clipboard", "Checklist"),
        ("car", "Veículo"),
        ("box", "Estoque"),
        ("cart", "Venda"),
        ("finance", "Financeiro"),
        ("chart", "Relatórios"),
        ("message", "Mensagens"),
        ("users", "Clientes / Usuários"),
        ("tools", "Ferramentas"),
        ("package", "Pacote"),
        ("gear", "Configurações"),
        ("send", "Enviar"),
        ("bell", "Notificações"),
        ("health", "Saúde do sistema"),
        ("audit", "Auditoria"),
        ("home", "Início"),
        ("plus", "Adicionar"),
    ]

    label = models.CharField(max_length=32, verbose_name="Rótulo")
    path = models.CharField(max_length=180, verbose_name="Rota do frontend")
    icon = models.CharField(max_length=30, choices=ICON_CHOICES, default="receipt", verbose_name="Ícone")
    permission_code = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="Permissão necessária",
        help_text="Opcional. Use uma permissão do sistema, como work_orders.view. Para alternativas, separe por vírgula.",
    )
    position = models.PositiveSmallIntegerField(default=10, db_index=True, verbose_name="Ordem")
    highlight = models.BooleanField(default=False, verbose_name="Destacar botão")
    open_in_new_tab = models.BooleanField(default=False, verbose_name="Abrir em nova aba")
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Ativo")

    class Meta:
        ordering = ["position", "label"]
        verbose_name = "botão do menu inferior"
        verbose_name_plural = "menu inferior do app"

    @property
    def permission_codes(self):
        raw = (self.permission_code or "").replace(";", ",")
        return [part.strip() for part in raw.split(",") if part.strip()]

    def clean(self):
        super().clean()
        self.label = (self.label or "").strip()
        self.path = (self.path or "").strip()
        if self.path and not (self.path.startswith("/") or self.path.startswith("http://") or self.path.startswith("https://")):
            self.path = f"/{self.path}"
        self.permission_code = (self.permission_code or "").strip()

    def __str__(self):
        return self.label

