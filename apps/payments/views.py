import logging

from django.db.models import Count, Q, Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrTeacher, IsFinance, IsFinanceOrAdmin
from apps.notifications.models import ActivityLog
from apps.notifications.views import diff_fields, log_activity

from .models import Payment
from .serializers import (
    PaymentCreateSerializer,
    PaymentSerializer,
    PaymentUpdateSerializer,
)
from .services import generate_monthly_invoices

logger = logging.getLogger('apps.payments')


class PaymentViewSet(generics.ListCreateAPIView):
    """
    GET  /api/v1/payments/?month=5&year=2025&status=unpaid  → Admin+Teacher+Moliyachi
    POST /api/v1/payments/  — oylik HISOB ochish (pul emas)  → Admin yoki Moliyachi
    """
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'month', 'year', 'student', 'group']
    search_fields    = ['student__user__full_name']
    ordering         = ['-year', '-month']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsFinanceOrAdmin()]
        return [(IsAdminOrTeacher | IsFinance)()]

    def get_queryset(self):
        qs   = Payment.objects.select_related('student__user', 'group', 'received_by')
        user = self.request.user
        if user.is_teacher:
            teacher = getattr(user, 'teacher_profile', None)
            if teacher:
                # Hisob ochilgan paytdagi guruh bo'yicha (o'quvchi keyin boshqa guruhga
                # o'tgan bo'lsa ham); guruhsiz eski hisoblar — o'quvchining joriy guruhi bo'yicha
                return qs.filter(
                    Q(group__teacher=teacher) |
                    Q(group__isnull=True, student__group__teacher=teacher)
                )
            return qs.none()
        return qs

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PaymentCreateSerializer
        return PaymentSerializer

    def create(self, request, *args, **kwargs):
        serializer = PaymentCreateSerializer(
            data=request.data, context={'request': request}
        )
        if not serializer.is_valid():
            first_field = next(iter(serializer.errors.keys()), 'unknown')
            first_error = next(iter(serializer.errors.values()), ['Xato'])[0]
            return Response(
                {'detail': f'{first_field}: {first_error}', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payment = serializer.save()
        if serializer.was_created:
            log_activity(
                request.user, ActivityLog.Action.CREATE, 'Payment',
                payment.pk, str(payment), request=request,
            )
        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED if serializer.was_created else status.HTTP_200_OK,
        )


class PaymentDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH → Admin yoki Moliyachi (narx va chegirma — faqat admin, PaymentUpdateSerializer)"""
    queryset           = Payment.objects.all()
    permission_classes = [IsFinanceOrAdmin]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return PaymentUpdateSerializer
        return PaymentSerializer

    http_method_names = ['get', 'patch', 'head', 'options']

    def perform_update(self, serializer):
        fields = ('amount', 'discount', 'debt_amount', 'status', 'note')
        before = {f: getattr(serializer.instance, f) for f in fields}
        payment = serializer.save()
        changes = diff_fields(before, payment, fields)
        log_activity(
            self.request.user, ActivityLog.Action.UPDATE, 'Payment',
            payment.pk, str(payment), changes=changes, request=self.request,
        )


class UnpaidStudentsView(APIView):
    """GET /api/v1/payments/unpaid/ — Admin yoki Moliyachi"""
    permission_classes = [IsFinanceOrAdmin]

    def get(self, request):
        now = timezone.now()
        try:
            month = int(request.query_params.get('month', now.month))
            year  = int(request.query_params.get('year',  now.year))
        except (ValueError, TypeError):
            return Response({'detail': "month va year butun son bo'lishi kerak."}, status=400)
        if not (1 <= month <= 12):
            return Response({'detail': "month 1 dan 12 gacha bo'lishi kerak."}, status=400)
        if not (2000 <= year <= 2100):
            return Response({'detail': "year 2000-2100 orasida bo'lishi kerak."}, status=400)

        unpaid = Payment.objects.filter(
            month=month, year=year,
            status__in=[Payment.Status.UNPAID, Payment.Status.PARTIAL]
        ).select_related('student__user', 'group')

        return Response(PaymentSerializer(unpaid, many=True).data)


class MonthlySummaryView(APIView):
    """GET /api/v1/payments/summary/ — Admin yoki Moliyachi"""
    permission_classes = [IsFinanceOrAdmin]

    def get(self, request):
        now = timezone.now()
        try:
            month = int(request.query_params.get('month', now.month))
            year  = int(request.query_params.get('year',  now.year))
        except (ValueError, TypeError):
            return Response({'detail': "month va year butun son bo'lishi kerak."}, status=400)
        if not (1 <= month <= 12):
            return Response({'detail': "month 1 dan 12 gacha bo'lishi kerak."}, status=400)
        if not (2000 <= year <= 2100):
            return Response({'detail': "year 2000-2100 orasida bo'lishi kerak."}, status=400)

        result = Payment.objects.filter(month=month, year=year).aggregate(
            total_amount  = Sum('amount'),
            total_paid    = Sum('paid_amount'),
            total_debt    = Sum('debt_amount'),
            paid_count    = Count('id', filter=Q(status='paid')),
            partial_count = Count('id', filter=Q(status='partial')),
            unpaid_count  = Count('id', filter=Q(status='unpaid')),
        )
        result['month'] = month
        result['year']  = year
        return Response(result)


class GenerateInvoicesView(APIView):
    """POST /api/v1/payments/generate/ {"month": 9, "year": 2026} — barcha faol o'quvchilarga
    shu oy hisobini ochadi. Takroriy chaqiruv xavfsiz (mavjud hisoblarga tegmaydi)."""
    permission_classes = [IsFinanceOrAdmin]

    def post(self, request):
        try:
            month = int(request.data.get('month'))
            year  = int(request.data.get('year'))
        except (ValueError, TypeError):
            return Response({'detail': "month va year butun son bo'lishi kerak."}, status=400)
        if not (1 <= month <= 12) or not (2000 <= year <= 2100):
            return Response({'detail': "Oy yoki yil noto'g'ri."}, status=400)
        result = generate_monthly_invoices(month, year)
        if result['created']:
            log_activity(
                request.user, ActivityLog.Action.CREATE, 'Payment', '',
                f"Oylik hisoblash {year}/{month:02d}: {result['created']} ta yangi hisob",
                request=request,
            )
        return Response(result)


class MyPaymentsView(generics.ListAPIView):
    """GET /api/v1/payments/my/ — current student's payment history."""
    permission_classes = [IsAuthenticated]
    serializer_class   = PaymentSerializer

    def get_queryset(self):
        from apps.students.models import Student
        try:
            student = Student.objects.get(user=self.request.user)
            return Payment.objects.filter(student=student).order_by('-year', '-month')
        except Student.DoesNotExist:
            return Payment.objects.none()
