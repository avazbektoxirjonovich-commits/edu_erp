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

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient    = models.ForeignKey(
                       'accounts.User', on_delete=models.CASCADE,
                       related_name='notifications', verbose_name='Qabul qiluvchi'
                   )
    channel      = models.CharField(max_length=10, choices=Channel.choices,
                                    default=Channel.SYSTEM, db_index=True)
    notif_type   = models.CharField(max_length=30, choices=Type.choices,
                                    default=Type.GENERAL)
    title        = models.CharField(max_length=200, verbose_name='Sarlavha')
    message      = models.TextField(verbose_name='Xabar')
    status       = models.CharField(max_length=10, choices=Status.choices,
                                    default=Status.PENDING, db_index=True)
    is_read      = models.BooleanField(default=False, db_index=True)
    sent_at      = models.DateTimeField(null=True, blank=True)
    error_msg    = models.CharField(max_length=500, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Bildirishnoma'
        verbose_name_plural = 'Bildirishnomalar'
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['status', 'channel']),
        ]

    def __str__(self):
        return f"{self.get_channel_display()} | {self.recipient} | {self.title[:40]}"
