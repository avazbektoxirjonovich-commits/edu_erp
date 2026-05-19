import uuid
from django.db import models
from django.core.validators import RegexValidator
from apps.accounts.models import User

phone_validator = RegexValidator(regex=r'^\+998\d{9}$', message="Format: +998901234567")


class Teacher(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.OneToOneField(User, on_delete=models.CASCADE,
                                      related_name='teacher_profile')
    branch     = models.ForeignKey(
                     'branches.Branch', on_delete=models.SET_NULL,
                     null=True, blank=True, related_name='teachers',
                     verbose_name='Filial', db_index=True
                 )
    phone      = models.CharField(max_length=15, validators=[phone_validator], db_index=True)
    subject    = models.CharField(max_length=100, blank=True, verbose_name="Fan / Yo'nalish")
    salary     = models.DecimalField(max_digits=12, decimal_places=0,
                                     default=0, verbose_name='Oylik maosh')
    is_active  = models.BooleanField(default=True, verbose_name='Faol', db_index=True)
    notes      = models.TextField(blank=True)
    photo      = models.ImageField(upload_to='teachers/photos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "O'qituvchi"
        verbose_name_plural = "O'qituvchilar"
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.user.full_name} | {self.subject}"

    @property
    def full_name(self):
        return self.user.full_name

    @property
    def group_count(self):
        return self.groups.filter(status='active').count()
