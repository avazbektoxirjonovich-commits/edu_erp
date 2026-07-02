"""
FACE AUTH — Models
FaceProfile: encrypted reference embedding per user.
FaceAuthLog: audit log of every auth attempt.
"""
import uuid
from django.db import models
from django.conf import settings


class FaceProfile(models.Model):
    class Status(models.TextChoices):
        ENROLLED     = 'enrolled',     "Ro'yxatdan o'tilgan"
        NOT_ENROLLED = 'not_enrolled', "Ro'yxatdan o'tilmagan"

    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user                = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='face_profile',
        verbose_name='Foydalanuvchi',
    )
    encrypted_embedding = models.TextField(
        null=True, blank=True,
        verbose_name='Shifrlangan embedding',
    )
    status              = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.NOT_ENROLLED,
        verbose_name='Holat',
    )
    enrolled_at         = models.DateTimeField(null=True, blank=True, verbose_name="Ro'yxatga olingan sana")
    consent_given       = models.BooleanField(default=False, verbose_name='Rozilik berilgan')
    consent_at          = models.DateTimeField(null=True, blank=True, verbose_name='Rozilik sanasi')
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Yuz profili'
        verbose_name_plural = 'Yuz profillari'

    def __str__(self) -> str:
        return f"{self.user} — {self.get_status_display()}"

    @property
    def is_enrolled(self) -> bool:
        return self.status == self.Status.ENROLLED and bool(self.encrypted_embedding)


class UsedToken(models.Model):
    """DB-backed single-use token registry (used when cache is in-memory only)."""
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Ishlatilgan token'
        verbose_name_plural = 'Ishlatilgan tokenlar'


class FaceAuthLog(models.Model):
    class Result(models.TextChoices):
        OK     = 'OK',     'Muvaffaqiyatli'
        DENIED = 'DENIED', 'Rad etildi'

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user             = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='face_auth_logs',
        verbose_name='Foydalanuvchi',
    )
    timestamp        = models.DateTimeField(auto_now_add=True, verbose_name='Vaqt')
    liveness_passed  = models.BooleanField(null=True, verbose_name='Jonlilik')
    identity_matched = models.BooleanField(null=True, verbose_name='Shaxsiyat')
    result           = models.CharField(max_length=10, choices=Result.choices, verbose_name='Natija')
    challenge        = models.CharField(max_length=50, default='', verbose_name='Vazifa')
    failure_reason   = models.CharField(max_length=250, default='', verbose_name='Sabab')
    ip_address       = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP manzil')

    class Meta:
        verbose_name        = 'Yuz autentifikatsiya jurnali'
        verbose_name_plural = 'Yuz autentifikatsiya jurnallari'
        ordering            = ['-timestamp']

    def __str__(self) -> str:
        return f"{self.user} — {self.result} — {self.timestamp:%Y-%m-%d %H:%M}"
