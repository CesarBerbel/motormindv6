from decimal import Decimal
from io import BytesIO

from django.apps import apps
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import WorkshopProfile, WorkOrder, WorkOrderCustomerApproval

ZERO = Decimal("0.00")
DOCUMENT_TITLES = {
    WorkOrderCustomerApproval.DocumentType.ESTIMATE: "ORÇAMENTO",
    WorkOrderCustomerApproval.DocumentType.WORK_ORDER: "ORDEM DE SERVIÇO",
    WorkOrderCustomerApproval.DocumentType.RECEIPT: "RECIBO",
    "delivery_receipt": "COMPROVANTE DE ENTREGA",
}


def format_money(value):
    value = Decimal(value or ZERO)
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_date(value):
    if not value:
        return "-"
    if hasattr(value, "astimezone"):
        value = timezone.localtime(value)
        return value.strftime("%d/%m/%Y %H:%M")
    return value.strftime("%d/%m/%Y")


def safe_text(value):
    return str(value or "").replace("\n", "<br/>")


def yes_no(value):
    return "Sim" if value else "Não"


def stock_reservation_text(line):
    status = getattr(line, "stock_reservation_status", "")
    if getattr(line, "stock_consumed_at", None):
        return "Consumido"
    if status == "reserved":
        return f"Reservado: {line.stock_reserved_quantity}"
    if status == "partial":
        return f"Parcial: {line.stock_reserved_quantity} reservado / falta {line.stock_shortage_quantity}"
    if status == "unavailable":
        return f"Aguardando: falta {line.stock_shortage_quantity}"
    if status == "not_applicable":
        return "Sem controle"
    return "Pendente"


def _doc_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="DocTitle", parent=styles["Title"], alignment=TA_CENTER, fontSize=16, leading=20, spaceAfter=8))
    styles.add(ParagraphStyle(name="SectionTitle", parent=styles["Heading2"], fontSize=11, leading=14, spaceBefore=8, spaceAfter=6, textColor=colors.HexColor("#1f2937")))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="SmallRight", parent=styles["Small"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="CenterSmall", parent=styles["Small"], alignment=TA_CENTER))
    return styles


def _make_table(rows, widths=None, header=True):
    table = Table(rows, colWidths=widths, hAlign="LEFT", repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold" if header else "Helvetica"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6") if header else colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    table.setStyle(TableStyle(style))
    return table


def _header(story, number, document_type, styles, title_override=""):
    profile = WorkshopProfile.get_solo()
    title = title_override or DOCUMENT_TITLES.get(document_type, "DOCUMENTO")
    story.append(Paragraph(title, styles["DocTitle"]))
    header_rows = [
        [
            Paragraph(f"<b>{safe_text(profile.display_name)}</b><br/>{safe_text(profile.legal_name)}", styles["BodyText"]),
            Paragraph(f"<b>Número:</b> {safe_text(number)}<br/><b>Emitido em:</b> {format_date(timezone.now())}", styles["SmallRight"]),
        ],
        [
            Paragraph(f"<b>Documento:</b> {safe_text(profile.document_number) or '-'}<br/><b>Contato:</b> {safe_text(profile.phone_e164) or '-'} | {safe_text(profile.email) or '-'}", styles["Small"]),
            Paragraph(f"<b>Endereço:</b><br/>{safe_text(profile.address_display) or '-'}", styles["SmallRight"]),
        ],
    ]
    story.append(_make_table(header_rows, [110 * mm, 70 * mm], header=False))
    if profile.print_header_text:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(safe_text(profile.print_header_text), styles["Small"]))
    story.append(Spacer(1, 5 * mm))


def _vehicle_text(vehicle, mileage_in=None, tank_label=""):
    if not vehicle:
        return "Sem veículo vinculado"
    lines = [
        f"<b>{safe_text(vehicle.display_name)}</b>",
        f"Placa: {safe_text(vehicle.plate) or '-'}",
        f"Ano: {safe_text(vehicle.year) or '-'}",
        f"Cor: {safe_text(vehicle.color) or '-'}",
    ]
    if mileage_in is not None:
        lines.append(f"KM entrada: {mileage_in or 0}")
    if tank_label:
        lines.append(f"Tanque de combustível: {safe_text(tank_label)}")
    lines.extend([
        f"Direção: {safe_text(getattr(vehicle, 'steering_type_label', '')) or '-'}",
        f"Câmbio: {safe_text(getattr(vehicle, 'transmission_type_label', '')) or '-'}",
        f"Portas: {safe_text(vehicle.door_count) or '-'}",
        f"Ar-condicionado: {yes_no(vehicle.has_air_conditioning)}",
        f"Veículo modificado: {yes_no(vehicle.is_modified)}",
    ])
    if vehicle.fipe_brand_code or vehicle.fipe_model_code or vehicle.fipe_year_code:
        lines.append(f"FIPE: {safe_text(vehicle.fipe_brand_code) or '-'} / {safe_text(vehicle.fipe_model_code) or '-'} / {safe_text(vehicle.fipe_year_code) or '-'}")
    if vehicle.version:
        lines.append(f"Versão: {safe_text(vehicle.version)}")
    return "<br/>".join(lines)


def _customer_text(customer):
    return (
        f"<b>{safe_text(customer.display_name)}</b><br/>"
        f"CPF/CNPJ: {safe_text(customer.document_number) or '-'}<br/>"
        f"Email: {safe_text(customer.email) or '-'}<br/>"
        f"Telefone: {safe_text(customer.phone_e164) or '-'}<br/>"
        f"Endereço: {safe_text(customer.address_display) or '-'}"
    )


def _source_estimate_for_work_order(work_order):
    if not getattr(work_order, "source_estimate_id", None):
        return None
    Estimate = apps.get_model("attendance", "Estimate")
    try:
        return Estimate.objects.get(pk=work_order.source_estimate_id)
    except Estimate.DoesNotExist:
        return None


def _customer_vehicle_section(story, work_order, styles):
    source_estimate = _source_estimate_for_work_order(work_order)
    tank_label = source_estimate.tank_level_label if source_estimate else ""
    rows = [
        [Paragraph("<b>Cliente</b>", styles["Small"]), Paragraph("<b>Veículo</b>", styles["Small"])],
        [
            Paragraph(_customer_text(work_order.customer), styles["Small"]),
            Paragraph(_vehicle_text(work_order.vehicle, mileage_in=work_order.mileage_in, tank_label=tank_label), styles["Small"]),
        ],
    ]
    story.append(_make_table(rows, [90 * mm, 90 * mm], header=True))


def _estimate_customer_vehicle_section(story, estimate, styles):
    rows = [
        [Paragraph("<b>Cliente</b>", styles["Small"]), Paragraph("<b>Veículo</b>", styles["Small"])],
        [
            Paragraph(_customer_text(estimate.customer), styles["Small"]),
            Paragraph(_vehicle_text(estimate.vehicle, tank_label=estimate.tank_level_label), styles["Small"]),
        ],
    ]
    story.append(_make_table(rows, [90 * mm, 90 * mm], header=True))


def _order_notes(story, work_order, styles):
    story.append(Paragraph("Dados da OS", styles["SectionTitle"]))
    rows = [
        ["Status", work_order.status_label, "Prioridade", work_order.priority_label],
        ["Abertura", format_date(work_order.opened_at), "Previsão", format_date(work_order.promised_at)],
        ["Origem", safe_text(work_order.source_estimate_number) or "Cadastro direto", "Tipo", safe_text(work_order.get_order_type_display())],
        ["Relato", Paragraph(safe_text(work_order.complaint) or "-", styles["Small"]), "Diagnóstico", Paragraph(safe_text(work_order.diagnosis) or "-", styles["Small"])],
        ["Solução", Paragraph(safe_text(work_order.solution) or "-", styles["Small"]), "Observações ao cliente", Paragraph(safe_text(work_order.customer_notes) or "-", styles["Small"])],
    ]
    story.append(_make_table(rows, [25 * mm, 65 * mm, 30 * mm, 60 * mm], header=False))


def _estimate_notes(story, estimate, styles):
    story.append(Paragraph("Dados do orçamento", styles["SectionTitle"]))
    rows = [
        ["Status", estimate.status_label, "Validade", format_date(estimate.valid_until)],
        ["Tanque", estimate.tank_level_label, "Criado em", format_date(estimate.created_at)],
        ["Título", Paragraph(safe_text(estimate.title) or "-", styles["Small"]), "Número", safe_text(estimate.number) or "-"],
        ["Relato", Paragraph(safe_text(estimate.complaint) or "-", styles["Small"]), "Diagnóstico", Paragraph(safe_text(estimate.diagnosis) or "-", styles["Small"])],
        ["Observações ao cliente", Paragraph(safe_text(estimate.customer_notes) or "-", styles["Small"]), "Observações internas", Paragraph(safe_text(estimate.internal_notes) or "-", styles["Small"])],
    ]
    story.append(_make_table(rows, [32 * mm, 58 * mm, 32 * mm, 58 * mm], header=False))


def _services(story, work_order, styles):
    story.append(Paragraph("Serviços", styles["SectionTitle"]))
    rows = [["Descrição", "Qtd.", "Unitário", "Desc.", "Total"]]
    for line in work_order.services.all():
        rows.append([Paragraph(safe_text(line.description), styles["Small"]), str(line.quantity), format_money(line.unit_price), format_money(line.discount_amount), format_money(line.total_amount)])
    if len(rows) == 1:
        rows.append(["Nenhum serviço lançado", "", "", "", ""])
    story.append(_make_table(rows, [92 * mm, 18 * mm, 25 * mm, 20 * mm, 25 * mm], header=True))


def _estimate_services(story, estimate, styles):
    story.append(Paragraph("Serviços", styles["SectionTitle"]))
    rows = [["Combo/Serviço", "Qtd.", "Unitário", "Desc.", "Total", "Aprovado"]]
    for line in estimate.services.select_related("source_package").all():
        description = safe_text(line.description)
        if line.source_package_id:
            description = f"{safe_text(line.source_package.name)} - {description}"
        rows.append([
            Paragraph(description, styles["Small"]),
            str(line.quantity),
            format_money(line.unit_price),
            format_money(line.discount_amount),
            format_money(line.total_amount),
            yes_no(line.approved_by_customer),
        ])
    if len(rows) == 1:
        rows.append(["Nenhum serviço lançado", "", "", "", "", ""])
    story.append(_make_table(rows, [78 * mm, 15 * mm, 24 * mm, 18 * mm, 23 * mm, 22 * mm], header=True))


def _parts(story, work_order, styles):
    story.append(Paragraph("Peças", styles["SectionTitle"]))
    rows = [["Código", "Serviço", "Descrição", "Qtd.", "Unitário", "Desc.", "Total", "Estoque"]]
    for line in work_order.parts.select_related("linked_service", "part").all():
        rows.append([
            line.part.sku if line.part else "-",
            Paragraph(safe_text(line.linked_service.description) if line.linked_service_id else "Sem vínculo", styles["Small"]),
            Paragraph(safe_text(line.description), styles["Small"]),
            str(line.quantity),
            format_money(line.unit_price),
            format_money(line.discount_amount),
            format_money(line.total_amount),
            Paragraph(safe_text(stock_reservation_text(line)), styles["Small"]),
        ])
    if len(rows) == 1:
        rows.append(["-", "-", "Nenhuma peça lançada", "", "", "", "", ""])
    story.append(_make_table(rows, [17 * mm, 30 * mm, 42 * mm, 12 * mm, 19 * mm, 13 * mm, 16 * mm, 31 * mm], header=True))


def _estimate_parts(story, estimate, styles):
    story.append(Paragraph("Peças", styles["SectionTitle"]))
    rows = [["Código", "Serviço", "Descrição", "Qtd.", "Unitário", "Desc.", "Total", "Aprovado"]]
    for line in estimate.parts.select_related("service_item", "part").all():
        rows.append([
            line.part.sku if line.part else "-",
            Paragraph(safe_text(line.service_item.description) if line.service_item_id else "Sem vínculo", styles["Small"]),
            Paragraph(safe_text(line.description), styles["Small"]),
            str(line.quantity),
            format_money(line.unit_price),
            format_money(line.discount_amount),
            format_money(line.total_amount),
            yes_no(line.approved_by_customer),
        ])
    if len(rows) == 1:
        rows.append(["-", "-", "Nenhuma peça lançada", "", "", "", "", ""])
    story.append(_make_table(rows, [18 * mm, 34 * mm, 47 * mm, 13 * mm, 21 * mm, 15 * mm, 17 * mm, 15 * mm], header=True))


def _checklist(story, work_order, styles):
    items = work_order.technical_checklist_items.select_related("work_order_service", "completed_by").all()
    if not items:
        return
    story.append(Paragraph("Checklist técnico", styles["SectionTitle"]))
    rows = [["Serviço", "Item", "Obrig.", "Concluído", "Observação"]]
    for item in items:
        rows.append([
            Paragraph(safe_text(item.work_order_service.description), styles["Small"]),
            Paragraph(safe_text(item.description), styles["Small"]),
            "Sim" if item.is_required else "Não",
            format_date(item.completed_at) if item.is_completed else "Pendente",
            Paragraph(safe_text(item.note) or "-", styles["Small"]),
        ])
    story.append(_make_table(rows, [45 * mm, 58 * mm, 15 * mm, 30 * mm, 32 * mm], header=True))


def _delivery_signature(story, work_order, styles):
    signature = getattr(work_order, "delivery_signature", None)
    if not signature:
        return
    story.append(Paragraph("Assinatura digital de entrega", styles["SectionTitle"]))
    rows = [
        ["Recebido por", safe_text(signature.recipient_name), "Documento", safe_text(signature.recipient_document) or "-"],
        ["Assinado em", format_date(signature.signed_at), "Registrado por", safe_text(signature.signed_by_name) or "Sistema"],
        ["Observações", Paragraph(safe_text(signature.notes) or "-", styles["Small"]), "IP", safe_text(signature.signed_ip) or "-"],
    ]
    story.append(_make_table(rows, [30 * mm, 70 * mm, 30 * mm, 50 * mm], header=False))
    try:
        story.append(Spacer(1, 4 * mm))
        img = Image(signature.signature_image.path, width=70 * mm, height=28 * mm, kind="proportional")
        story.append(img)
    except Exception:
        story.append(Paragraph("Imagem da assinatura indisponível para impressão.", styles["Small"]))


def _payments(story, work_order, styles):
    story.append(Paragraph("Pagamentos", styles["SectionTitle"]))
    rows = [["Data", "Forma", "Referência", "Valor"]]
    for payment in work_order.payments.all():
        rows.append([format_date(payment.paid_at), payment.get_method_display(), safe_text(payment.reference) or "-", format_money(payment.amount)])
    if len(rows) == 1:
        rows.append(["-", "Nenhum pagamento registrado", "", ""])
    story.append(_make_table(rows, [35 * mm, 45 * mm, 70 * mm, 30 * mm], header=True))


def _totals(story, work_order, styles):
    rows = [
        ["Subtotal serviços", format_money(work_order.subtotal_services)],
        ["Subtotal peças", format_money(work_order.subtotal_parts)],
        ["Descontos", format_money(work_order.discount_total)],
        ["Total", format_money(work_order.grand_total)],
        ["Pago", format_money(work_order.paid_total)],
        ["Saldo", format_money(work_order.balance_due)],
    ]
    table = _make_table(rows, [130 * mm, 50 * mm], header=False)
    table.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"), ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#f9fafb"))]))
    story.append(Paragraph("Resumo financeiro", styles["SectionTitle"]))
    story.append(table)


def _estimate_totals(story, estimate, styles):
    item_discounts = sum((item.discount_amount or ZERO for item in estimate.services.all()), ZERO) + sum((item.discount_amount or ZERO for item in estimate.parts.all()), ZERO)
    rows = [
        ["Subtotal serviços", format_money(estimate.subtotal_services)],
        ["Subtotal peças", format_money(estimate.subtotal_parts)],
        ["Descontos de itens", format_money(item_discounts)],
        ["Desconto geral", format_money(estimate.discount_amount)],
        ["Total", format_money(estimate.total_amount)],
    ]
    table = _make_table(rows, [130 * mm, 50 * mm], header=False)
    table.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold"), ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#f9fafb"))]))
    story.append(Paragraph("Resumo financeiro", styles["SectionTitle"]))
    story.append(table)


def _terms(story, document_type, styles):
    profile = WorkshopProfile.get_solo()
    terms = profile.estimate_terms if document_type == WorkOrderCustomerApproval.DocumentType.ESTIMATE else profile.work_order_terms
    if document_type == WorkOrderCustomerApproval.DocumentType.RECEIPT:
        terms = profile.print_footer_text or profile.work_order_terms
    if terms:
        story.append(Paragraph("Condições", styles["SectionTitle"]))
        story.append(Paragraph(safe_text(terms), styles["Small"]))
    if profile.bank_info or profile.pix_key:
        story.append(Paragraph("Dados de pagamento", styles["SectionTitle"]))
        story.append(Paragraph(f"{safe_text(profile.bank_info)}<br/><b>Pix:</b> {safe_text(profile.pix_key) or '-'}", styles["Small"]))


def _signatures(story, customer_name, styles):
    story.append(Spacer(1, 12 * mm))
    profile = WorkshopProfile.get_solo()
    rows = [
        ["________________________________________", "________________________________________"],
        ["Assinatura do cliente", "Assinatura da oficina/técnico"],
        [customer_name, profile.responsible_name or profile.display_name],
    ]
    story.append(_make_table(rows, [90 * mm, 90 * mm], header=False))


def generate_work_order_pdf(work_order: WorkOrder, document_type="work_order") -> bytes:
    allowed_types = set(dict(WorkOrderCustomerApproval.DocumentType.choices)) | {"delivery_receipt"}
    if document_type not in allowed_types:
        document_type = WorkOrderCustomerApproval.DocumentType.WORK_ORDER
    work_order.recalculate_totals(save=False)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=12 * mm, bottomMargin=12 * mm, title=f"{DOCUMENT_TITLES.get(document_type)} {work_order.number}")
    styles = _doc_styles()
    story = []
    _header(story, work_order.number, document_type, styles)
    _customer_vehicle_section(story, work_order, styles)
    _order_notes(story, work_order, styles)
    _services(story, work_order, styles)
    _parts(story, work_order, styles)
    if document_type in {WorkOrderCustomerApproval.DocumentType.WORK_ORDER, "delivery_receipt"}:
        _checklist(story, work_order, styles)
    if document_type in {WorkOrderCustomerApproval.DocumentType.RECEIPT, "delivery_receipt"}:
        _payments(story, work_order, styles)
    _totals(story, work_order, styles)
    _terms(story, document_type, styles)
    if document_type == "delivery_receipt":
        _delivery_signature(story, work_order, styles)
    _signatures(story, work_order.customer.full_name, styles)
    doc.build(story)
    return buffer.getvalue()


def generate_estimate_pdf(estimate) -> bytes:
    estimate.recalculate_totals(save=False)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=12 * mm, bottomMargin=12 * mm, title=f"ORÇAMENTO {estimate.number}")
    styles = _doc_styles()
    story = []
    _header(story, estimate.number, WorkOrderCustomerApproval.DocumentType.ESTIMATE, styles, title_override="ORÇAMENTO")
    _estimate_customer_vehicle_section(story, estimate, styles)
    _estimate_notes(story, estimate, styles)
    _estimate_services(story, estimate, styles)
    _estimate_parts(story, estimate, styles)
    _estimate_totals(story, estimate, styles)
    _terms(story, WorkOrderCustomerApproval.DocumentType.ESTIMATE, styles)
    _signatures(story, estimate.customer.full_name, styles)
    doc.build(story)
    return buffer.getvalue()
