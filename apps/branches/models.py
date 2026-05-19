import uuid
from django.db import models
from django.core.validators import RegexValidator

phone_validator = RegexValidator(regex=r'^\+998\d{9}$', message="Format: +998901234567")


class Branch(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name       = models.CharField(max_length=150, unique=True, verbose_name='Filial nomi')
    address    = models.CharField(max_length=255, blank=True, verbose_name='Manzil')
    phone      = models.CharField(max_length=15, blank=True, validators=[phone_validator],
                                  verbose_name='Telefon')
    is_active  = models.BooleanField(default=True, verbose_name='Faol', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Filial'
        verbose_name_plural = 'Filiallar'
        ordering            = ['name']

    def __str__(self):
        return self.name

    @property
    def active_groups_count(self):
        return self.groups.filter(status='active').count()

    @property
    def active_students_count(self):
        from apps.students.models import Student
        return Student.objects.filter(group__branch=self, status='active').count()