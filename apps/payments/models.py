import calendar
import uuid
from datetime import date

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

DEFAULT_PAYMENT_DUE_DAY = 10  # Payment.group yo'q bo'lsa ishlatiladigan standart muddat


class Payment(models.Model):

    class Status(models.TextChoices):
        PAID    = 'paid',    "To'langan"
        PARTIAL = 'partial', 'Qisman'
        UNPAID  = 'unpaid',  "To'lanmagan"

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student     = models.ForeignKey(
                      'students.Student', on_delete=models.CASCADE,
                      related_name='payments', verbose_name="O'quvchi",
                      db_index=True
                  )
    group       = models.ForeignKey(
                      'groups.Group', on_delete=models.SET_NULL,
                      null=True, blank=True, related_name='payments', verbose_name='Guruh',
                      db_index=True
                  )
    month       = models.PositiveSmallIntegerField(verbose_name='Oy')
    year        = models.PositiveSmallIntegerField(verbose_name='Yil')
    amount      = models.DecimalField(
                      max_digits=10, decimal_places=0,
                      validators=[MinValueValidator(0)],
                      verbose_name="To'lov summasi"
                  )
    paid_amount = models.DecimalField(
                      max_digits=10, decimal_places=0,
                      default=0,
                      validators=[MinValueValidator(0)],
                      verbose_name="To'langan summa"
                  )
    debt_amount = models.DecimalField(
                      max_digits=10, decimal_places=0,
                      default=0, verbose_name="Qarz summasi"
                  )
    discount    = models.DecimalField(
                      max_digits=10, decimal_places=0,
                      default=0, verbose_name='Chegirma'
                  )
    status      = models.CharField(max_length=10, choices=Status.choices,
                                   default=Status.UNPAID, verbose_name='Holat',
                                   db_index=True)
    payment_date = models.DateField(null=True, blank=True, verbose_name="To'lov sanasi")
    note         = models.CharField(max_length=200, blank=True, verbose_name='Izoh')
    received_by  = models.ForeignKey(
                       'accounts.User', on_delete=models.SET_NULL,
                       null=True, blank=True,
                       related_name='received_payments',
                       verbose_name='Qabul qilgan'
                   )
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "To'lov"
        verbose_name_plural = "To'lovlar"
        ordering            = ['-year', '-month']
        unique_together     = ['student', 'group', 'month', 'year']
        indexes = [
            models.Index(fields=['month', 'year', 'status']),
            models.Index(fields=['student', 'year', 'month']),
        ]

    def __str__(self):
        return f"{self.student} | {self.year}/{self.month:02d} | {self.get_status_display()}"

    @staticmethod
    def compute_status(amount, discount, paid_amount):
        effective = max(0, amount - discount)
        debt = max(0, effective - paid_amount)
        if paid_amount <= 0:
            return Payment.Status.UNPAID, debt
        if paid_amount >= effective:
            return Payment.Status.PAID, 0
        return Payment.Status.PARTIAL, debt

    def save(self, *args, **kwargs):
        self.status, self.debt_amount = self.compute_status(
            self.amount, self.discount, self.paid_amount
        )
        super().save(*args, **kwargs)

    @property
    def due_date(self):
        """Shu oy uchun to'lov muddati sanasi — guruhning payment_due_day'iga asoslanadi."""
        day = self.group.payment_due_day if self.group else DEFAULT_PAYMENT_DUE_DAY
        last_day_of_month = calendar.monthrange(self.year, self.month)[1]
        return date(self.year, self.month, min(day, last_day_of_month))

    @property
    def is_overdue(self):
        """PAID bo'lmagan va muddati o'tgan to'lovlar uchun True.
        Bu vaqtga bog'liq — DB'da saqlanmaydi, har doim jonli hisoblanadi."""
        if self.status == self.Status.PAID:
            return False
        return timezone.localdate() > self.due_date

    @property
    def effective_status(self):
        """Frontend uchun 4-holatli status: paid / partial / unpaid / overdue."""
        return 'overdue' if self.is_overdue else self.status
