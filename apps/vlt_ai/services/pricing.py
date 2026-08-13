"""
VLT AI — Cost estimation
==========================
Static $/million-token table for supported Claude models. Used only to
populate Message.estimated_cost for reporting/audit — never sent to the API.
"""
from __future__ import annotations

from decimal import Decimal

# {model_id_prefix: (input $/MTok, output $/MTok)}
PRICING_PER_MTOK: dict[str, tuple[Decimal, Decimal]] = {
    "claude-haiku-4-5": (Decimal("1.00"), Decimal("5.00")),
    "claude-sonnet-5": (Decimal("3.00"), Decimal("15.00")),
    "claude-opus-5": (Decimal("5.00"), Decimal("25.00")),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal | None:
    """Return an estimated USD cost, or None if the model isn't in the table
    (unknown pricing must never be silently reported as $0)."""
    for prefix, (in_rate, out_rate) in PRICING_PER_MTOK.items():
        if model.startswith(prefix):
            cost = (Decimal(input_tokens) * in_rate + Decimal(output_tokens) * out_rate) / Decimal(1_000_000)
            return cost.quantize(Decimal("0.000001"))
    return None
