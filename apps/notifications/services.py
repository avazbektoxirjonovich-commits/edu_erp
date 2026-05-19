"""
Notification service layer.
Supports: System notifications (DB), Telegram (via bot), SMS (stub ready).
"""
import logging
from django.utils import timezone

logger = logging.getLogger('apps.notifications')


class NotificationService:

    @staticmethod
    def send_system(user, title, message, notif_type='general'):
        from .models import Notification
        notif = Notification.objects.create(
            recipient=user,
            channel=Notification.Channel.SYSTEM,
            notif_type=notif_type,
            title=title,
            message=message,
            status=Notification.Status.SENT,
            sent_at=timezone.now(),
        )
        logger.info(f"System notification sent to {user}: {title}")
        return notif

    @staticmethod
    def send_telegram(chat_id, message):
        from django.conf import settings
        import urllib.request
        import json

        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            logger.warning("TELEGRAM_BOT_TOKEN not configured")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}).encode()
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        try:
            urllib.request.urlopen(req, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    @staticmethod
    def send_sms(phone, message):
        # Stub — integrate with Eskiz.uz, Playmobile, or similar SMS gateway
        logger.info(f"[SMS STUB] To {phone}: {message[:50]}")
        return True

    @classmethod
    def payment_reminder(cls, student, amount, month, year):
        message = (
            f"Hurmatli {student.full_name}!\n"
            f"{year}-yil {month}-oy uchun to'lov: {amount:,.0f} so'm.\n"
            f"Iltimos, o'z vaqtida to'lang."
        )
        cls.send_system(
            student.user,
            title="To'lov eslatmasi",
            message=message,
            notif_type='payment_reminder',
        )
        if student.parent_phone:
            cls.send_sms(student.parent_phone, message)

    @classmethod
    def attendance_alert(cls, student, date, status):
        status_text = {'absent': "kelmadi", 'late': "kech keldi"}.get(status, status)
        message = f"{student.full_name} bugun ({date}) darsga {status_text}."
        cls.send_system(
            student.user,
            title="Davomat ogohlantirishsi",
            message=message,
            notif_type='attendance_alert',
        )
        if student.parent_phone:
            cls.send_sms(student.parent_phone, message)
