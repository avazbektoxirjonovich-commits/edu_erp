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
    answer       = models.TextField(blank=True, verbose_name='Javob matni')
    file         = models.FileField(
                       upload_to='homework/submissions/', blank=True, null=True,
                       validators=[FileExtensionValidator(ALLOWED_HOMEWORK_EXTENSIONS)],
                       verbose_name='Topshirilgan fayl'
                   )
    # Fayl binary — Render ephemeral storage muammosi hal qilingan
    file_name    = models.CharField(max_length=255, blank=True, verbose_name='Fayl nomi')
    file_content = models.BinaryField(null=True, blank=True, editable=False, verbose_name='Fayl (binary)')
    score       = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Ball')
    feedback    = models.TextField(blank=True, verbose_name="O'qituvchi izohi")
    # Ushbu topshiriq uchun HOZIRGACHA berilgan jami KUMUSH — qayta baholashda
    # faqat farq (delta) beriladi, to'liq miqdor emas (duplicate reward'ning
    # oldini olish uchun). Eski (migratsiyadan oldingi) yozuvlar uchun 0 dan
    # boshlanadi — tarixiy ma'lumot o'ylab topilmaydi (agar ular keyinchalik
    # qayta baholansa, bu holat "Remaining issues"da hujjatlashtirilgan).
    kumush_awarded = models.PositiveSmallIntegerField(default=0, verbose_name="Berilgan Kumush")
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

        # XP mukofot — eski, o'zgarmagan formula (assignment.xp_reward
        # asosida). KUMUSH'dan ATAYLAB AJRATILGAN (add_xp_only): XP va
        # KUMUSH endi bir xil miqdor emas, shuning uchun bittasi
        # ikkinchisiga qo'shilib ketmasligi kerak. max_score=0 bo'lsa
        # hech narsa berilmaydi.
        if self.assignment.max_score > 0:
            xp = self.assignment.xp_reward * score // self.assignment.max_score
            if xp > 0:
                self.student.add_xp_only(xp)

            # KUMUSH — YANGI qoida: mukofot = ball foizi (butun sonli
            # arifmetika, float ishlatilmaydi). Qayta baholashda faqat
            # FARQ (delta) beriladi — shu bois bir xil ball bilan qayta
            # yuborish hech qanday qo'shimcha KUMUSH bermaydi, ball
            # oshirilsa faqat farqi, pasaytirilsa ortig'i qaytarib olinadi
            # (balans manfiyga tushishi mumkin bo'lgan holatda
            # apply_kumush_and_xp o'zi xavfsiz rad etadi).
            new_kumush = score * 100 // self.assignment.max_score
            delta = new_kumush - self.kumush_awarded
            if delta != 0:
                reason = f"Vazifa: {self.assignment.title} ({score}/{self.assignment.max_score})"
                txn = self.student.apply_kumush_and_xp(
                    coins_delta=delta, reason=reason, created_by=graded_by,
                    source_type='homework', source_id=str(self.pk),
                )
                if txn is not None:
                    # Delta fully applied — kumush_awarded now equals the
                    # full target amount for the current score.
                    self.kumush_awarded = new_kumush
                    Submission.objects.filter(pk=self.pk).update(kumush_awarded=new_kumush)
                    from apps.notifications.models import ActivityLog
                    from apps.notifications.views import log_activity
                    log_activity(
                        graded_by, ActivityLog.Action.UPDATE, 'Submission', self.pk, str(self),
                        changes={'kumush_delta': delta, 'kumush_awarded': new_kumush,
                                 'balance_before': txn.balance_before, 'balance_after': txn.balance_after},
                    )
                # else: refused (a downward correction whose balance the
                # student no longer has) — kumush_awarded is deliberately
                # left unchanged, since the reduction did not actually
                # happen; apply_kumush_and_xp already logs a warning.
        logger.info(f"Baholandi: {self.student.full_name} | {self.assignment.title} | {score}/{self.assignment.max_score}")
