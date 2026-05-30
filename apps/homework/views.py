import logging
from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend

from apps.accounts.permissions import IsAdminOrTeacher
from .models import Assignment, Submission
from .serializers import (
    AssignmentListSerializer, AssignmentDetailSerializer,
    AssignmentCreateSerializer, SubmissionSerializer,
    SubmissionCreateSerializer, GradeSubmissionSerializer,
)

logger = logging.getLogger('apps.homework')


class AssignmentListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/homework/assignments/          → barcha vazifalar (admin/teacher)
    POST /api/v1/homework/assignments/          → yangi vazifa yaratish
    """
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'group', 'teacher']
    search_fields    = ['title', 'description']
    ordering         = ['-due_date']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminOrTeacher()]
        return [IsAuthenticated()]

    def get_queryset(self):
        from django.db.models import Count, Q as Qf
        user = self.request.user
        qs = (
            Assignment.objects
            .select_related('group', 'teacher__user')
            .annotate(
                _submission_count=Count('submissions', distinct=True),
                _graded_count=Count(
                    'submissions',
                    filter=Qf(submissions__status='graded'),
                    distinct=True,
                ),
            )
        )

        if user.is_student:
            student = getattr(user, 'student_profile', None)
            if student and student.group:
                return qs.filter(group=student.group, status=Assignment.Status.ACTIVE)
            return qs.none()

        if user.is_teacher:
            teacher = getattr(user, 'teacher_profile', None)
            if teacher:
                return qs.filter(teacher=teacher)
            return qs.none()

        return qs

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AssignmentCreateSerializer
        return AssignmentListSerializer


class AssignmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PUT/DELETE /api/v1/homework/assignments/{id}/"""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs   = Assignment.objects.select_related('group', 'teacher__user')

        if user.is_student:
            student = getattr(user, 'student_profile', None)
            if student and student.group:
                return qs.filter(group=student.group)
            return qs.none()

        if user.is_teacher:
            teacher = getattr(user, 'teacher_profile', None)
            if teacher:
                return qs.filter(teacher=teacher)
            return qs.none()

        return qs

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AssignmentCreateSerializer
        return AssignmentDetailSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAdminOrTeacher()]
        return [IsAuthenticated()]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        data = AssignmentDetailSerializer(instance).data
        # Attach student's own submission if applicable
        if request.user.is_student:
            student = getattr(request.user, 'student_profile', None)
            if student:
                sub = Submission.objects.filter(assignment=instance, student=student).first()
                data['my_submission'] = SubmissionSerializer(sub).data if sub else None
        return Response(data)


class SubmissionListView(generics.ListAPIView):
    """
    GET /api/v1/homework/submissions/?assignment={id}
    Admin/Teacher barcha topshiriqlarni ko'radi
    """
    serializer_class = SubmissionSerializer
    permission_classes = [IsAdminOrTeacher]
    filter_backends  = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['assignment', 'student', 'status']
    ordering         = ['-submitted_at']

    def get_queryset(self):
        return Submission.objects.select_related(
            'student__user', 'assignment', 'graded_by'
        )


class SubmitAssignmentView(APIView):
    """
    POST /api/v1/homework/assignments/{id}/submit/
    O'quvchi vazifani topshiradi
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk)
        serializer = SubmissionCreateSerializer(
            data={**request.data, 'assignment': str(assignment.id)},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        submission = serializer.save()
        logger.info(f"Topshirildi: {submission.student.full_name} | {assignment.title}")
        return Response(SubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)


class GradeSubmissionView(APIView):
    """
    POST /api/v1/homework/submissions/{id}/grade/
    O'qituvchi/admin ball qo'yadi
    """
    permission_classes = [IsAdminOrTeacher]

    def post(self, request, pk):
        submission = get_object_or_404(
            Submission.objects.select_related('student', 'assignment__group'), pk=pk
        )

        if request.user.is_teacher:
            teacher = getattr(request.user, 'teacher_profile', None)
            if not teacher or not teacher.groups.filter(pk=submission.assignment.group.pk).exists():
                return Response(
                    {'detail': "Siz faqat o'z guruhingiz topshiriqlarini baholashingiz mumkin."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = GradeSubmissionSerializer(
            data=request.data,
            context={'submission': submission}
        )
        serializer.is_valid(raise_exception=True)
        submission.grade(
            score=serializer.validated_data['score'],
            feedback=serializer.validated_data['feedback'],
            graded_by=request.user,
        )
        return Response(SubmissionSerializer(submission).data)


class MyAssignmentsView(generics.ListAPIView):
    """
    GET /api/v1/homework/my/
    O'quvchining o'z vazifalari + topshirish holati
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = AssignmentListSerializer

    def get_queryset(self):
        user    = self.request.user
        student = getattr(user, 'student_profile', None)
        if not student or not student.group:
            return Assignment.objects.none()
        return Assignment.objects.filter(
            group=student.group, status=Assignment.Status.ACTIVE
        ).select_related('group', 'teacher__user').order_by('due_date')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        student  = getattr(request.user, 'student_profile', None)

        # Single query to fetch all student submissions for these assignments
        submission_map = {}
        if student:
            assignment_ids = queryset.values_list('id', flat=True)
            for sub in Submission.objects.filter(student=student, assignment_id__in=assignment_ids):
                submission_map[sub.assignment_id] = sub

        assignments_data = []
        for assignment in queryset:
            item = AssignmentListSerializer(assignment).data
            sub  = submission_map.get(assignment.id)
            item['my_submission'] = SubmissionSerializer(sub).data if sub else None
            assignments_data.append(item)

        return Response({'count': len(assignments_data), 'results': assignments_data})
