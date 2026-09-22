"""Moliyaviy hisob-kitoblar — bir nechta view (xarajat xulosasi, keyinroq dashboard,
Excel hisobotlar) tomonidan qayta ishlatiladigan umumiy mantiq."""
import calendar
from datetime import date

from django.db.models import Q, Sum
from django.utils import timezone

from apps.teachers.models import TeacherSalaryPayment

from .models import Expense, PaymentTransaction


def resolve_period(request):
    """
    Query params'dan davr oralig'ini aniqlaydi:
      - ?start=YYYY-MM-DD&end=YYYY-MM-DD berilsa — shu oraliq ustuvor.
      - Aks holda ?month=&year= (yo'q bo'lsa — joriy oy).
    Xato bo'lsa ValueError chiqaradi (chaqiruvchi 400 qaytarishi kerak).
    """
    start = request.query_params.get('start')
    end   = request.query_params.get('end')
    if start and end:
        return date.fromisoformat(start), date.fromisoformat(end)

    now   = timezone.localdate()
    month = int(request.query_params.get('month', now.month))
    year  = int(request.query_params.get('year', now.year))
    if not (1 <= month <= 12):
        raise ValueError("month 1 dan 12 gacha bo'lishi kerak.")
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def compute_financial_summary(start_date, end_date):
    """
    TOTAL INCOME − TOTAL EXPENSES (ish haqi + boshqa xarajatlar) = NET RESULT.

    CASH BASIS (FIN-003): `total_income` here is Sum(PaymentTransaction.amount)
    filtered by the transaction's own `paid_at` date — i.e. cash actually
    collected within [start_date, end_date], regardless of which billing
    month/year the underlying Payment belongs to. This is intentionally a
    different figure from FinanceDashboardView's `expected_monthly_income` /
    `received_income`, which are ACCRUAL BASIS: Sum(Payment.amount /
    paid_amount) for Payment rows whose own `month`/`year` (billing period)
    matches the requested period, regardless of when the cash was received.
    A payment collected late (e.g. December cash for a November bill) is
    correctly counted once under each basis, in different periods — this is
    not double-counting, it's two legitimate, differently-defined figures.
    Do not unify these without an explicit product decision to do so.
    """
    income = PaymentTransaction.objects.valid().filter(
        paid_at__date__gte=start_date, paid_at__date__lte=end_date,
    ).aggregate(total=Sum('amount'))['total'] or 0

    salary_agg = TeacherSalaryPayment.objects.filter(
        paid_at__date__gte=start_date, paid_at__date__lte=end_date,
        status=TeacherSalaryPayment.Status.PAID,
    ).aggregate(amount=Sum('amount'), bonus=Sum('bonus'), deductions=Sum('deductions'))
    total_salaries = (
        (salary_agg['amount'] or 0) + (salary_agg['bonus'] or 0) - (salary_agg['deductions'] or 0)
    )

    other_expenses = Expense.objects.filter(
        expense_date__gte=start_date, expense_date__lte=end_date,
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_expenses = total_salaries + other_expenses

    return {
        'start_date':            str(start_date),
        'end_date':               str(end_date),
        'total_income':          float(income),
        'total_salaries':        float(total_salaries),
        'total_other_expenses':  float(other_expenses),
        'total_expenses':        float(total_expenses),
        'net_result':            float(income - total_expenses),
    }


def carry_recurring_expenses(month, year, user):
    """Davomli xarajatlarni (oldingi oyda is_recurring=True) shu oyga ko'chiradi.
    Qayta chaqirilsa takrorlamaydi: har bir asl xarajatdan oyiga bitta nusxa."""
    from django.db import transaction

    prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
    templates = Expense.objects.filter(is_recurring=True, expense_date__year=prev_year,
                                       expense_date__month=prev_month)
    last_day = calendar.monthrange(year, month)[1]
    created = []
    with transaction.atomic():
        for tpl in templates:
            origin = tpl.recurring_source_id or tpl.pk
            exists = Expense.objects.filter(
                expense_date__year=year, expense_date__month=month, is_recurring=True,
            ).filter(Q(recurring_source_id=origin) | Q(pk=origin)).exists()
            if exists:
                continue
            created.append(Expense.objects.create(
                name=tpl.name, category=tpl.category, amount=tpl.amount,
                expense_date=date(year, month, min(tpl.expense_date.day, last_day)),
                description=tpl.description, is_recurring=True,
                recurring_source_id=origin, created_by=user,
            ))
    return created
