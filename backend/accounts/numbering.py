import re

from django.db import transaction
from django.utils import timezone

from .models import NumberSequence


def _max_existing_sequence(model, formatted_prefix, number_field="number"):
    pattern = re.compile(rf"^{re.escape(formatted_prefix)}(\d+)$")
    last_number = 0
    values = model.objects.filter(**{f"{number_field}__startswith": formatted_prefix}).values_list(number_field, flat=True)
    for value in values:
        match = pattern.match(str(value or ""))
        if not match:
            continue
        try:
            last_number = max(last_number, int(match.group(1)))
        except ValueError:
            continue
    return last_number


@transaction.atomic
def next_formatted_sequence(scope, prefix, model, width=5, number_field="number", year=None):
    """Gera códigos sequenciais anuais de forma atômica.

    Formato padrão: PREFIXO-ANO-00001.
    O primeiro uso de cada escopo/ano inicializa a sequência a partir dos registros
    já existentes para evitar colisão em bases migradas.
    """
    sequence_year = year or timezone.localdate().year
    formatted_prefix = f"{prefix}-{sequence_year}-"
    existing_max = _max_existing_sequence(model, formatted_prefix, number_field=number_field)
    sequence, _created = NumberSequence.objects.select_for_update(of=("self",)).get_or_create(
        scope=scope,
        year=sequence_year,
        defaults={"last_number": existing_max},
    )
    if sequence.last_number < existing_max:
        sequence.last_number = existing_max
    sequence.last_number += 1
    sequence.save(update_fields=["last_number", "updated_at"])
    return f"{formatted_prefix}{sequence.last_number:0{width}d}"
