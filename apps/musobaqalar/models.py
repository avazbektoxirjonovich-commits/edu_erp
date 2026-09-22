"""
MUSOBAQALAR — oylik matematika musobaqalariga ro'yxatdan o'tish
================================================================
Competition (musobaqa) → Participant (ishtirokchi, public saytdan yoziladi)
→ Result (natija: ball va o'rin).

Holat faqat oldinga yuradi (qarang: Competition.NEXT_STATUS):
  draft → published → registration_closed → finished
"""
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.validators import phone_validator

GRADE_VALIDATORS = [MinValueValidator(1), MaxValueValidator(11)]


class Competition(models.Model):

    class Status(models.TextChoices):
        DRAFT               = 'draft',               'Qoralama'
        PUBLISHED           = 'published',           "E'lon qilingan"
        REGISTRATION_CLOSED = 'registration_closed', "Ro'yxat yopilgan"
        FINISHED            = 'finished',            'Yakunlangan'

    # Ruxsat etilgan yagona keyingi holat
    NEXT_STATUS = {
        Status.DRAFT:               Status.PUBLISHED,
        Status.PUBLISHED:           Status.REGISTRATION_CLOSED,
        Status.REGISTRATION_CLOSED: Status.FINISHED,
    }

    id                    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name                  = models.CharField(max_length=200, verbose_name='Nomi')
    grade_from            = models.PositiveSmallIntegerField(validators=GRADE_VALIDATORS,
                                                             verbose_name='Boshlanish sinfi')
    grade_to              = models.PositiveSmallIntegerField(validators=GRADE_VALIDATORS,
                                                             verbose_name='Tugash sinfi')
    status                = models.CharField(max_length=20, choices=Status.choices,
                                             default=Status.DRAFT, db_index=True, verbose_name='Holati')
    location              = models.TextField(blank=True, verbose_name='Manzil')
    registration_deadline = models.DateTimeField(verbose_name="Ro'yxatdan o'tish muddati")
    competition_date      = models.DateTimeField(null=True, blank=True, verbose_name='Musobaqa sanasi')
    # Maxfiylik: natijalarda to'liq familya ko'rsatilsinmi (yo'q bo'lsa "Ali V.")
    show_full_names       = models.BooleanField(default=False,
                                                verbose_name="Natijalarda to'liq ism-familya")
    created_by            = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True,
                                              related_name='created_competitions',
                                              verbose_name='Yaratgan admin')
    created_at            = models.DateTimeField(auto_now_add=True, verbose_name='Yaratilgan vaqt')
    updated_at            = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Musobaqa'
        verbose_name_plural = 'Musobaqalar'
        ordering            = ['-created_at']
        constraints = [
            models.CheckConstraint(check=models.Q(grade_from__lte=models.F('grade_to')),
                                   name='competition_grade_range_valid'),
            # Public sayt "joriy musobaqa"ni ko'rsatadi — bir vaqtda faqat bittasi e'lon qilingan bo'ladi
            models.UniqueConstraint(fields=['status'], condition=models.Q(status='published'),
                                    name='competition_single_published'),
        ]

    def __str__(self):
        return f"{self.name} ({self.grade_from}-{self.grade_to} sinf)"

    def clean(self):
        if self.grade_from and self.grade_to and self.grade_from > self.grade_to:
            raise ValidationError({'grade_to': "Tugash sinfi boshlanish sinfidan kichik bo'lmasligi kerak."})

    @property
    def is_registration_open(self):
        return self.status == self.Status.PUBLISHED and timezone.now() <= self.registration_deadline

    def accepts_grade(self, grade):
        return self.grade_from <= grade <= self.grade_to


class Participant(models.Model):

    class Status(models.TextChoices):
        NEW       = 'new',       'Yangi'
        CONFIRMED = 'confirmed', 'Tasdiqlandi'

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    competition   = models.ForeignKey(Competition, on_delete=models.PROTECT,
                                      related_name='participants', verbose_name='Musobaqa')
    first_name    = models.CharField(max_length=60, verbose_name='Ism')
    last_name     = models.CharField(max_length=60, verbose_name='Familya')
    phone         = models.CharField(max_length=13, validators=[phone_validator], verbose_name='Telefon')
    address       = models.TextField(verbose_name='Yashash manzili')
    # Public formada so'ralmaydi (ixtiyoriy) — kerak bo'lsa admin keyin to'ldiradi
    grade         = models.PositiveSmallIntegerField(validators=GRADE_VALIDATORS, null=True, blank=True,
                                                     verbose_name='Sinf')
    status        = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW,
                                     db_index=True, verbose_name='Holati')
    confirmed_by  = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='confirmed_participants', verbose_name='Kim tasdiqladi')
    confirmed_at  = models.DateTimeField(null=True, blank=True, verbose_name='Tasdiqlangan vaqt')
    # Spam/bot tahlili uchun (public formadan yozilgan IP)
    ip_address    = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP manzil')
    registered_at = models.DateTimeField(auto_now_add=True, verbose_name="Ro'yxatdan o'tgan vaqt")

    class Meta:
        verbose_name        = 'Ishtirokchi'
        verbose_name_plural = 'Ishtirokchilar'
        ordering            = ['-registered_at']
        constraints = [
            # Bitta bola bitta musobaqaga faqat bir marta yoziladi
            models.UniqueConstraint(fields=['competition', 'phone'], name='participant_unique_phone'),
        ]
        indexes = [models.Index(fields=['competition', 'grade', 'status'])]

    def __str__(self):
        grade = f"{self.grade}-sinf" if self.grade else "sinf ko'rsatilmagan"
        return f"{self.first_name} {self.last_name} | {grade} | {self.competition.name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def clean(self):
        if self.competition_id and self.grade and not self.competition.accepts_grade(self.grade):
            raise ValidationError({'grade': (
                f"Bu musobaqa {self.competition.grade_from}-{self.competition.grade_to} sinflar uchun."
            )})


class Result(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant = models.OneToOneField(Participant, on_delete=models.CASCADE,
                                       related_name='result', verbose_name='Ishtirokchi')
    score       = models.PositiveIntegerField(verbose_name='Ball')
    place       = models.PositiveSmallIntegerField(null=True, blank=True,
                                                   verbose_name="O'rin")
    entered_by  = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True,
                                    related_name='entered_results', verbose_name='Kim kiritdi')
    entered_at  = models.DateTimeField(auto_now=True, verbose_name='Kiritilgan vaqt')

    class Meta:
        verbose_name        = 'Natija'
        verbose_name_plural = 'Natijalar'
        ordering            = ['-score']

    def __str__(self):
        return f"{self.participant} — {self.score} ball"
