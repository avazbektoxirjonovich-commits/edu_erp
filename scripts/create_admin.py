"""
EduERP — Admin foydalanuvchi yaratish skripti.

Ishlatish:
    python scripts/create_admin.py

Muhit o'zgaruvchilari (ixtiyoriy):
    ADMIN_PHONE    - telefon raqam (standart: +998901234567)
    ADMIN_PASSWORD - parol (standart: terminal orqali so'raladi)
"""
import os, sys, django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()

from apps.accounts.models import User

ADMIN_PHONE = os.environ.get('ADMIN_PHONE', '+998901234567')
ADMIN_NAME  = os.environ.get('ADMIN_NAME', 'Administrator')


def create_admin():
    if User.objects.filter(phone=ADMIN_PHONE).exists():
        print(f"[!] Admin allaqachon mavjud: {ADMIN_PHONE}")
        return

    import getpass
    password = getpass.getpass("Admin paroli: ")
    if len(password) < 4:
        print("[!] Parol kamida 4 ta belgi bo'lishi kerak.")
        return

    user = User.objects.create_superuser(
        phone=ADMIN_PHONE,
        password=password,
        full_name=ADMIN_NAME,
    )
    print(f"[+] Admin yaratildi: {user.phone} | Rol: {user.role}")


if __name__ == '__main__':
    create_admin()