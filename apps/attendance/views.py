import logging
from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from apps.accounts.permissions import IsAdminOrTeacher
from .models import Attendance
from .serializers import AttendanceSerializer, BulkAttendanceSerializer

logger = logging.getLogger('apps.attendance')


class AttendanceListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/attendance/ → Admin+Teacher (teacher faqat o'z guruhi)
    POST /api/v1/attendance/ → Admin+Teacher
    """
    serializer_class   = AttendanceSerializer
    permission_classes = [IsAdminOrTeacher]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['group', 'student', 'date', 'status']
    ordering_fields    = ['date']
    ordering           = ['-date']

    def get_queryset(self):
        qs   = Attendance.objects.select_related('student__user', 'group').all()
        user = self.request.user
        if user.is_teacher:
            teacher = getattr(user, 'teacher_profile', None)
            if teacher:
                return qs.filter(group__teacher=teacher)
            return qs.none()
        return qs

    def perform_create(self, serializer):
        serializer.save(marked_by=self.request.user)


class AttendanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PUT/DELETE /api/v1/attendance/{id}/"""
    queryset           = Attendance.objects.all()
    serializer_class   = AttendanceSerializer
    permission_classes = [IsAdminOrTeacher]


class BulkAttendanceView(APIView):
    """
    POST /api/v1/attendance/bulk/
    Bir vaqtda butun guruh davomatini belgilash.
    """
    permission_classes = [IsAdminOrTeacher]

    def post(self, request):
        serializer = BulkAttendanceSerializer(
            data=request.data, context={'request': request}
        )
        if serializer.is_valid():
            created = serializer.save()
            logger.info(f"Bulk davomat: {len(created)} ta yozuv | {request.user}")
            return Response(
                {'created': len(created)},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MyAttendanceView(generics.ListAPIView):
    """GET /api/v1/attendance/my/ — current student's attendance records."""
    permission_classes = [IsAuthenticated]
    serializer_class   = AttendanceSerializer

    def get_queryset(self):
        from apps.students.models import Student
        try:
            student = Student.objects.get(user=self.request.user)
            return Attendance.objects.filter(student=student).select_related('group').order_by('-date')
        except Student.DoesNotExist:
            return Attendance.objects.none()
