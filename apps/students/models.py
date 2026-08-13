import logging
import uuid
from functools import cached_property

from django.db import models

from apps.accounts.models import User
from apps.common.utils import calculate_attendance_pct
from apps.common.validators import phone_validator

logger = logging.getLogger('apps.students')


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

    def apply_kumush_and_xp(self, *, xp_delta=0, coins_delta=0, reason='', created_by=None,
                             source_type='', source_id=''):
        """
        THE single atomic primitive for every KUMUSH (and, optionally, XP)
        mutation in the system. Locks this Student row, applies both deltas
        in one atomic update, and — when coins_delta != 0 — writes exactly
        one KumushTransaction row carrying balance_before/balance_after/
        created_by/source_type/source_id. This is what makes every KUMUSH
        movement auditable: nothing calls this without a ledger row being
        written alongside the balance change, in the same transaction.

        Refuses (returns None, no mutation at all) if coins_delta is
        negative and would take the balance below zero — the same
        conditional-safety guarantee spend_coins() already provided,
        now generalized and lock-based instead of F()-conditional, since
        this path always takes an explicit row lock anyway.

        source_type/source_id together form the idempotency key callers use
        to detect "have I already awarded this exact event" (e.g.
        source_type='attendance', source_id=str(attendance.pk)) — this
        function itself does not enforce uniqueness; callers that need
        exactly-once semantics must check before calling (see
        apps.attendance.services / Submission.grade / zukko views for the
        established pattern).

        Returns the created KumushTransaction, or None if coins_delta == 0
        (pure XP-only change) or if a negative coins_delta was refused.
        """
        from django.db import transaction as db_transaction

        from apps.store.models import KumushTransaction

        with db_transaction.atomic():
            locked = Student.objects.select_for_update().get(pk=self.pk)
            balance_before = locked.coins

            if coins_delta < 0 and balance_before + coins_delta < 0:
                logger.warning(
                    f"Kumush yetarli emas: {self.full_name} ({reason}) — "
                    f"so'ralgan {coins_delta}, mavjud {balance_before}"
                )
                return None

            new_coins = balance_before + coins_delta
            new_xp = locked.xp_points + xp_delta
            new_level = max(1, new_xp // 500 + 1)

            Student.objects.filter(pk=self.pk).update(
                coins=new_coins, xp_points=new_xp, level=new_level,
            )
            self.coins, self.xp_points, self.level = new_coins, new_xp, new_level

            txn = None
            if coins_delta != 0:
                txn = KumushTransaction.objects.create(
                    student=self,
                    amount=coins_delta,
                    type=KumushTransaction.Type.EARN if coins_delta > 0 else KumushTransaction.Type.SPEND,
                    reason=reason,
                    created_by=created_by,
                    balance_before=balance_before,
                    balance_after=new_coins,
                    source_type=source_type,
                    source_id=str(source_id) if source_id else '',
                )
            logger.info(
                f"Kumush {coins_delta:+d} / XP {xp_delta:+d} → {self.full_name} ({reason})"
            )
            return txn

    def add_xp(self, amount, reason='', created_by=None, source_type='', source_id=''):
        """Increase both XP and KUMUSH by `amount` (1:1 coupled — the
        existing/original reward shape, used by ZUKKO and any other simple
        xp==coins reward path). Now ledger-backed via
        apply_kumush_and_xp(): every call writes a KumushTransaction.
        Returns the created KumushTransaction (or None — same contract as
        apply_kumush_and_xp)."""
        return self.apply_kumush_and_xp(
            xp_delta=amount, coins_delta=amount, reason=reason,
            created_by=created_by, source_type=source_type, source_id=source_id,
        )

    def add_xp_only(self, amount):
        """Bump xp_points (and recompute level) WITHOUT touching coins or
        the KUMUSH ledger. Used where XP and KUMUSH must be awarded on
        independent formulas (homework: XP uses assignment.xp_reward,
        KUMUSH uses the score-percentage rule — see Submission.grade()).
        This preserves homework's existing XP behavior unchanged while its
        KUMUSH behavior is upgraded to delta-based/ledger-backed."""
        from django.db.models import F
        Student.objects.filter(pk=self.pk).update(xp_points=F('xp_points') + amount)
        self.refresh_from_db(fields=['xp_points'])
        new_level = max(1, self.xp_points // 500 + 1)
        Student.objects.filter(pk=self.pk).update(level=new_level)
        self.level = new_level
        logger.info(f"XP +{amount} (kumushsiz) → {self.full_name}")

    def spend_coins(self, amount, reason=''):
        """
        Kumushni xavfsiz kamaytiradi: shart bilan UPDATE (coins >= amount)
        bitta atomik SQL so'rovda bajariladi, shu bois parallel so'rovlarda
        ham balans manfiyga tushmaydi va ikki marta sarflanmaydi.
        Yetarli mablag' bo'lmasa False qaytaradi, hech narsa o'zgarmaydi.
        """
        updated = Student.objects.filter(pk=self.pk, coins__gte=amount).update(
            coins=models.F('coins') - amount,
        )
        if not updated:
            return False
        self.refresh_from_db(fields=['coins'])
        logger.info(f"Kumush -{amount} → {self.full_name} ({reason})")
        return True

    @property
    def xp_to_next_level(self):
        return 500 - (self.xp_points % 500)

    @property
    def level_progress_pct(self):
        return min(100, (self.xp_points % 500) * 100 // 500)

    @cached_property
    def attendance_percentage(self):
        from django.db.models import Count, Q

        from apps.attendance.models import Attendance
        result = Attendance.objects.filter(student=self).aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present'))
        )
        return calculate_attendance_pct(result['present'], result['total'])

    @cached_property
    def total_debt(self):
        from django.db.models import Sum

        from apps.payments.models import Payment
        result = Payment.objects.filter(student=self).aggregate(debt=Sum('debt_amount'))
        return result['debt'] or 0
