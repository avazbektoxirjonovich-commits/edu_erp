"""
EduERP — Admin foydalanuvchi yaratish skripti.

Ishlatish:
    python manage.py shell < scripts/create_admin.py
yoki:
    python scripts/create_admin.py
"""
import os, sys, django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.accounts.models import User

ADMIN_PHONE    = '+998901234567'
ADMIN_PASSWORD = 'admin12345'
ADMIN_NAME     = 'Administrator'


def create_admin():
    if User.objects.filter(phone=ADMIN_PHONE).exists():
        user = User.objects.get(phone=ADMIN_PHONE)
        print(f"[!] Admin allaqachon mavjud: {user.phone}")
        return user

    user = User.objects.create_superuser(
        phone=ADMIN_PHONE,
        password=ADMIN_PASSWORD,
        full_name=ADMIN_NAME,
    )
    print(f"[+] Admin yaratildi:")
    print(f"    Telefon : {ADMIN_PHONE}")
    print(f"    Parol   : {ADMIN_PASSWORD}")
    print(f"    Rol     : {user.role}")
    return user


if __name__ == '__main__':
    create_admin()
