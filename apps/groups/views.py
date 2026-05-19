from rest_framework.viewsets import ModelViewSet
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from apps.accounts.permissions import IsAdminOrTeacher, IsAdmin
from .models import Group
from .serializers import GroupListSerializer, GroupCreateSerializer


class GroupViewSet(ModelViewSet):
    """
    GET    → Admin + Teacher (teacher faqat o'z guruhlari)
    POST/PUT/DELETE → Admin only
    """
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'teacher', 'branch']
    search_fields    = ['name', 'subject']
    ordering_fields  = ['name', 'created_at', 'start_date']
    ordering         = ['-created_at']

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'update', 'partial_update']:
            return [IsAdmin()]
        return [IsAdminOrTeacher()]

    def get_queryset(self):
        qs = (
            Group.objects
            .select_related('teacher__user')
            .prefetch_related('schedules')
            .annotate(
                _student_count=Count(
                    'students',
                    filter=Q(students__status='active'),
                    distinct=True,
                )
            )
        )
        user = self.request.user
        if user.is_teacher:
            teacher = getattr(user, 'teacher_profile', None)
            if teacher:
                return qs.filter(teacher=teacher)
            return qs.none()
        return qs

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return GroupCreateSerializer
        return GroupListSerializer
