import logging
from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

from apps.accounts.permissions import IsAdmin
from .models import Payment
from .serializers import (
    PaymentSerializer, PaymentCreateSerializer,
    PaymentUpdateSerializer, MonthlyPaymentSummarySerializer
)

logger = logging.getLogger('apps.payments')


class PaymentViewSet(generics.ListCreateAPIView):
    """
    GET  /api/v1/payments/?month=5&year=2025&status=unpaid  → Admin+Teacher
    POST /api/v1/payments/                                   → Admin only
    """
    permission_classes = [IsAdmin]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = ['status', 'month', 'year', 'student', 'group']
    search_fields      = ['student__user__full_name']
    ordering           = ['-year', '-month']

    def get_queryset(self):
        return Payment.objects.select_related(
            'student__user', 'group', 'received_by'
        ).all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PaymentCreateSerializer
        return PaymentSerializer


class PaymentDetailView(generics.RetrieveUpdateAPIView):
    """GET/PUT/PATCH → Admin only"""
    queryset           = Payment.objects.all()
    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return PaymentUpdateSerializer
        return PaymentSerializer


class UnpaidStudentsView(APIView):
    """GET /api/v1/payments/unpaid/ — Admin only"""
    permission_classes = [IsAdmin]

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
    """GET /api/v1/payments/summary/ — Admin only"""
    permission_classes = [IsAdmin]

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
