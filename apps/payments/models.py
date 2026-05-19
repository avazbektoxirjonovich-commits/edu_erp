import uuid
from django.db import models
from django.core.validators import MinValueValidator


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
                      null=True, related_name='payments', verbose_name='Guruh',
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

    def save(self, *args, **kwargs):
        effective_amount = max(0, self.amount - self.discount)
        self.debt_amount = max(0, effective_amount - self.paid_amount)

        if self.paid_amount <= 0:
            self.status = self.Status.UNPAID
        elif self.paid_amount >= effective_amount:
            self.status = self.Status.PAID
            self.debt_amount = 0
        else:
            self.status = self.Status.PARTIAL

        super().save(*args, **kwargs)
