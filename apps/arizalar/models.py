"""
ARIZA — saytdan kelgan "o'quv markazga yozilish" so'rovi.

O'quvchi saytda o'zi haqida to'liq ma'lumot qoldiradi, ariza ERP'dagi
"Arizalar" paneliga tushadi. Admin bog'lanadi va kerak bo'lsa shu arizadan
o'quvchi akkaunti ochadi (status → qabul qilindi).

Ariza — bu o'quvchi EMAS: u faqat so'rov. Akkaunt ochilgandan keyingina
Student yaratiladi va arizaga bog'lanadi.
"""
import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.accounts.models import User


class Application(models.Model):

    class Status(models.TextChoices):
        NEW       = 'new',       'Yangi'
        CONTACTED = 'contacted', "Bog'lanildi"
        ENROLLED  = 'enrolled',  'Qabul qilindi'
        REJECTED  = 'rejected',  'Rad etildi'

    # Holat faqat "yangi"dan boshlanadi; qabul qilingan ariza yopiq hisoblanadi
    OPEN_STATUSES = (Status.NEW, Status.CONTACTED)

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name    = models.CharField(max_length=150, verbose_name='Ism familiya otasining ismi')
    phone        = models.CharField(max_length=20, db_index=True, verbose_name='Telefon')
    address      = models.CharField(max_length=300, verbose_name='Yashash manzili')
    parent_name  = models.CharField(max_length=150, verbose_name="Ota-ona ismi")
    age          = models.PositiveSmallIntegerField(
                       validators=[MinValueValidator(3), MaxValueValidator(99)],
                       verbose_name='Yosh')
    direction    = models.CharField(max_length=100, verbose_name="Yo'nalish")

    status       = models.CharField(max_length=10, choices=Status.choices,
                                    default=Status.NEW, db_index=True, verbose_name='Holat')
    note         = models.TextField(blank=True, verbose_name='Admin izohi')

    # Arizadan ochilgan o'quvchi (ochilgan bo'lsa)
    student      = models.OneToOneField('students.Student', null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name='application',
                                        verbose_name="O'quvchi")
    handled_by   = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='handled_applications',
                                     verbose_name='Kim ishlagan')
    handled_at   = models.DateTimeField(null=True, blank=True, verbose_name='Qachon ishlangan')

    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = 'Ariza'
        verbose_name_plural = 'Arizalar'
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(age__gte=3) & models.Q(age__lte=99),
                                   name='ariza_age_range'),
        ]

    def __str__(self):
        return f'{self.full_name} ({self.phone})'

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES
