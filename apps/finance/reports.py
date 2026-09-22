"""
Moliya hisobotlari (davr bo'yicha):
  - kassirlar: kim qancha pul qabul qildi, qaysi turda, qachon (har bir chek bilan)
  - to'lov turlari bo'yicha jami
  - oyliklar: kimga qancha berildi, qachon, kim berdi

Pul summalari FAQAT bekor qilinmagan cheklardan; bekor qilinganlari alohida ko'rsatiladi.
"""
from collections import defaultdict

from django.db.models import Count, Sum
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsFinanceOrAdmin
from apps.teachers.models import TeacherSalaryPayment

from .models import PaymentTransaction
from .services import resolve_period

TYPE_LABELS = dict(PaymentTransaction.PaymentType.choices)


def _money(v):
    return float(v or 0)


def cashier_report(start, end):
    base = PaymentTransaction.objects.filter(paid_at__date__gte=start, paid_at__date__lte=end)
    valid = base.valid()

    by_type = [
        {'payment_type': row['payment_type'], 'label': TYPE_LABELS.get(row['payment_type'], row['payment_type']),
         'total': _money(row['total']), 'count': row['count']}
        for row in valid.values('payment_type').annotate(total=Sum('amount'), count=Count('id'))
                        .order_by('payment_type')
    ]

    cashiers = defaultdict(lambda: {'total': 0.0, 'count': 0, 'by_type': defaultdict(float)})
    names = {}
    for row in valid.values('received_by', 'received_by__full_name', 'payment_type').annotate(
            total=Sum('amount'), count=Count('id')):
        c = cashiers[row['received_by']]
        names[row['received_by']] = row['received_by__full_name'] or '—'
        c['total'] += _money(row['total'])
        c['count'] += row['count']
        c['by_type'][row['payment_type']] += _money(row['total'])
    cashier_rows = sorted(
        ({'user_id': uid, 'name': names[uid], 'total': c['total'], 'count': c['count'],
          'by_type': dict(c['by_type'])} for uid, c in cashiers.items()),
        key=lambda r: (-r['total'], r['name']),
    )

    receipts = [{
        'id': str(t.pk), 'paid_at': t.paid_at, 'receipt_number': t.receipt_number,
        'student_name': t.payment.student.user.full_name,
        'month': t.payment.month, 'year': t.payment.year,
        'amount': _money(t.amount), 'payment_type': t.payment_type,
        'payment_type_display': t.get_payment_type_display(),
        'received_by_name': t.received_by.full_name if t.received_by else None,
        'is_cancelled': t.is_cancelled, 'cancel_reason': t.cancel_reason,
    } for t in base.select_related('payment__student__user', 'received_by').order_by('-paid_at')]

    cancelled = base.filter(is_cancelled=True).aggregate(total=Sum('amount'), count=Count('id'))
    return {
        'total': sum(r['total'] for r in by_type),
        'count': sum(r['count'] for r in by_type),
        'by_type': by_type,
        'cashiers': cashier_rows,
        'receipts': receipts,
        'cancelled': {'total': _money(cancelled['total']), 'count': cancelled['count']},
    }


def salary_report(start, end):
    rows = (TeacherSalaryPayment.objects
            .filter(paid_at__date__gte=start, paid_at__date__lte=end,
                    status=TeacherSalaryPayment.Status.PAID)
            .select_related('teacher__user', 'paid_by').order_by('-paid_at'))
    items = [{
        'id': str(s.pk), 'teacher_name': s.teacher.user.full_name,
        'month': s.month, 'year': s.year,
        'amount': _money(s.amount), 'bonus': _money(s.bonus), 'deductions': _money(s.deductions),
        'total': _money(s.total), 'paid_at': s.paid_at,
        'paid_by_name': s.paid_by.full_name if s.paid_by else None, 'note': s.note,
    } for s in rows]
    per_teacher = defaultdict(float)
    for i in items:
        per_teacher[i['teacher_name']] += i['total']
    return {
        'total': sum(i['total'] for i in items),
        'items': items,
        'by_teacher': sorted(({'teacher_name': k, 'total': v} for k, v in per_teacher.items()),
                             key=lambda r: -r['total']),
    }


class FinanceReportView(APIView):
    """GET /api/v1/finance/reports/?start=YYYY-MM-DD&end=YYYY-MM-DD (yoki ?month=&year=)"""
    permission_classes = [IsFinanceOrAdmin]

    def get(self, request):
        try:
            start, end = resolve_period(request)
        except ValueError as e:
            return Response({'detail': str(e) or "Sana noto'g'ri (YYYY-MM-DD)."}, status=400)
        if start > end:
            return Response({'detail': "Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas."}, status=400)
        return Response({
            'start': str(start), 'end': str(end),
            'payments': cashier_report(start, end),
            'salaries': salary_report(start, end),
        })
