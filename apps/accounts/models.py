"""
ACCOUNTS — Foydalanuvchi modeli
=================================
Barcha rollar (Admin, Teacher, Student) shu model orqali boshqariladi.
"""
import uuid
import logging
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from apps.common.validators import phone_validator

logger = logging.getLogger('apps.accounts')


class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError('Telefon raqami kiritilishi shart')
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        logger.info(f"Yangi foydalanuvchi: {phone} | Rol: {extra_fields.get('role','student')}")
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.ADMIN)
        return self.create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN     = 'admin',     'Administrator'
        TEACHER   = 'teacher',   "O'qituvchi"
        STUDENT   = 'student',   "O'quvchi"
        DEVELOPER = 'developer', 'Dasturchi'
        PARENT    = 'parent',    'Ota-ona'

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone      = models.CharField(max_length=15, unique=True, validators=[phone_validator],
                                  verbose_name='Telefon raqam')
    full_name  = models.CharField(max_length=150, verbose_name="To'liq ism")
    role       = models.CharField(max_length=10, choices=Role.choices,
                                  default=Role.STUDENT, verbose_name='Rol')
    is_active  = models.BooleanField(default=True)
    is_staff   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD  = 'phone'
    REQUIRED_FIELDS = ['full_name']
    objects = UserManager()

    class Meta:
        verbose_name        = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"

    @property
    def is_admin(self):     return self.role == self.Role.ADMIN
    @property
    def is_teacher(self):   return self.role == self.Role.TEACHER
    @property
    def is_student(self):   return self.role == self.Role.STUDENT
    @property
    def is_developer(self): return self.role == self.Role.DEVELOPER
    @property
    def is_parent(self):    return self.role == self.Role.PARENT
    @property
    def is_staff_level(self):
        """Admin yoki Developer — boshqaruv huquqi"""
        return self.role in (self.Role.ADMIN, self.Role.DEVELOPER)
