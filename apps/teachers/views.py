from rest_framework.viewsets import ModelViewSet
from rest_framework import filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from apps.accounts.permissions import IsAdmin
from .models import Teacher
from .serializers import TeacherSerializer, TeacherCreateSerializer


class TeacherViewSet(ModelViewSet):
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'branch']
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
        if self.action in ['create', 'update', 'partial_update']:
            return TeacherCreateSerializer
        return TeacherSerializer
