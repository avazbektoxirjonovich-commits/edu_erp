from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics
from rest_framework.viewsets import ModelViewSet

from apps.accounts.permissions import IsAdmin, IsFinance, IsFinanceOrAdmin
from apps.notifications.models import ActivityLog
from apps.notifications.views import diff_fields, log_activity

from .models import Teacher, TeacherSalaryPayment
from .serializers import (
    TeacherCreateSerializer,
    TeacherSalaryPaymentSerializer,
    TeacherSerializer,
    TeacherUpdateSerializer,
)


class TeacherViewSet(ModelViewSet):
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields    = ['user__full_name', 'subject', 'phone']
    ordering         = ['-created_at']

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'update', 'partial_update']:
            return [IsAdmin()]
        return [(IsAdmin | IsFinance)()]

    def get_queryset(self):
        return (
            Teacher.objects
            .select_related('user')
            .annotate(
                _group_count=Count(
                    'groups',
                    filter=Q(groups__status='active'),
                    distinct=True,
                )
            )
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return TeacherCreateSerializer
        if self.action in ['update', 'partial_update']:
            return TeacherUpdateSerializer
        return TeacherSerializer

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        instance.user.is_active = False
        instance.user.save(update_fields=['is_active'])
        log_activity(
            self.request.user, ActivityLog.Action.DELETE, 'Teacher',
            instance.pk, str(instance), request=self.request,
        )


class TeacherSalaryListCreateView(generics.ListCreateAPIView):
    serializer_class   = TeacherSalaryPaymentSerializer
    permission_classes = [IsFinanceOrAdmin]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['teacher', 'month', 'year', 'status']
    ordering           = ['-year', '-month']

    def get_queryset(self):
        return TeacherSalaryPayment.objects.select_related('teacher__user', 'paid_by')

    def perform_create(self, serializer):
        salary = serializer.save()
        log_activity(
            self.request.user, ActivityLog.Action.CREATE, 'TeacherSalaryPayment',
            salary.pk, str(salary), request=self.request,
        )


class TeacherSalaryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/PUT — masalan pending yozuvni to'langan qilib belgilash. DELETE — bekor qilish."""
    serializer_class   = TeacherSalaryPaymentSerializer
    permission_classes = [IsFinanceOrAdmin]
    queryset           = TeacherSalaryPayment.objects.select_related('teacher__user', 'paid_by')

    def perform_update(self, serializer):
        before = {f: getattr(serializer.instance, f) for f in
                  ('amount', 'worked_hours', 'bonus', 'deductions', 'status')}
        salary = serializer.save()
        changes = diff_fields(before, salary,
                               ('amount', 'worked_hours', 'bonus', 'deductions', 'status'))
        log_activity(
            self.request.user, ActivityLog.Action.UPDATE, 'TeacherSalaryPayment',
            salary.pk, str(salary), changes=changes, request=self.request,
        )

    def perform_destroy(self, instance):
        repr_str = str(instance)
        pk = instance.pk
        instance.delete()
        log_activity(
            self.request.user, ActivityLog.Action.DELETE, 'TeacherSalaryPayment',
            pk, repr_str, request=self.request,
        )
