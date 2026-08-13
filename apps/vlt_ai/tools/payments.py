"""
VLT AI Tools — Payments
========================
Tool: get_payment_summary
"""
from __future__ import annotations

import logging

from django.db.models import Count, Q, Sum

from apps.vlt_ai.tools.registry import ai_tool
from apps.vlt_ai.tools.schemas import (
    DEBT_REPORT_SCHEMA,
    MY_DEBT_SCHEMA,
    MY_PAYMENTS_SCHEMA,
    PAYMENT_REPORT_SCHEMA,
    PAYMENT_SUMMARY_SCHEMA,
)

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


@ai_tool(
    name="get_my_payments",
    required_permission="payments.view_self",
    description=MY_PAYMENTS_SCHEMA["description"],
    schema=MY_PAYMENTS_SCHEMA,
)
def get_my_payments(user, limit: int = 12) -> dict:
    """Return the current student's own payment history.

    No ID argument — always scoped to the authenticated user's own
    student_profile.
    """
    from apps.payments.models import Payment

    student = getattr(user, "student_profile", None)
    if student is None:
        return {"error": "O'quvchi profili topilmadi"}

    rows = list(
        Payment.objects.filter(student=student)
        .order_by("-year", "-month")
        .values("month", "year", "amount", "paid_amount", "debt_amount", "status")[:limit]
    )

    return {
        "count": len(rows),
        "payments": [
            {
                "month": r["month"],
                "year": r["year"],
                "amount": float(r["amount"]),
                "paid_amount": float(r["paid_amount"]),
                "debt_amount": float(r["debt_amount"]),
                "status": r["status"],
            }
            for r in rows
        ],
    }


@ai_tool(
    name="get_my_debt",
    required_permission="payments.view_self",
    description=MY_DEBT_SCHEMA["description"],
    schema=MY_DEBT_SCHEMA,
)
def get_my_debt(user) -> dict:
    """Return the current student's own total debt and unpaid/partial rows."""
    from apps.payments.models import Payment

    student = getattr(user, "student_profile", None)
    if student is None:
        return {"error": "O'quvchi profili topilmadi"}

    unpaid = list(
        Payment.objects.filter(student=student)
        .exclude(status="paid")
        .order_by("-year", "-month")
        .values("month", "year", "debt_amount", "status")
    )

    return {
        "total_debt": float(student.total_debt),
        "unpaid_count": len(unpaid),
        "unpaid_payments": [
            {
                "month": r["month"],
                "year": r["year"],
                "debt_amount": float(r["debt_amount"]),
                "status": r["status"],
            }
            for r in unpaid
        ],
    }


@ai_tool(
    name="get_payment_report",
    required_permission="payments.view_any",
    description=PAYMENT_REPORT_SCHEMA["description"],
    schema=PAYMENT_REPORT_SCHEMA,
)
def get_payment_report(user, month: int | None = None, year: int | None = None) -> dict:
    """Detailed payment report for finance/admin — defaults to the current month."""
    from django.utils import timezone

    from apps.payments.models import Payment

    now = timezone.localdate()
    month = month or now.month
    year = year or now.year

    qs = Payment.objects.filter(month=month, year=year)
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
        "period": {"month": month, "year": year},
        "total_count": agg["total_count"] or 0,
        "paid_count": agg["paid_count"] or 0,
        "partial_count": agg["partial_count"] or 0,
        "unpaid_count": agg["unpaid_count"] or 0,
        "total_amount": float(agg["total_amount"] or 0),
        "total_paid": float(agg["total_paid"] or 0),
        "total_debt": float(agg["total_debt"] or 0),
        "collection_rate_pct": (
            round(float(agg["total_paid"] or 0) / float(agg["total_amount"]) * 100, 1)
            if agg["total_amount"] else 0
        ),
    }


@ai_tool(
    name="get_debt_report",
    required_permission="payments.view_any",
    description=DEBT_REPORT_SCHEMA["description"],
    schema=DEBT_REPORT_SCHEMA,
)
def get_debt_report(user, limit: int = 10) -> dict:
    """Top debtor students and total outstanding debt, for finance/admin."""
    from apps.payments.models import Payment
    from apps.students.models import Student

    total_debt = Payment.objects.aggregate(total=Sum("debt_amount"))["total"] or 0

    top_debtors = list(
        Student.objects.annotate(debt=Sum("payments__debt_amount"))
        .filter(debt__gt=0)
        .select_related("user", "group")
        .order_by("-debt")[:limit]
        .values("id", "user__full_name", "group__name", "debt")
    )

    return {
        "total_debt": float(total_debt),
        "top_debtors": [
            {
                "student_id": str(d["id"]),
                "name": d["user__full_name"],
                "group": d["group__name"],
                "debt": float(d["debt"] or 0),
            }
            for d in top_debtors
        ],
    }
