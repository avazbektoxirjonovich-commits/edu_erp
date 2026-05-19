"""
GROUPS — Guruh modeli
======================
O'quvchilar va o'qituvchilar guruh orqali bog'lanadi.
Dars jadvali (LessonSchedule) ham shu yerda.
"""
import uuid
from django.db import models


class Group(models.Model):
    """
    Ta'lim guruhi.

    Bog'liqliklar:
        Group.teacher   → Teacher (ForeignKey)
        Group.students  → Student (reverse FK)
        Group.schedules → LessonSchedule (reverse FK)
        Group.attendances → Attendance (reverse FK)
        Group.payments  → Payment (reverse FK)
    """

    class Status(models.TextChoices):
        ACTIVE    = 'active',    'Faol'
        INACTIVE  = 'inactive',  'Nofaol'
        COMPLETED = 'completed', 'Tugallangan'

    class DayOfWeek(models.IntegerChoices):
        MONDAY    = 1, 'Dushanba'
        TUESDAY   = 2, 'Seshanba'
        WEDNESDAY = 3, 'Chorshanba'
        THURSDAY  = 4, 'Payshanba'
        FRIDAY    = 5, 'Juma'
        SATURDAY  = 6, 'Shanba'
        SUNDAY    = 7, 'Yakshanba'

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=100, verbose_name='Guruh nomi')
    subject     = models.CharField(max_length=100, blank=True, verbose_name="Fan / Yo'nalish")
    branch      = models.ForeignKey(
                      'branches.Branch', on_delete=models.SET_NULL,
                      null=True, blank=True, related_name='groups',
                      verbose_name='Filial', db_index=True
                  )
    description = models.TextField(blank=True, verbose_name='Tavsif')
    teacher     = models.ForeignKey(
                      'teachers.Teacher', on_delete=models.SET_NULL,
                      null=True, related_name='groups',
                      verbose_name="O'qituvchi"
                  )
    status      = models.CharField(max_length=15, choices=Status.choices,
                                   default=Status.ACTIVE, verbose_name='Holat')
    max_students = models.PositiveSmallIntegerField(default=20, verbose_name="Max o'quvchi")
    monthly_fee  = models.DecimalField(max_digits=10, decimal_places=0,
                                       default=500000, verbose_name='Oylik to\'lov')
    start_date  = models.DateField(verbose_name='Boshlanish sanasi')
    end_date    = models.DateField(null=True, blank=True, verbose_name='Tugash sanasi')
    start_time  = models.TimeField(verbose_name='Dars boshlanish vaqti')
    end_time    = models.TimeField(verbose_name='Dars tugash vaqti')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Guruh'
        verbose_name_plural = 'Guruhlar'
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.name} | {self.teacher}"

    @property
    def student_count(self):
        # Used as fallback when view doesn't annotate
        return self.students.filter(status='active').count()

    @property
    def is_full(self):
        return self.student_count >= self.max_students

    @property
    def days_of_week(self):
        return list(self.schedules.values_list('day_of_week', flat=True).order_by('day_of_week'))


class LessonSchedule(models.Model):
    """
    Dars jadvali.
    Bir guruh haftaning bir necha kunida dars o'tishi mumkin.
    Masalan: Python A1 guruhi — Dushanba, Chorshanba, Juma
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group      = models.ForeignKey(
                     Group, on_delete=models.CASCADE,
                     related_name='schedules',
                     verbose_name='Guruh'
                 )
    day_of_week = models.IntegerField(choices=Group.DayOfWeek.choices, verbose_name='Hafta kuni')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Dars jadvali'
        verbose_name_plural = 'Dars jadvallari'
        unique_together     = ['group', 'day_of_week']  # Bir kun bir marta

    def __str__(self):
        return f"{self.group.name} | {self.get_day_of_week_display()}"
