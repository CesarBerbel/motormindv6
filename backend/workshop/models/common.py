from decimal import Decimal
import hashlib
import os
import re
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from accounts.numbering import next_formatted_sequence

from messaging.models import Contact, MessageLog, MessageTemplate, TimeStampedModel

User = get_user_model()
ZERO = Decimal("0.00")


def normalize_lookup_name(value):
    """Normaliza nomes usados em cadastros auxiliares: sem espaços e em minúsculo."""
    return re.sub(r"\s+", "", (value or "").strip()).lower()


def generate_prefixed_sequence_code(model, prefix):
    codes = model.objects.filter(code__startswith=f"{prefix}-").values_list("code", flat=True)
    last_number = 0
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$", re.IGNORECASE)
    for code in codes:
        match = pattern.match(str(code or "").strip())
        if not match:
            continue
        try:
            last_number = max(last_number, int(match.group(1)))
        except ValueError:
            continue
    return f"{prefix}-{last_number + 1:04d}"


IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
IMAGE_EXTENSIONS_WITH_SVG = IMAGE_EXTENSIONS + ["svg"]
MAX_IMAGE_SIZE = 8 * 1024 * 1024
MAX_LOGO_SIZE = 3 * 1024 * 1024

PART_UNIT_CHOICES = [
    ("un", "Unidade"),
    ("pc", "Peça"),
    ("kit", "Kit"),
    ("par", "Par"),
    ("jogo", "Jogo"),
    ("cx", "Caixa"),
    ("pct", "Pacote"),
    ("m", "Metro"),
    ("cm", "Centímetro"),
    ("l", "Litro"),
    ("ml", "Mililitro"),
    ("kg", "Quilograma"),
    ("g", "Grama"),
]

UNIT_NORMALIZATION_ALIASES = {
    "": "un",
    "und": "un",
    "unid": "un",
    "unidade": "un",
    "unidades": "un",
    "unit": "un",
    "units": "un",
    "peca": "pc",
    "pecas": "pc",
    "peça": "pc",
    "peças": "pc",
    "pcs": "pc",
    "pç": "pc",
    "pçs": "pc",
    "caixa": "cx",
    "caixas": "cx",
    "pacote": "pct",
    "pacotes": "pct",
    "quilo": "kg",
    "quilograma": "kg",
    "quilogramas": "kg",
    "metro": "m",
    "metros": "m",
    "centimetro": "cm",
    "centímetros": "cm",
    "centimetros": "cm",
    "litro": "l",
    "litros": "l",
}


def normalize_part_unit(value):
    raw = (value or "").strip().lower()
    compact = re.sub(r"\s+", "", raw)
    return UNIT_NORMALIZATION_ALIASES.get(compact, compact or "un")


def safe_upload_path(prefix, instance, filename):
    ext = os.path.splitext(filename or "arquivo")[1].lower() or ".jpg"
    return f"{prefix}/{timezone.localdate():%Y/%m}/{uuid4().hex}{ext}"


def workshop_logo_upload_path(instance, filename):
    return safe_upload_path("workshop/logos", instance, filename)


def service_photo_upload_path(instance, filename):
    return safe_upload_path("workshop/services", instance, filename)


def part_photo_upload_path(instance, filename):
    return safe_upload_path("workshop/parts", instance, filename)


def work_order_photo_upload_path(instance, filename):
    work_order_id = getattr(instance, "work_order_id", None) or "sem-os"
    return safe_upload_path(f"workshop/work-orders/{work_order_id}/photos", instance, filename)


def work_order_checklist_photo_upload_path(instance, filename):
    work_order_id = getattr(instance, "work_order_id", None) or "sem-os"
    return safe_upload_path(f"workshop/work-orders/{work_order_id}/checklist", instance, filename)


def work_order_signature_upload_path(instance, filename):
    work_order_id = getattr(instance, "work_order_id", None) or "sem-os"
    return safe_upload_path(f"workshop/work-orders/{work_order_id}/signatures", instance, filename)


def validate_file_size(value, max_size=MAX_IMAGE_SIZE, label="imagem"):
    if value and getattr(value, "size", 0) > max_size:
        raise ValidationError({"image": f"A {label} deve ter no máximo {max_size // (1024 * 1024)} MB."})




# Mantem caminhos historicos usados em migrations antigas, como
# workshop.models.workshop_logo_upload_path, mesmo com a divisao em modulos.
for _fn in [
    safe_upload_path,
    workshop_logo_upload_path,
    service_photo_upload_path,
    part_photo_upload_path,
    work_order_photo_upload_path,
    work_order_checklist_photo_upload_path,
    work_order_signature_upload_path,
    validate_file_size,
]:
    _fn.__module__ = "workshop.models"
