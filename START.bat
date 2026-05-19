@echo off
chcp 65001 >nul
echo.
echo  ==========================================
echo    EduERP - Talim Markazi ERP Tizimi
echo  ==========================================
echo.

set SETTINGS=config.settings.windows

echo  [1/4] Kutubxonalar tekshirilmoqda...
pip install -r requirements.txt --quiet
echo  OK!
echo.

echo  [2/4] Migrations ishga tushmoqda...
python manage.py migrate --settings=%SETTINGS%
echo  OK!
echo.

echo  [3/4] Admin yaratilmoqda...
python manage.py shell --settings=%SETTINGS% -c "from apps.accounts.models import User; User.objects.filter(phone='+998901234567').exists() or User.objects.create_superuser(phone='+998901234567', password='admin123', full_name='Administrator')"
echo  OK!
echo.

echo  [4/4] Server ishga tushmoqda...
echo.
echo  ==========================================
echo   Brauzerda oching:
echo   http://127.0.0.1:8000/
echo.
echo   Login : +998901234567
echo   Parol : admin123
echo  ==========================================
echo.
python manage.py runserver --settings=%SETTINGS%