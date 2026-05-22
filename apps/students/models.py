import uuid
import logging
from django.db import models
from django.core.validators import RegexValidator
from apps.accounts.models import User

logger = logging.getLogger('apps.students')
phone_validator = RegexValidator(regex=r'^\+998\d{9}$', message="Format: +998901234567")


class Student(models.Model):

    class Status(models.TextChoices):
        ACTIVE   = 'active',   'Faol'
        INACTIVE = 'inactive', 'Nofaol'
        FROZEN   = 'frozen',   'Toxtatilgan'

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user         = models.OneToOneField(
                       User, on_delete=models.CASCADE,
                       related_name='student_profile',
                       verbose_name='Foydalanuvchi'
                   )
    group        = models.ForeignKey(
                       'groups.Group', on_delete=models.SET_NULL,
                       null=True, blank=True,
                       related_name='students',
                       verbose_name='Guruh',
                       db_index=True
                   )
    phone        = models.CharField(max_length=15, validators=[phone_validator], db_index=True)
    parent_phone = models.CharField(max_length=15, validators=[phone_validator], blank=True)
    parent_name  = models.CharField(max_length=150, blank=True, verbose_name="Ota-ona ismi")
    address      = models.CharField(max_length=200, blank=True)
    birth_date   = models.DateField(null=True, blank=True)
    status       = models.CharField(
                       max_length=10,
                       choices=Status.choices,
                       default=Status.ACTIVE,
                       db_index=True
                   )
    joined_date  = models.DateField(auto_now_add=True)
    notes        = models.TextField(blank=True)
    photo        = models.ImageField(upload_to='students/photos/', blank=True, null=True)
    parent_user  = models.ForeignKey(
                       User, on_delete=models.SET_NULL,
                       null=True, blank=True,
                       related_name='children',
                       verbose_name='Ota-ona akkaunt'
                   )

    # ── Gamification ──────────────────────────────────────────
    xp_points    = models.PositiveIntegerField(default=0, verbose_name='XP Ball')
    coins        = models.PositiveIntegerField(default=0, verbose_name='Kumushlar')
    level        = models.PositiveSmallIntegerField(default=1, verbose_name='Daraja')

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "O'quvchi"
        verbose_name_plural = "O'quvchilar"
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'group']),
            models.Index(fields=['created_at']),
            models.Index(fields=['-xp_points']),
        ]

    def __str__(self):
        group_name = self.group.name if self.group else "Guruhsiz"
        return f"{self.user.full_name} | {group_name}"

    @property
    def full_name(self):
        return self.user.full_name

    def add_xp(self, amount, reason=''):
        self.xp_points += amount
        self.coins     += amount
        # Level: every 500 XP = 1 level
        self.level = max(1, self.xp_points // 500 + 1)
        self.save(update_fields=['xp_points', 'coins', 'level'])
        logger.info(f"XP +{amount} → {self.full_name} ({reason})")

    @property
    def xp_to_next_level(self):
        return 500 - (self.xp_points % 500)

    @property
    def level_progress_pct(self):
        return min(100, (self.xp_points % 500) * 100 // 500)

    @property
    def attendance_percentage(self):
        from apps.attendance.models import Attendance
        from django.db.models import Count, Q
        result = Attendance.objects.filter(student=self).aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present'))
        )
        if not result['total']:
            return 0
        return round(result['present'] / result['total'] * 100, 1)

    @property
    def total_debt(self):
        from django.db.models import Sum
        from apps.payments.models import Payment
        result = Payment.objects.filter(student=self).aggregate(debt=Sum('debt_amount'))
        return result['debt'] or 0
