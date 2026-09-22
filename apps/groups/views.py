from django.db import transaction
from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.accounts.permissions import IsAdmin, IsAdminOrTeacher, IsFinance

from .models import Group, LessonSchedule, Room
from .rooms import assert_no_conflicts, resolve_room_name
from .serializers import GroupCreateSerializer, GroupListSerializer, RoomSerializer


class GroupViewSet(ModelViewSet):
    """
    GET    → Admin + Teacher (teacher faqat o'z guruhlari)
    POST/PUT/DELETE → Admin only
    """
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'teacher']
    search_fields    = ['name', 'subject']
    ordering_fields  = ['name', 'created_at', 'start_date']
    ordering         = ['-created_at']

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'update', 'partial_update']:
            return [IsAdmin()]
        return [(IsAdminOrTeacher | IsFinance)()]

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

    @action(detail=True, methods=['post'], url_path='set-schedule', permission_classes=[IsAdmin])
    def set_schedule(self, request, pk=None):
        group = self.get_object()
        pairs = []
        for s in request.data.get('schedules', []):
            day = s.get('day_of_week')
            if day is None:
                continue
            try:
                day = int(day)
            except (TypeError, ValueError):
                return Response({'detail': "Hafta kuni noto'g'ri."}, status=400)
            if not 1 <= day <= 7:
                return Response({'detail': "Hafta kuni 1 dan 7 gacha bo'lishi kerak."}, status=400)
            pairs.append((day, resolve_room_name(s.get('room', ''))))
        # Xona band bo'lsa — hech narsa o'zgarmaydi
        assert_no_conflicts(group, pairs)
        with transaction.atomic():
            group.schedules.all().delete()
            created = [LessonSchedule.objects.create(group=group, day_of_week=d, room=r)
                       for d, r in dict(pairs).items()]
        return Response({'schedules': [{'id': str(o.id), 'day_of_week': o.day_of_week, 'room': o.room}
                                       for o in created],
                         'count': len(created)})


class RoomViewSet(ModelViewSet):
    """
    /api/v1/groups/rooms/ — xonalar ro'yxati (qaysi guruh, qaysi kun va soatda band).
    Ko'rish: admin, o'qituvchi, moliyachi; o'zgartirish: admin.
    """
    serializer_class = RoomSerializer
    queryset         = Room.objects.all()

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'update', 'partial_update']:
            return [IsAdmin()]
        return [(IsAdminOrTeacher | IsFinance)()]

    def perform_update(self, serializer):
        old_name = serializer.instance.name
        with transaction.atomic():
            room = serializer.save()
            if room.name != old_name:
                LessonSchedule.objects.filter(room__iexact=old_name).update(room=room.name)

    def destroy(self, request, *args, **kwargs):
        room = self.get_object()
        if LessonSchedule.objects.filter(room__iexact=room.name).exists():
            return Response({'detail': "Bu xonada darslar bor — avval guruhlar jadvalidan olib tashlang "
                                       "yoki xonani nofaol qiling."}, status=400)
        return super().destroy(request, *args, **kwargs)
