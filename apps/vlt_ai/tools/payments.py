"""
VLT AI Tools — Payments
========================
Tool: get_payment_summary
"""
from __future__ import annotations

import logging

from django.db.models import Count, Q, Sum

from apps.vlt_ai.tools.registry import ai_tool
from apps.vlt_ai.tools.schemas import PAYMENT_SUMMARY_SCHEMA

logger = logging.getLogger("apps.vlt_ai.tools.payments")


@ai_tool(
    name="get_payment_summary",
    required_permission="payments.view_any",
    description=PAYMENT_SUMMARY_SCHEMA["description"],
    schema=PAYMENT_SUMMARY_SCHEMA,
)
def get_payment_summary(
    user,
    month: int | None = None,
    year: int | None = None,
    status: str | None = None,
) -> dict:
    """Return payment statistics summary (admin/dev only)."""
    from apps.payments.models import Payment

    qs = Payment.objects.all()

    if month is not None:
        qs = qs.filter(month=month)
    if year is not None:
        qs = qs.filter(year=year)
    if status:
        qs = qs.filter(status=status)

    agg = qs.aggregate(
        total_count=Count("id"),
        paid_count=Count("id", filter=Q(status="paid")),
        partial_count=Count("id", filter=Q(status="partial")),
        unpaid_count=Count("id", filter=Q(status="unpaid")),
        total_amount=Sum("amount"),
        total_paid=Sum("paid_amount"),
        total_debt=Sum("debt_amount"),
    )

    return {
        "filter": {"month": month, "year": year, "status": status},
        "total_count": agg["total_count"] or 0,
        "paid_count": agg["paid_count"] or 0,
        "partial_count": agg["partial_count"] or 0,
        "unpaid_count": agg["unpaid_count"] or 0,
        "total_amount": float(agg["total_amount"] or 0),
        "total_paid": float(agg["total_paid"] or 0),
        "total_debt": float(agg["total_debt"] or 0),
    }
