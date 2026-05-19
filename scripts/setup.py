"""
EduERP — To'liq avtomatik sozlash skripti.

Ishlatish:
    python scripts/setup.py
"""
import os, sys, subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANAGE   = os.path.join(BASE_DIR, 'manage.py')
SETTINGS = 'config.settings.development'


def run(cmd, env=None):
    e = {**os.environ, 'DJANGO_SETTINGS_MODULE': SETTINGS}
    if env:
        e.update(env)
    result = subprocess.run(cmd, shell=True, cwd=BASE_DIR, env=e)
    if result.returncode != 0:
        print(f"[!] XATO: {cmd}")
        sys.exit(1)


def main():
    print("=" * 60)
    print("  EduERP — Tizimni sozlash")
    print("=" * 60)

    print("\n[1/5] Paketlarni o'rnatish...")
    run(f"{sys.executable} -m pip install -r requirements.txt -q")

    print("\n[2/5] Migrations tayyorlash...")
    run(f"{sys.executable} {MANAGE} makemigrations --settings={SETTINGS}")

    print("\n[3/5] Migrations amalga oshirish...")
    run(f"{sys.executable} {MANAGE} migrate --settings={SETTINGS}")

    print("\n[4/5] Admin foydalanuvchi yaratish...")
    run(f"{sys.executable} scripts/create_admin.py")

    print("\n[5/5] Statik fayllarni yig'ish...")
    run(f"{sys.executable} {MANAGE} collectstatic --noinput --settings={SETTINGS}")

    print("\n" + "=" * 60)
    print("  MUVAFFAQIYAT! Tizim tayyor.")
    print("=" * 60)
    print("\n  Serverni ishga tushirish uchun:")
    print(f"  python manage.py runserver --settings={SETTINGS}")
    print("\n  Admin kirish:")
    print("  URL  : http://127.0.0.1:8000/admin/")
    print("  Tel  : +998901234567")
    print("  Parol: admin12345")
    print("\n  ERP paneli:")
    print("  URL  : http://127.0.0.1:8000/")
    print()


if __name__ == '__main__':
    main()
