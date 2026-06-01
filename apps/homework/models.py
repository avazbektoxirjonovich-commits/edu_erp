"""
HOMEWORK — Uyga vazifa moduli
==============================
Assignment: o'qituvchi yaratadi, guruhga belgilaydi
Submission: o'quvchi topshiradi, o'qituvchi baholaydi
"""
import uuid
import logging
from django.core.validators import MinValueValidator, FileExtensionValidator
from django.db import models
from django.utils import timezone

ALLOWED_HOMEWORK_EXTENSIONS = [
    'pdf', 'doc', 'docx', 'txt', 'odt',
    'jpg', 'jpeg', 'png', 'gif',
    'ppt', 'pptx', 'xls', 'xlsx', 'csv',
    'zip', 'rar', 'mp4', 'mp3',
]

logger = logging.getLogger('apps.homework')


class Assignment(models.Model):

    class Status(models.TextChoices):
        DRAFT     = 'draft',     'Qoralama'
        ACTIVE    = 'active',    'Faol'
        CLOSED    = 'closed',    'Yopilgan'

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title       = models.CharField(max_length=255, verbose_name='Sarlavha')
    description = models.TextField(verbose_name='Topshiriq matni')
    group       = models.ForeignKey(
                      'groups.Group', on_delete=models.CASCADE,
                      related_name='assignments', verbose_name='Guruh',
                      db_index=True
                  )
    teacher     = models.ForeignKey(
                      'teachers.Teacher', on_delete=models.SET_NULL,
                      null=True, related_name='assignments',
                      verbose_name="O'qituvchi"
                  )
    assigned_date = models.DateField(null=True, blank=True, verbose_name='Berilgan sana')
    lesson_date   = models.DateField(null=True, blank=True, verbose_name='Dars sanasi')
    due_date      = models.DateField(null=True, blank=True, verbose_name='Tugash sanasi', db_index=True)
    max_score     = models.PositiveSmallIntegerField(
                        default=100,
                        validators=[MinValueValidator(1)],
                        verbose_name='Maksimal ball'
                    )
    xp_reward   = models.PositiveSmallIntegerField(default=50,  verbose_name='XP mukofot')
    status      = models.CharField(
                      max_length=10, choices=Status.choices,
                      default=Status.ACTIVE, db_index=True
                  )
    file        = models.FileField(
                      upload_to='homework/assignments/', blank=True, null=True,
                      validators=[FileExtensionValidator(ALLOWED_HOMEWORK_EXTENSIONS)],
                      verbose_name='Fayl (ixtiyoriy)'
                  )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Vazifa'
        verbose_name_plural = 'Vazifalar'
        ordering            = ['-due_date']
        indexes = [
            models.Index(fields=['status', 'group']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.title} | {self.group.name}"

    @property
    def is_overdue(self):
        if not self.due_date:
            return False
        from datetime import date
        return date.today() > self.due_date and self.status == self.Status.ACTIVE

    @property
    def submission_count(self):
        return self.submissions.count()

    @property
    def graded_count(self):
        return self.submissions.filter(status=Submission.Status.GRADED).count()


class Submission(models.Model):

    class Status(models.TextChoices):
        SUBMITTED = 'submitted', 'Topshirildi'
        GRADED    = 'graded',    'Baholandi'
        LATE      = 'late',      'Kech topshirildi'
        MISSING   = 'missing',   'Topshirilmagan'

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment  = models.ForeignKey(
                      Assignment, on_delete=models.CASCADE,
                      related_name='submissions', verbose_name='Vazifa',
                      db_index=True
                  )
    student     = models.ForeignKey(
                      'students.Student', on_delete=models.CASCADE,
                      related_name='submissions', verbose_name="O'quvchi",
                      db_index=True
                  )
    answer      = models.TextField(blank=True, verbose_name='Javob matni')
    file        = models.FileField(
                      upload_to='homework/submissions/', blank=True, null=True,
                      validators=[FileExtensionValidator(ALLOWED_HOMEWORK_EXTENSIONS)],
                      verbose_name='Topshirilgan fayl'
                  )
    score       = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Ball')
    feedback    = models.TextField(blank=True, verbose_name="O'qituvchi izohi")
    status      = models.CharField(
                      max_length=12, choices=Status.choices,
                      default=Status.SUBMITTED, db_index=True
                  )
    submitted_at = models.DateTimeField(auto_now_add=True)
    graded_at    = models.DateTimeField(null=True, blank=True)
    graded_by    = models.ForeignKey(
                       'accounts.User', on_delete=models.SET_NULL,
                       null=True, blank=True, related_name='graded_submissions'
                   )

    class Meta:
        verbose_name        = 'Topshiriq'
        verbose_name_plural = 'Topshiriqlar'
        ordering            = ['-submitted_at']
        unique_together     = ['assignment', 'student']
        indexes = [
            models.Index(fields=['status', 'assignment']),
            models.Index(fields=['student', 'status']),
        ]

    def __str__(self):
        return f"{self.student.full_name} → {self.assignment.title}"

    @property
    def score_percentage(self):
        if self.score is None:
            return None
        if not self.assignment.max_score:
            return 0
        return round(self.score / self.assignment.max_score * 100, 1)

    def grade(self, score, feedback, graded_by):
        self.score      = score
        self.feedback   = feedback
        self.status     = self.Status.GRADED
        self.graded_at  = timezone.now()
        self.graded_by  = graded_by
        self.save(update_fields=['score', 'feedback', 'status', 'graded_at', 'graded_by'])

        # XP mukofot berish — max_score=0 bo'lsa XP berilmaydi
        if self.assignment.max_score > 0:
            xp = self.assignment.xp_reward * score // self.assignment.max_score
            if xp > 0:
                self.student.add_xp(xp, reason=f"Vazifa: {self.assignment.title}")
        logger.info(f"Baholandi: {self.student.full_name} | {self.assignment.title} | {score}/{self.assignment.max_score}")
