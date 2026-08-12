"""Moliyaviy hisob-kitoblar — bir nechta view (xarajat xulosasi, keyinroq dashboard,
Excel hisobotlar) tomonidan qayta ishlatiladigan umumiy mantiq."""
import calendar
from datetime import date

from django.db.models import Sum
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
    """TOTAL INCOME − TOTAL EXPENSES (ish haqi + boshqa xarajatlar) = NET RESULT."""
    income = PaymentTransaction.objects.filter(
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
