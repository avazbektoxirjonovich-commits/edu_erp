"""
VLT AI Tools — Finance
=======================
Tools: get_salary_report, get_expense_report, get_asset_report, get_finance_summary

Reuses apps.finance.services.compute_financial_summary() — the same
aggregation already backing the Finance Dashboard / Excel exports — rather
than recomputing income/expense/net-result logic here.
"""
from __future__ import annotations

import logging

from django.db.models import Sum

from apps.vlt_ai.tools.registry import ai_tool
from apps.vlt_ai.tools.schemas import (
    ASSET_REPORT_SCHEMA,
    EXPENSE_REPORT_SCHEMA,
    FINANCE_SUMMARY_SCHEMA,
    SALARY_REPORT_SCHEMA,
)

logger = logging.getLogger("apps.vlt_ai.tools.finance")


def _month_bounds(month: int | None, year: int | None):
    import calendar
    from datetime import date

    from django.utils import timezone

    now = timezone.localdate()
    month = month or now.month
    year = year or now.year
    last_day = calendar.monthrange(year, month)[1]
    return month, year, date(year, month, 1), date(year, month, last_day)


@ai_tool(
    name="get_salary_report",
    required_permission="finance.view_reports",
    description=SALARY_REPORT_SCHEMA["description"],
    schema=SALARY_REPORT_SCHEMA,
)
def get_salary_report(user, month: int | None = None, year: int | None = None) -> dict:
    """Teacher salary report for a given month (finance/admin only)."""
    from apps.teachers.models import TeacherSalaryPayment

    month, year, _start, _end = _month_bounds(month, year)

    qs = TeacherSalaryPayment.objects.filter(month=month, year=year).select_related("teacher__user")
    agg = qs.aggregate(total_amount=Sum("amount"), total_bonus=Sum("bonus"), total_deductions=Sum("deductions"))

    rows = list(
        qs.values("teacher__user__full_name", "amount", "bonus", "deductions", "status")
    )

    return {
        "period": {"month": month, "year": year},
        "total_paid_count": qs.filter(status="paid").count(),
        "total_pending_count": qs.filter(status="pending").count(),
        "total_amount": float(agg["total_amount"] or 0),
        "total_bonus": float(agg["total_bonus"] or 0),
        "total_deductions": float(agg["total_deductions"] or 0),
        "payments": [
            {
                "teacher": r["teacher__user__full_name"],
                "amount": float(r["amount"]),
                "bonus": float(r["bonus"]),
                "deductions": float(r["deductions"]),
                "status": r["status"],
            }
            for r in rows
        ],
    }


@ai_tool(
    name="get_expense_report",
    required_permission="finance.view_reports",
    description=EXPENSE_REPORT_SCHEMA["description"],
    schema=EXPENSE_REPORT_SCHEMA,
)
def get_expense_report(user, month: int | None = None, year: int | None = None) -> dict:
    """Center expense report, broken down by category (finance/admin only)."""
    from apps.finance.models import Expense

    month, year, start, end = _month_bounds(month, year)

    qs = Expense.objects.filter(expense_date__gte=start, expense_date__lte=end)
    total = qs.aggregate(total=Sum("amount"))["total"] or 0

    by_category = {}
    for choice, _label in Expense.Category.choices:
        by_category[choice] = float(
            qs.filter(category=choice).aggregate(total=Sum("amount"))["total"] or 0
        )

    return {
        "period": {"month": month, "year": year},
        "total_amount": float(total),
        "by_category": by_category,
    }


@ai_tool(
    name="get_asset_report",
    required_permission="finance.view_reports",
    description=ASSET_REPORT_SCHEMA["description"],
    schema=ASSET_REPORT_SCHEMA,
)
def get_asset_report(user) -> dict:
    """Center asset report, broken down by condition (finance/admin only)."""
    from apps.finance.models import Asset

    assets = list(Asset.objects.all())
    total_value = sum(a.total_value for a in assets)
    by_condition = {}
    for choice, _label in Asset.Condition.choices:
        by_condition[choice] = float(
            sum(a.total_value for a in assets if a.condition == choice)
        )

    return {
        "total_assets": len(assets),
        "total_value": float(total_value),
        "value_by_condition": by_condition,
    }


@ai_tool(
    name="get_finance_summary",
    required_permission="finance.view_reports",
    description=FINANCE_SUMMARY_SCHEMA["description"],
    schema=FINANCE_SUMMARY_SCHEMA,
)
def get_finance_summary(user, month: int | None = None, year: int | None = None) -> dict:
    """Overall financial summary for a month — income, expenses, salaries, net result."""
    from apps.finance.services import compute_financial_summary

    month, year, start, end = _month_bounds(month, year)
    summary = compute_financial_summary(start, end)
    summary["period"] = {"month": month, "year": year}
    return summary
