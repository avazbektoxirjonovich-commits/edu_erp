"""
python manage.py payments_audit [--month 9 --year 2026] [--details]

FAQAT O'QIYDI — bazaga hech narsa yozmaydi. Deploy'dan oldin va keyin jonli
bazada ishga tushirib, to'lov ma'lumotlarining holatini ko'rish uchun.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Count, DecimalField, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.payments.models import Payment
from apps.students.models import Student

ZERO = Value(Decimal(0), output_field=DecimalField(max_digits=14, decimal_places=0))


class Command(BaseCommand):
    help = "To'lov ma'lumotlarini tekshiradi (faqat o'qiydi)"

    def add_arguments(self, parser):
        parser.add_argument('--month', type=int, default=None)
        parser.add_argument('--year', type=int, default=None)
        parser.add_argument('--details', action='store_true', help="Har bir muammoli yozuvni ko'rsatish")

    def handle(self, *args, **options):
        from apps.finance.models import PaymentTransaction

        today = timezone.localdate()
        month = options['month'] or today.month
        year = options['year'] or today.year
        details = options['details']

        valid_sum = Subquery(
            PaymentTransaction.objects.filter(payment=OuterRef('pk'), is_cancelled=False)
            .values('payment').annotate(s=Sum('amount')).values('s')[:1]
        )
        payments = Payment.objects.annotate(receipts=Coalesce(valid_sum, ZERO))

        uncovered = payments.filter(paid_amount__gt=F('receipts'))
        overcovered = payments.filter(paid_amount__lt=F('receipts'))
        overpaid = Payment.objects.filter(paid_amount__gt=F('amount') - F('discount'))
        duplicates = (
            Payment.objects.values('student', 'month', 'year')
            .annotate(n=Count('id')).filter(n__gt=1)
        )
        active = Student.objects.filter(status=Student.Status.ACTIVE).select_related('group', 'user')
        billed_ids = set(
            Payment.objects.filter(month=month, year=year).values_list('student_id', flat=True)
        )
        no_invoice = [s for s in active if s.pk not in billed_ids and s.effective_monthly_fee]
        no_fee = [s for s in active if not s.effective_monthly_fee]

        w = self.stdout.write
        w(self.style.MIGRATE_HEADING(f"TO'LOVLAR TEKSHIRUVI — {year}/{month:02d}"))
        w(f"Jami hisoblar: {Payment.objects.count()}, jami cheklar: {PaymentTransaction.objects.count()}")
        self._row("Chek bilan qoplanmagan to'langan summa (migratsiya 'eski yozuv' chek yaratadi)",
                  uncovered, details, lambda p: f"{p} — to'langan {p.paid_amount}, cheklar {p.receipts}")
        self._row("To'langan summa cheklardan KAM (qo'lda ko'rib chiqish kerak)",
                  overcovered, details, lambda p: f"{p} — to'langan {p.paid_amount}, cheklar {p.receipts}")
        self._row("Ortiqcha to'langan hisoblar", overpaid, details,
                  lambda p: f"{p} — summa {p.amount}, chegirma {p.discount}, to'langan {p.paid_amount}")
        self._row("Bir oyga bir nechta hisob (o'quvchi+oy)", duplicates, details,
                  lambda d: f"student={d['student']} {d['year']}/{d['month']:02d} — {d['n']} ta")
        self._row(f"Faol, narxi bor, lekin {year}/{month:02d} hisobi YO'Q (qarzi ko'rinmayapti)",
                  no_invoice, details, lambda s: f"{s.full_name} — {s.effective_monthly_fee}")
        self._row("Faol, lekin narxi yo'q (guruhsiz va shaxsiy narxsiz)", no_fee, details,
                  lambda s: s.full_name)
        cancelled = PaymentTransaction.objects.filter(is_cancelled=True).aggregate(
            n=Count('id'), s=Coalesce(Sum('amount'), ZERO))
        w(f"Bekor qilingan cheklar: {cancelled['n']} ta, {cancelled['s']:,.0f} so'm")
        unknown = PaymentTransaction.objects.filter(payment_type='unknown').aggregate(
            n=Count('id'), s=Coalesce(Sum('amount'), ZERO))
        w(f"'Noma'lum (eski yozuv)' cheklar: {unknown['n']} ta, {unknown['s']:,.0f} so'm")
        debt_q = Q(status__in=[Payment.Status.UNPAID, Payment.Status.PARTIAL])
        total_debt = Payment.objects.filter(debt_q).aggregate(s=Coalesce(Sum('debt_amount'), ZERO))['s']
        w(f"Jami qayd etilgan qarz: {total_debt:,.0f} so'm")

    def _row(self, title, items, details, fmt):
        items = list(items)
        style = self.style.WARNING if items else self.style.SUCCESS
        self.stdout.write(style(f"- {title}: {len(items)}"))
        if details:
            for item in items[:200]:
                self.stdout.write(f"    {fmt(item)}")
