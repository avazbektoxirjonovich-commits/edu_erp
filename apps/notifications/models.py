import uuid
from django.db import models


class Notification(models.Model):

    class Channel(models.TextChoices):
        SMS      = 'sms',      'SMS'
        TELEGRAM = 'telegram', 'Telegram'
        SYSTEM   = 'system',   'Tizim'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Kutilmoqda'
        SENT    = 'sent',    'Yuborildi'
        FAILED  = 'failed',  'Xato'

    class Type(models.TextChoices):
        PAYMENT_REMINDER = 'payment_reminder', "To'lov eslatmasi"
        ATTENDANCE_ALERT = 'attendance_alert', 'Davomat ogohlantirishsi'
        GENERAL          = 'general',          'Umumiy'
        SUPPORT_MESSAGE  = 'support_message',  'Yordam xabari'
        SUPPORT_REPLY    = 'support_reply',    'Yordam javobi'

    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender    = models.ForeignKey(
                    'accounts.User', null=True, blank=True,
                    on_delete=models.SET_NULL,
                    related_name='sent_notifications', verbose_name='Yuboruvchi'
                )
    recipient = models.ForeignKey(
                    'accounts.User', on_delete=models.CASCADE,
                    related_name='notifications', verbose_name='Qabul qiluvchi'
                )
    parent    = models.ForeignKey(
                    'self', null=True, blank=True,
                    on_delete=models.SET_NULL,
                    related_name='replies', verbose_name='Asl xabar'
                )
    channel     = models.CharField(max_length=10, choices=Channel.choices,
                                   default=Channel.SYSTEM, db_index=True)
    notif_type  = models.CharField(max_length=30, choices=Type.choices,
                                   default=Type.GENERAL)
    title       = models.CharField(max_length=200, verbose_name='Sarlavha')
    message     = models.TextField(verbose_name='Xabar')
    status      = models.CharField(max_length=10, choices=Status.choices,
                                   default=Status.PENDING, db_index=True)
    is_read     = models.BooleanField(default=False, db_index=True)
    sent_at     = models.DateTimeField(null=True, blank=True)
    error_msg   = models.CharField(max_length=500, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Bildirishnoma'
        verbose_name_plural = 'Bildirishnomalar'
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['status', 'channel']),
            models.Index(fields=['notif_type', 'sender']),
        ]

    def __str__(self):
        return f"{self.get_channel_display()} | {self.recipient} | {self.title[:40]}"


class ActivityLog(models.Model):

    class Action(models.TextChoices):
        CREATE = 'create', 'Yaratildi'
        UPDATE = 'update', 'Yangilandi'
        DELETE = 'delete', "O'chirildi"
        LOGIN  = 'login',  'Tizimga kirdi'
        LOGOUT = 'logout', 'Tizimdan chiqdi'

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user        = models.ForeignKey(
                      'accounts.User', null=True, on_delete=models.SET_NULL,
                      related_name='activity_logs', verbose_name='Foydalanuvchi'
                  )
    action      = models.CharField(max_length=10, choices=Action.choices, db_index=True)
    model_name  = models.CharField(max_length=50, verbose_name='Model', db_index=True)
    object_id   = models.CharField(max_length=50, blank=True, verbose_name='Obyekt ID')
    object_repr = models.CharField(max_length=200, verbose_name='Obyekt')
    changes     = models.JSONField(null=True, blank=True, verbose_name="O'zgarishlar")
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Faoliyat jurnali'
        verbose_name_plural = 'Faoliyat jurnali'
        ordering            = ['-created_at']

    def __str__(self):
        user_str = str(self.user) if self.user else 'Nomalum'
        return f"{user_str} | {self.get_action_display()} | {self.model_name}"