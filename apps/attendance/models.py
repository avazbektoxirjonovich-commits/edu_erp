"""
ATTENDANCE — Davomat modeli
============================
Har bir dars uchun alohida yozuv saqlanadi.
Student + Group + Date kombinatsiyasi noyob bo'lishi kerak.
"""
import uuid
from django.db import models


class Attendance(models.Model):
    """
    Davomat yozuvi.

    Bog'liqliklar:
        Attendance.student → Student
        Attendance.group   → Group
    """

    class Status(models.TextChoices):
        PRESENT = 'present', 'Keldi'
        ABSENT  = 'absent',  'Kelmadi'
        LATE    = 'late',    'Kech keldi'
        EXCUSED = 'excused', "Sababli yo'q"

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student    = models.ForeignKey(
                     'students.Student', on_delete=models.CASCADE,
                     related_name='attendances', verbose_name="O'quvchi"
                 )
    group      = models.ForeignKey(
                     'groups.Group', on_delete=models.CASCADE,
                     related_name='attendances', verbose_name='Guruh'
                 )
    date       = models.DateField(verbose_name='Sana')
    status     = models.CharField(max_length=10, choices=Status.choices,
                                  default=Status.PRESENT, verbose_name='Holat')
    note       = models.CharField(max_length=200, blank=True, verbose_name='Izoh')
    marked_by  = models.ForeignKey(
                     'accounts.User', on_delete=models.SET_NULL,
                     null=True, related_name='marked_attendances',
                     verbose_name='Belgilagan'
                 )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Davomat'
        verbose_name_plural = 'Davomatlar'
        ordering            = ['-date']
        unique_together     = ['student', 'group', 'date']  # Bir kunda bir marta

    def __str__(self):
        return f"{self.student} | {self.date} | {self.get_status_display()}"
