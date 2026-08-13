import calendar
from datetime import date

from django.db.models import Count, Q, Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin, IsFinanceOrAdmin
from apps.notifications.models import ActivityLog
from apps.notifications.views import log_activity
from apps.payments.models import Payment
from apps.payments.serializers import PaymentSerializer
from apps.students.models import Student

from .models import Asset, Expense, PaymentTransaction
from .serializers import (
    AssetSerializer,
    DebtorPaymentSerializer,
    ExpenseSerializer,
    PaymentTransactionSerializer,
    RecordPaymentSerializer,
)
from .services import compute_financial_summary, resolve_period


class RecordPaymentView(generics.CreateAPIView):
    """POST /api/v1/finance/transactions/record/ — to'lov qabul qilish (chek yaratadi)."""
    permission_classes = [IsFinanceOrAdmin]
    serializer_class    = RecordPaymentSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        txn = serializer.save()
        payment = Payment.objects.select_related('student__user', 'group').get(pk=txn.payment_id)
        log_activity(
            request.user, ActivityLog.Action.CREATE, 'PaymentTransaction',
            txn.pk, str(txn), request=request,
        )
        return Response(
            {
                'transaction': PaymentTransactionSerializer(txn).data,
                'payment':     PaymentSerializer(payment).data,
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentTransactionListView(generics.ListAPIView):
    """GET /api/v1/finance/transactions/?student=&payment= — to'lov tarixi (cheklar)."""
    permission_classes = [IsFinanceOrAdmin]
    serializer_class    = PaymentTransactionSerializer

    def get_queryset(self):
        qs = PaymentTransaction.objects.select_related(
            'payment__student__user', 'received_by'
        ).order_by('-paid_at')
        student_id = self.request.query_params.get('student')
        payment_id = self.request.query_params.get('payment')
        if student_id:
            qs = qs.filter(payment__student_id=student_id)
        if payment_id:
            qs = qs.filter(payment_id=payment_id)
        return qs


class TransactionDetailView(generics.RetrieveDestroyAPIView):
    """
    GET    /api/v1/finance/transactions/<uuid:pk>/ — bitta chek (chop etish sahifasi uchun).
    DELETE — to'lovni bekor qilish. Payment.paid_amount avtomatik qayta hisoblanadi
             (apps/finance/signals.py), audit jurnaliga 'bekor qilindi' deb yoziladi.
    """
    permission_classes = [IsFinanceOrAdmin]
    serializer_class    = PaymentTransactionSerializer
    queryset            = PaymentTransaction.objects.select_related(
        'payment__student__user', 'payment__group', 'received_by'
    )

    def perform_destroy(self, instance):
        repr_str = str(instance)
        pk = instance.pk
        instance.delete()
        log_activity(
            self.request.user, ActivityLog.Action.DELETE, 'PaymentTransaction',
            pk, repr_str, request=self.request,
        )


class DebtorsListView(generics.ListAPIView):
    """
    GET /api/v1/finance/debts/?month=&year=&group=&search=&overdue_only=
    Qarzdorlik ro'yxati — shu oy uchun PARTIAL/UNPAID to'lovlar, eng katta
    qarzdan boshlab tartiblangan, har birida umumiy (barcha oylik) qarz ham
    ko'rsatiladi — qarzdorlarni tez aniqlash uchun.
    """
    permission_classes = [IsFinanceOrAdmin]
    serializer_class    = DebtorPaymentSerializer
    pagination_class    = None  # qarzdorlar ro'yxati bitta ekranda to'liq ko'rinishi kerak

    def get_queryset(self):
        now = timezone.localdate()
        try:
            month = int(self.request.query_params.get('month', now.month))
            year  = int(self.request.query_params.get('year', now.year))
        except (TypeError, ValueError):
            month, year = now.month, now.year

        qs = Payment.objects.filter(
            month=month, year=year,
            status__in=[Payment.Status.UNPAID, Payment.Status.PARTIAL],
        ).select_related('student__user', 'group')

        group_id = self.request.query_params.get('group')
        if group_id:
            qs = qs.filter(group_id=group_id)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(student__user__full_name__icontains=search) |
                Q(student__phone__icontains=search)
            )

        rows = list(qs)
        if self.request.query_params.get('overdue_only') == 'true':
            rows = [p for p in rows if p.is_overdue]
        rows.sort(key=lambda p: p.debt_amount, reverse=True)
        return rows


class ExpenseViewSet(viewsets.ModelViewSet):
    """
    /api/v1/finance/expenses/ — Markaz xarajatlari CRUD.
    Filtr: ?category=&search=&month=&year= yoki ?start=&end=
    """
    permission_classes = [IsFinanceOrAdmin]
    serializer_class    = ExpenseSerializer
    filter_backends     = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields    = ['category']
    search_fields        = ['name', 'description']
    ordering             = ['-expense_date']

    def get_queryset(self):
        qs = Expense.objects.select_related('created_by')
        start = self.request.query_params.get('start')
        end   = self.request.query_params.get('end')
        month = self.request.query_params.get('month')
        year  = self.request.query_params.get('year')
        if start and end:
            qs = qs.filter(expense_date__gte=start, expense_date__lte=end)
        elif month and year:
            qs = qs.filter(expense_date__month=month, expense_date__year=year)
        return qs

    def perform_create(self, serializer):
        expense = serializer.save(created_by=self.request.user)
        log_activity(
            self.request.user, ActivityLog.Action.CREATE, 'Expense',
            expense.pk, str(expense), request=self.request,
        )

    def perform_update(self, serializer):
        expense = serializer.save()
        log_activity(
            self.request.user, ActivityLog.Action.UPDATE, 'Expense',
            expense.pk, str(expense), request=self.request,
        )

    def perform_destroy(self, instance):
        repr_str = str(instance)
        pk = instance.pk
        instance.delete()
        log_activity(
            self.request.user, ActivityLog.Action.DELETE, 'Expense',
            pk, repr_str, request=self.request,
        )


class ExpenseSummaryView(APIView):
    """
    GET /api/v1/finance/expenses/summary/?month=&year= (yoki ?start=&end=)
    TOTAL INCOME − TOTAL EXPENSES = NET RESULT.
    """
    permission_classes = [IsFinanceOrAdmin]

    def get(self, request):
        try:
            start_date, end_date = resolve_period(request)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(compute_financial_summary(start_date, end_date))


class AssetViewSet(viewsets.ModelViewSet):
    """
    /api/v1/finance/assets/ — Markaz mulklari CRUD (oddiy ro'yxat, ombor tizimi emas).
    Filtr: ?condition=&category=&search=
    Finance: view/add/edit. Faqat Admin/Developer o'chira oladi.
    """
    serializer_class    = AssetSerializer
    filter_backends     = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields    = ['condition']
    search_fields        = ['name', 'category']
    ordering             = ['-created_at']

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAdmin()]
        return [IsFinanceOrAdmin()]

    def get_queryset(self):
        return Asset.objects.select_related('created_by')

    def perform_create(self, serializer):
        asset = serializer.save(created_by=self.request.user)
        log_activity(
            self.request.user, ActivityLog.Action.CREATE, 'Asset',
            asset.pk, str(asset), request=self.request,
        )

    def perform_update(self, serializer):
        asset = serializer.save()
        log_activity(
            self.request.user, ActivityLog.Action.UPDATE, 'Asset',
            asset.pk, str(asset), request=self.request,
        )

    def perform_destroy(self, instance):
        repr_str = str(instance)
        pk = instance.pk
        instance.delete()
        log_activity(
            self.request.user, ActivityLog.Action.DELETE, 'Asset',
            pk, repr_str, request=self.request,
        )


class AssetSummaryView(APIView):
    """GET /api/v1/finance/assets/summary/ — jami mulklar qiymati va holat bo'yicha taqsimot."""
    permission_classes = [IsFinanceOrAdmin]

    def get(self, request):
        assets = list(Asset.objects.all())
        total_value = sum(a.total_value for a in assets)
        by_condition = {}
        for choice, _label in Asset.Condition.choices:
            by_condition[choice] = sum(
                a.total_value for a in assets if a.condition == choice
            )
        return Response({
            'total_assets':     len(assets),
            'total_value':      float(total_value),
            'value_by_condition': {k: float(v) for k, v in by_condition.items()},
        })


class StudentFinanceSummaryView(APIView):
    """
    GET /api/v1/finance/students/<uuid:pk>/summary/?month=&year=
    Moliya paneli — bitta o'quvchi bo'yicha to'liq ko'rinish:
    oylik to'lov, to'langan, qoldiq, qarz, holat + so'nggi to'lovlar tarixi.
    """
    permission_classes = [IsFinanceOrAdmin]

    def get(self, request, pk):
        try:
            student = Student.objects.select_related('user', 'group').get(pk=pk)
        except Student.DoesNotExist:
            return Response({'detail': "O'quvchi topilmadi."}, status=404)

        now = timezone.localdate()
        try:
            month = int(request.query_params.get('month', now.month))
            year  = int(request.query_params.get('year', now.year))
        except (ValueError, TypeError):
            return Response({'detail': "month va year butun son bo'lishi kerak."}, status=400)
        if not (1 <= month <= 12):
            return Response({'detail': "month 1 dan 12 gacha bo'lishi kerak."}, status=400)

        current_payment = Payment.objects.filter(
            student=student, month=month, year=year
        ).select_related('group').first()

        history = Payment.objects.filter(student=student).select_related('group').order_by('-year', '-month')[:12]

        return Response({
            'student_id':      str(student.id),
            'full_name':       student.full_name,
            'phone':           student.phone,
            'group_id':        str(student.group_id) if student.group_id else None,
            'group_name':      student.group.name if student.group else None,
            'monthly_fee':     student.group.monthly_fee if student.group else None,
            'month':           month,
            'year':            year,
            'current_payment': PaymentSerializer(current_payment).data if current_payment else None,
            'total_debt':      float(student.total_debt),
            'history':         PaymentSerializer(history, many=True).data,
        })


class FinanceDashboardView(APIView):
    """
    GET /api/v1/finance/dashboard/?month=&year=
    Moliya panelining bosh sahifasi uchun barcha ko'rsatkichlar bitta so'rovda.
    """
    permission_classes = [IsFinanceOrAdmin]

    def get(self, request):
        now = timezone.localdate()
        try:
            month = int(request.query_params.get('month', now.month))
            year  = int(request.query_params.get('year', now.year))
        except (TypeError, ValueError):
            return Response({'detail': "month va year butun son bo'lishi kerak."}, status=400)
        if not (1 <= month <= 12):
            return Response({'detail': "month 1 dan 12 gacha bo'lishi kerak."}, status=400)

        payment_agg = Payment.objects.filter(month=month, year=year).aggregate(
            expected = Sum('amount'),
            received = Sum('paid_amount'),
            debt     = Sum('debt_amount'),
            paid     = Count('id', filter=Q(status=Payment.Status.PAID)),
            partial  = Count('id', filter=Q(status=Payment.Status.PARTIAL)),
            unpaid   = Count('id', filter=Q(status=Payment.Status.UNPAID)),
        )

        today_income = PaymentTransaction.objects.filter(
            paid_at__date=now
        ).aggregate(total=Sum('amount'))['total'] or 0

        last_day = calendar.monthrange(year, month)[1]
        month_summary = compute_financial_summary(date(year, month, 1), date(year, month, last_day))

        total_debt_all_time = Payment.objects.aggregate(total=Sum('debt_amount'))['total'] or 0
        assets = list(Asset.objects.all())
        total_asset_value = sum(a.total_value for a in assets)

        return Response({
            'month': month,
            'year':  year,
            'expected_monthly_income':      float(payment_agg['expected'] or 0),
            'received_income':              float(payment_agg['received'] or 0),
            'outstanding_debt_this_month':  float(payment_agg['debt'] or 0),
            'outstanding_debt_total':       float(total_debt_all_time),
            'paid_students':                payment_agg['paid'] or 0,
            'partial_students':             payment_agg['partial'] or 0,
            'unpaid_students':              payment_agg['unpaid'] or 0,
            'today_income':                 float(today_income),
            'monthly_income':               month_summary['total_income'],
            'teacher_salaries':             month_summary['total_salaries'],
            'expenses':                     month_summary['total_other_expenses'],
            'net_result':                   month_summary['net_result'],
            'total_asset_value':            float(total_asset_value),
        })
