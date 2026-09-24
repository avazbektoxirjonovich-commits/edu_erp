"""
Arizalar — ERP ichidagi boshqaruv API (faqat administrator).
Saytdan ariza qabul qilish alohida: public.py.
"""
import secrets

from django.db import IntegrityError, transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsAdmin
from apps.groups.models import Group
from apps.notifications.models import ActivityLog
from apps.notifications.views import log_activity
from apps.students.models import Student

from .models import Application
from .serializers import (
    ApplicationDetailSerializer,
    ApplicationListSerializer,
    ConvertSerializer,
)


def generate_password():
    """Yangi o'quvchi uchun oson aytiladigan parol (6 raqam)."""
    return f'{secrets.randbelow(900000) + 100000}'


class ApplicationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                         mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """
    /api/v1/arizalar/                  — ro'yxat (?status=, ?search=)
    /api/v1/arizalar/<id>/             — to'liq ma'lumot, izohni saqlash (PATCH)
    POST .../<id>/contacted/           — "Bog'lanildi" deb belgilash
    POST .../<id>/reject/              — rad etish
    POST .../<id>/convert/             — PANEL OCHISH: o'quvchi akkaunti yaratish
    GET  .../stats/                    — yangi arizalar soni (yon menyudagi belgi uchun)
    """
    permission_classes = [IsAdmin]
    http_method_names = ['get', 'patch', 'post', 'head', 'options']
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields    = ['full_name', 'phone', 'direction', 'parent_name']
    ordering_fields  = ['created_at', 'full_name', 'age']
    ordering         = ['-created_at']
    queryset = Application.objects.select_related('handled_by', 'student')

    def get_serializer_class(self):
        return ApplicationListSerializer if self.action == 'list' else ApplicationDetailSerializer

    def perform_update(self, serializer):
        application = serializer.save()
        log_activity(self.request.user, ActivityLog.Action.UPDATE, 'Application',
                     application.pk, str(application), request=self.request)

    def _set_status(self, request, new_status):
        application = self.get_object()
        if application.status == Application.Status.ENROLLED:
            return Response({'detail': "Bu ariza bo'yicha panel allaqachon ochilgan."},
                            status=status.HTTP_400_BAD_REQUEST)
        old = application.status
        application.status = new_status
        application.handled_by = request.user
        application.handled_at = timezone.now()
        application.save(update_fields=['status', 'handled_by', 'handled_at'])
        log_activity(request.user, ActivityLog.Action.UPDATE, 'Application',
                     application.pk, str(application),
                     changes={'status': {'old': old, 'new': new_status}}, request=request)
        return Response(ApplicationDetailSerializer(application).data)

    @action(detail=True, methods=['post'])
    def contacted(self, request, pk=None):
        return self._set_status(request, Application.Status.CONTACTED)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        return self._set_status(request, Application.Status.REJECTED)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        return Response({
            'new': Application.objects.filter(status=Application.Status.NEW).count(),
            'open': Application.objects.filter(status__in=Application.OPEN_STATUSES).count(),
        })

    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        """PANEL OCHISH — arizadan o'quvchi akkaunti yaratadi.

        Qoidalar:
          1. Kurs to'lovi (monthly_fee) majburiy — busiz panel ochilmaydi.
          2. Bir ariza — bir marta. Qator qulflanadi, ikki marta bosilsa ikkinchisi rad etiladi.
          3. Telefon raqam band bo'lsa (boshqa foydalanuvchi) — aniq xabar, hech narsa yaratilmaydi.
          4. Hammasi bitta tranzaksiyada: yarim ochilgan akkaunt qolmaydi.
          5. Arizadagi ma'lumot yo'qolmaydi: manzil, ota-ona, yosh va yo'nalish o'quvchiga ko'chadi.
        """
        serializer = ConvertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        group = None
        if data.get('group'):
            group = Group.objects.filter(pk=data['group']).first()
            if not group:
                return Response({'group': ['Bunday guruh topilmadi.']},
                                status=status.HTTP_400_BAD_REQUEST)

        password = (data.get('password') or '').strip() or generate_password()

        try:
            with transaction.atomic():
                # Qulflash: ikki admin bir vaqtda bossa ham bitta akkaunt ochiladi
                application = Application.objects.select_for_update().get(pk=self.get_object().pk)

                if application.student_id or application.status == Application.Status.ENROLLED:
                    return Response({'detail': "Bu ariza bo'yicha panel allaqachon ochilgan."},
                                    status=status.HTTP_400_BAD_REQUEST)
                if application.status == Application.Status.REJECTED:
                    return Response({'detail': "Rad etilgan ariza bo'yicha panel ochilmaydi."},
                                    status=status.HTTP_400_BAD_REQUEST)

                existing = User.objects.filter(phone=application.phone).first()
                if existing:
                    return Response({'detail': (
                        f"Bu telefon raqam band: {existing.full_name} "
                        f"({existing.get_role_display()}). Avval uni tekshiring.")},
                        status=status.HTTP_400_BAD_REQUEST)

                user = User.objects.create_user(
                    phone=application.phone, password=password,
                    full_name=application.full_name, role=User.Role.STUDENT,
                )
                student = Student.objects.create(
                    user=user, phone=application.phone, group=group,
                    monthly_fee=data['monthly_fee'], discount=data.get('discount') or 0,
                    address=application.address, parent_name=application.parent_name,
                    notes=(f"Saytdan ariza orqali qabul qilindi.\n"
                           f"Yosh: {application.age}\nYo'nalish: {application.direction}"),
                )
                application.student = student
                application.status = Application.Status.ENROLLED
                application.handled_by = request.user
                application.handled_at = timezone.now()
                application.save(update_fields=['student', 'status', 'handled_by', 'handled_at'])
        except IntegrityError:
            return Response({'detail': "Akkaunt ochilmadi — ma'lumotlarni tekshirib qayta urinib ko'ring."},
                            status=status.HTTP_400_BAD_REQUEST)

        log_activity(request.user, ActivityLog.Action.CREATE, 'Student',
                     student.pk, str(student), request=request)
        log_activity(request.user, ActivityLog.Action.UPDATE, 'Application',
                     application.pk, str(application),
                     changes={'status': {'old': Application.Status.NEW, 'new': Application.Status.ENROLLED}},
                     request=request)

        return Response({
            'student_id':  str(student.pk),
            'full_name':   student.full_name,
            'phone':       student.phone,
            'parol':       password,
            'monthly_fee': str(student.monthly_fee),
            'discount':    str(student.discount),
            'group':       group.name if group else None,
            'xabar':       "Panel ochildi. Kirish ma'lumotlarini o'quvchiga ayting.",
        }, status=status.HTTP_201_CREATED)
