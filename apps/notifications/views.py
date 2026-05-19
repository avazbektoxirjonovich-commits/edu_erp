from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import Notification
from .serializers import NotificationSerializer
from apps.accounts.models import User


class NotificationListView(generics.ListAPIView):
    serializer_class   = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')


class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)
        return Response({'detail': 'Barcha bildirishnomalar o\'qildi'})


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return Response({'unread': count})


class SupportMessageView(APIView):
    """POST /api/v1/notifications/support/ — sends a support message to all developers."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = (request.data.get('message') or '').strip()
        if not message:
            return Response({'detail': "Xabar matni bo'sh bo'lishi mumkin emas."}, status=400)

        sender = request.user
        title  = f"Yordam so'rovi: {sender.full_name} ({sender.phone})"

        developers = User.objects.filter(role=User.Role.DEVELOPER, is_active=True)
        if not developers.exists():
            return Response({'detail': 'Dasturchi topilmadi, lekin xabar qabul qilindi.'}, status=200)

        for dev in developers:
            Notification.objects.create(
                recipient  = dev,
                channel    = Notification.Channel.SYSTEM,
                notif_type = Notification.Type.GENERAL,
                title      = title,
                message    = message,
                status     = Notification.Status.SENT,
            )
        return Response({'detail': "Xabar dasturchi(lar)ga yuborildi. Tez orada javob beriladi!"})
