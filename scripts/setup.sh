#!/bin/bash
# ============================================================
#  ERP TIZIMI — Birinchi ishga tushirish skripti
#  Ishlatish: bash scripts/setup.sh
# ============================================================
set -e  # Xato bo'lsa to'xtat

echo "🚀 ERP tizimi o'rnatilmoqda..."

# 1. Virtual environment yaratish
echo "📦 Virtual environment yaratilmoqda..."
python3 -m venv venv
source venv/bin/activate

# 2. Paketlarni o'rnatish
echo "📥 Paketlar o'rnatilmoqda..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# 3. .env fayl
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  .env fayl yaratildi. Iltimos, ma'lumotlarni to'ldiring!"
fi

# 4. Logs papkasi
mkdir -p logs media staticfiles

# 5. Migration
echo "🗄️  Ma'lumotlar bazasi migratsiya..."
python manage.py makemigrations accounts students teachers groups attendance payments
python manage.py migrate

# 6. Superuser
echo ""
echo "👤 Admin foydalanuvchi yaratish:"
python manage.py createsuperuser

# 7. Static fayllar
python manage.py collectstatic --noinput -q

echo ""
echo "✅ O'rnatish tugadi!"
echo "🌐 Serverni ishga tushirish: python manage.py runserver"
echo "🔑 Admin panel: http://localhost:8000/admin/"
