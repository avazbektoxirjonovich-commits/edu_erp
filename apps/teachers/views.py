from rest_framework.viewsets import ModelViewSet
from rest_framework import filters, generics
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from apps.accounts.permissions import IsAdmin
from .models import Teacher, TeacherSalaryPayment
from .serializers import (
    TeacherSerializer, TeacherCreateSerializer,
    TeacherUpdateSerializer, TeacherSalaryPaymentSerializer,
)


class TeacherViewSet(ModelViewSet):
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields    = ['user__full_name', 'subject', 'phone']
    ordering         = ['-created_at']

    def get_permissions(self):
        return [IsAdmin()]

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
        from apps.notifications.views import log_activity
        from apps.notifications.models import ActivityLog
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
    permission_classes = [IsAdmin]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['teacher', 'month', 'year']
    ordering           = ['-year', '-month']

    def get_queryset(self):
        return TeacherSalaryPayment.objects.select_related('teacher__user', 'paid_by')


class TeacherSalaryDetailView(generics.RetrieveDestroyAPIView):
    serializer_class   = TeacherSalaryPaymentSerializer
    permission_classes = [IsAdmin]
    queryset           = TeacherSalaryPayment.objects.select_related('teacher__user', 'paid_by')
