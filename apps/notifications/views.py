from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .models import Notification, ActivityLog
from .serializers import (
    NotificationSerializer, SupportMessageSerializer,
    SupportReplySerializer, ActivityLogSerializer,
)
from apps.accounts.models import User
from apps.accounts.permissions import IsStaffLevel


def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_activity(user, action, model_name, object_id='', object_repr='', changes=None, request=None):
    ip = _get_client_ip(request) if request else None
    ActivityLog.objects.create(
        user=user,
        action=action,
        model_name=model_name,
        object_id=str(object_id),
        object_repr=object_repr[:200],
        changes=changes,
        ip_address=ip,
    )


# ── Bildirishnomalar ──────────────────────────────────────────────────────────

class NotificationListView(generics.ListAPIView):
    serializer_class   = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user
        ).select_related('sender').order_by('-created_at')


class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)
        return Response({'detail': "Barcha bildirishnomalar o'qildi"})


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return Response({'unread': count})


# ── Yordam chat (ikki tomonlama) ──────────────────────────────────────────────

class SupportMessageView(APIView):
    """
    GET  — chat tarixi (o'zi yuborgan + javoblar)
    POST — xabar yuborish (qatlamli: student/teacher→admin, admin→developer)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        msgs = Notification.objects.filter(
            notif_type__in=[
                Notification.Type.SUPPORT_MESSAGE,
                Notification.Type.SUPPORT_REPLY,
            ]
        ).filter(
            Q(sender=user) | Q(recipient=user)
        ).select_related('sender', 'recipient').order_by('created_at')

        serializer = NotificationSerializer(msgs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = SupportMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        message = serializer.validated_data['message']
        sender  = request.user
        role    = sender.role

        if role in (User.Role.STUDENT, User.Role.TEACHER, User.Role.PARENT):
            recipients = User.objects.filter(role=User.Role.ADMIN, is_active=True)
            if not recipients.exists():
                recipients = User.objects.filter(role=User.Role.DEVELOPER, is_active=True)
            title = f"Yordam: {sender.full_name} ({sender.get_role_display()})"
        elif role == User.Role.ADMIN:
            recipients = User.objects.filter(role=User.Role.DEVELOPER, is_active=True)
            title = f"Admin murojaat: {sender.full_name}"
        else:
            return Response(
                {'detail': "Siz yordam xabari yubora olmaysiz."},
                status=400
            )

        if not recipients.exists():
            return Response({'detail': "Qabul qiluvchi topilmadi."}, status=404)

        created = []
        for rec in recipients:
            notif = Notification.objects.create(
                sender     = sender,
                recipient  = rec,
                channel    = Notification.Channel.SYSTEM,
                notif_type = Notification.Type.SUPPORT_MESSAGE,
                title      = title,
                message    = message,
                status     = Notification.Status.SENT,
            )
            created.append(notif)

        return Response(NotificationSerializer(created[0]).data, status=201)


class SupportReplyView(APIView):
    """POST /api/v1/notifications/support/{id}/reply/ — javob yozish"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            original = Notification.objects.select_related('sender', 'recipient').get(pk=pk)
        except Notification.DoesNotExist:
            return Response({'detail': 'Xabar topilmadi.'}, status=404)

        if original.recipient != request.user and original.sender != request.user:
            return Response({'detail': "Siz bu xabarga javob bera olmaysiz."}, status=403)

        serializer = SupportReplySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        reply_to = original.sender
        if not reply_to:
            return Response({'detail': "Asl yuboruvchi topilmadi."}, status=404)

        reply = Notification.objects.create(
            sender     = request.user,
            recipient  = reply_to,
            parent     = original,
            channel    = Notification.Channel.SYSTEM,
            notif_type = Notification.Type.SUPPORT_REPLY,
            title      = f"Javob: {original.title[:100]}",
            message    = serializer.validated_data['message'],
            status     = Notification.Status.SENT,
        )
        original.is_read = True
        original.save(update_fields=['is_read'])

        return Response(NotificationSerializer(reply).data, status=201)


class SupportInboxView(generics.ListAPIView):
    """GET /api/v1/notifications/support/inbox/ — admin/developer uchun kiruvchi xabarlar"""
    serializer_class   = NotificationSerializer
    permission_classes = [IsStaffLevel]

    def get_queryset(self):
        return Notification.objects.filter(
            recipient  = self.request.user,
            notif_type = Notification.Type.SUPPORT_MESSAGE,
        ).select_related('sender').order_by('-created_at')


# ── To'lov eslatmalari ───────────────────────────────────────────────────────

class SendPaymentRemindersView(APIView):
    """POST /api/v1/notifications/send-reminders/ — qarzdorlarga eslatma yuborish"""
    permission_classes = [IsStaffLevel]

    def post(self, request):
        from apps.payments.models import Payment
        now = timezone.now()
        try:
            month = int(request.data.get('month', now.month))
            year  = int(request.data.get('year',  now.year))
        except (ValueError, TypeError):
            return Response({'detail': "month va year butun son bo'lishi kerak."}, status=400)

        unpaid = (
            Payment.objects
            .filter(month=month, year=year, status__in=['unpaid', 'partial'])
            .select_related('student__user')
            .filter(student__user__is_active=True)
        )

        # 1 ta query: bu oy allaqachon eslatma yuborilgan user IDlar
        already_sent_ids = set(
            Notification.objects.filter(
                notif_type         = Notification.Type.PAYMENT_REMINDER,
                created_at__month  = now.month,
                created_at__year   = now.year,
            ).values_list('recipient_id', flat=True)
        )

        to_create  = []
        sent_count = 0
        skip_count = 0

        for pay in unpaid:
            user = pay.student.user
            if user.pk in already_sent_ids:
                skip_count += 1
                continue
            to_create.append(Notification(
                recipient  = user,
                channel    = Notification.Channel.SYSTEM,
                notif_type = Notification.Type.PAYMENT_REMINDER,
                title      = f"{month}-oy to'lov eslatmasi",
                message    = (
                    f"Hurmatli {user.full_name},\n"
                    f"{year}-yil {month}-oy uchun to'lovingiz amalga oshirilmagan.\n"
                    f"Qarz: {pay.debt_amount:,.0f} so'm.\n"
                    f"Iltimos, to'lovni amalga oshiring."
                ),
                status = Notification.Status.SENT,
            ))
            sent_count += 1

        if to_create:
            Notification.objects.bulk_create(to_create, batch_size=500)

        return Response({
            'sent':    sent_count,
            'skipped': skip_count,
            'month':   month,
            'year':    year,
            'detail':  f"{sent_count} ta eslatma yuborildi, {skip_count} ta allaqachon yuborilgan.",
        })


# ── Faoliyat jurnali ──────────────────────────────────────────────────────────

class ActivityLogListView(generics.ListAPIView):
    """GET /api/v1/notifications/activity/ — so'nggi amallar (faqat admin/developer)"""
    serializer_class   = ActivityLogSerializer
    permission_classes = [IsStaffLevel]
    pagination_class   = None
    filter_backends    = []  # Manual filtering — sliced queryset bilan global backendlar ishlamaydi

    def get_queryset(self):
        qs = ActivityLog.objects.select_related('user').order_by('-created_at')
        model  = self.request.query_params.get('model')
        action = self.request.query_params.get('action')
        if model:
            qs = qs.filter(model_name__iexact=model)
        if action:
            qs = qs.filter(action=action)
        return qs[:200]