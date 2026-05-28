import logging
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q, Sum, DecimalField
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend

from apps.accounts.permissions import IsAdminOrTeacher, IsAdmin, IsStudent
from apps.notifications.views import log_activity
from apps.notifications.models import ActivityLog
from .models import Student
from .serializers import (
    StudentListSerializer, StudentDetailSerializer,
    StudentCreateSerializer, StudentUpdateSerializer
)

logger = logging.getLogger('apps.students')


class StudentViewSet(ModelViewSet):
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'group']
    search_fields    = ['user__full_name', 'phone']
    ordering_fields  = ['user__full_name', 'joined_date', 'created_at']
    ordering         = ['-created_at']

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'update', 'partial_update']:
            return [IsAdmin()]
        return [IsAdminOrTeacher()]

    def get_queryset(self):
        from apps.attendance.models import Attendance
        from apps.payments.models import Payment

        qs = Student.objects.select_related('user', 'group')

        # Teacher faqat o'z guruhi o'quvchilarini ko'radi
        user = self.request.user
        if user.is_teacher:
            teacher = getattr(user, 'teacher_profile', None)
            if teacher:
                qs = qs.filter(group__teacher=teacher)
            else:
                return qs.none()

        if self.action == 'list':
            # Single optimized query: annotate attendance % and total debt
            qs = qs.annotate(
                _total_attend=Count('attendances', distinct=True),
                _present=Count(
                    'attendances',
                    filter=Q(attendances__status='present'),
                    distinct=True
                ),
                _total_debt=Coalesce(
                    Sum('payments__debt_amount',
                        output_field=DecimalField(max_digits=12, decimal_places=0)),
                    0,
                    output_field=DecimalField(max_digits=12, decimal_places=0)
                ),
            )
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return StudentListSerializer
        elif self.action == 'create':
            return StudentCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return StudentUpdateSerializer
        return StudentDetailSerializer

    def perform_create(self, serializer):
        student = serializer.save()
        logger.info(f"Yangi o'quvchi: {student.full_name} | Guruh: {student.group}")
        log_activity(
            self.request.user, ActivityLog.Action.CREATE, 'Student',
            student.pk, str(student), request=self.request,
        )

    def perform_update(self, serializer):
        student = serializer.save()
        log_activity(
            self.request.user, ActivityLog.Action.UPDATE, 'Student',
            student.pk, str(student), request=self.request,
        )

    def perform_destroy(self, instance):
        repr_str = str(instance)
        pk       = instance.pk
        user     = instance.user
        log_activity(
            self.request.user, ActivityLog.Action.DELETE, 'Student',
            pk, repr_str, request=self.request,
        )
        user.delete()  # cascades: Student → payments, attendance, submissions

    @action(detail=True, methods=['post'], url_path='create-parent', permission_classes=[IsAdmin])
    def create_parent(self, request, pk=None):
        """POST /students/{id}/create-parent/ — ota-ona akkaunt yaratish va biriktirish."""
        from apps.accounts.models import User
        student = self.get_object()
        phone    = request.data.get('phone', '').strip()
        password = request.data.get('password', 'erp12345')
        name     = request.data.get('full_name') or student.parent_name or f"{student.user.full_name} (Ota-ona)"
        if not phone:
            return Response({'detail': 'Telefon raqam majburiy.'}, status=400)
        if User.objects.filter(phone=phone).exists():
            user = User.objects.get(phone=phone)
            if user.role != User.Role.PARENT:
                return Response({'detail': 'Bu telefon boshqa rol uchun ro\'yxatdan o\'tgan.'}, status=400)
        else:
            user = User.objects.create_user(phone=phone, password=password,
                                             full_name=name, role=User.Role.PARENT)
        student.parent_user = user
        student.save(update_fields=['parent_user'])
        return Response({'detail': "Ota-ona akkaunt yaratildi va biriktirildi.",
                         'parent_phone': user.phone, 'parent_id': str(user.id)})

    @action(detail=True, methods=['get'], url_path='payments')
    def payments(self, request, pk=None):
        from apps.payments.models import Payment
        from apps.payments.serializers import PaymentSerializer
        pays = Payment.objects.filter(
            student=self.get_object()
        ).select_related('group', 'received_by').order_by('-year', '-month')
        return Response(PaymentSerializer(pays, many=True).data)

    @action(detail=True, methods=['get'], url_path='attendances')
    def attendances(self, request, pk=None):
        from apps.attendance.models import Attendance
        from apps.attendance.serializers import AttendanceSerializer
        atts = Attendance.objects.filter(
            student=self.get_object()
        ).select_related('group').order_by('-date')
        return Response(AttendanceSerializer(atts, many=True).data)


class ParentDashboardView(APIView):
    """GET /api/v1/students/parent/ — farzandlarining ma'lumotlari."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        children = Student.objects.filter(
            parent_user=request.user
        ).select_related('user', 'group__teacher__user')
        result = []
        for s in children:
            from apps.payments.models import Payment
            from apps.attendance.models import Attendance
            from django.db.models import Sum as DSum, Count as DCount, Q as DQ
            debt = Payment.objects.filter(student=s).aggregate(
                d=Coalesce(DSum('debt_amount', output_field=DecimalField(max_digits=12, decimal_places=0)), 0,
                           output_field=DecimalField(max_digits=12, decimal_places=0))
            )['d']
            att = Attendance.objects.filter(student=s).aggregate(
                total=DCount('id'),
                present=DCount('id', filter=DQ(status='present'))
            )
            att_pct = round(att['present']/att['total']*100, 1) if att['total'] else 0
            recent_att = list(
                Attendance.objects.filter(student=s).order_by('-date')
                .values('date', 'status')[:7]
            )
            recent_pay = list(
                Payment.objects.filter(student=s).order_by('-year', '-month')
                .values('month', 'year', 'paid_amount', 'debt_amount', 'status')[:3]
            )
            g = s.group
            result.append({
                'id':         str(s.id),
                'full_name':  s.user.full_name,
                'phone':      s.phone,
                'status':     s.status,
                'group_name': g.name if g else None,
                'teacher_name': g.teacher.user.full_name if g and g.teacher else None,
                'xp_points':  s.xp_points,
                'level':      s.level,
                'attendance_percentage': att_pct,
                'total_debt': float(debt),
                'recent_attendance': recent_att,
                'recent_payments':   recent_pay,
            })
        return Response(result)


class StudentMeView(APIView):
    """GET /api/v1/students/me/ — returns the current student's full profile."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            student = Student.objects.select_related('user', 'group').get(user=request.user)
        except Student.DoesNotExist:
            return Response({'detail': 'Student profil topilmadi.'}, status=404)

        from apps.payments.models import Payment
        from django.db.models import Sum as DSum
        debt = Payment.objects.filter(student=student).aggregate(
            d=Coalesce(DSum('debt_amount', output_field=DecimalField(max_digits=12, decimal_places=0)), 0,
                       output_field=DecimalField(max_digits=12, decimal_places=0))
        )['d']

        g = student.group
        group_data = None
        if g:
            group_data = {
                'id':          str(g.id),
                'name':        g.name,
                'teacher_name': g.teacher.user.full_name if g.teacher else None,
                'start_time':  str(g.start_time) if g.start_time else None,
                'end_time':    str(g.end_time)   if g.end_time   else None,
                'room':        getattr(g, 'room', ''),
                'days_of_week': list(g.days_of_week or []),
            }

        return Response({
            'id':                  str(student.id),
            'full_name':           student.user.full_name,
            'phone':               student.phone,
            'group':               str(g.id) if g else None,
            'group_name':          g.name    if g else None,
            'group_data':          group_data,
            'status':              student.status,
            'joined_date':         str(student.joined_date),
            'birth_date':          str(student.birth_date) if student.birth_date else None,
            'address':             student.address,
            'parent_name':         student.parent_name,
            'parent_phone':        student.parent_phone,
            'xp_points':           student.xp_points,
            'coins':               student.coins,
            'level':               student.level,
            'xp_to_next_level':    student.xp_to_next_level,
            'level_progress_pct':  student.level_progress_pct,
            'attendance_percentage': student.attendance_percentage,
            'total_debt':          float(debt),
        })
