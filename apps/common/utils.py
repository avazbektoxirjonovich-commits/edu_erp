from django.db.models import Sum, DecimalField
from django.db.models.functions import Coalesce

_DEBT_FIELD = DecimalField(max_digits=12, decimal_places=0)


def debt_annotation(field='payments__debt_amount'):
    """
    Coalesce(Sum(field), 0) — qarz summasi annotatsiyasi.
    annotate() uchun: debt_annotation('payments__debt_amount')
    aggregate() uchun: debt_annotation('debt_amount')
    """
    return Coalesce(Sum(field, output_field=_DEBT_FIELD), 0, output_field=_DEBT_FIELD)
