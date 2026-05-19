# 🎓 EduERP — Ta'lim Markazi Boshqaruv Tizimi

> Django + PostgreSQL + JWT asosida qurilgan professional ERP tizimi

## 📋 Modullar

| Modul | Tavsif |
|-------|--------|
| **Accounts** | Foydalanuvchilar, rollar (Admin/Teacher/Student), JWT auth |
| **Students** | O'quvchilar CRUD, profil, davomat va to'lov tarixi |
| **Teachers** | O'qituvchilar boshqaruvi |
| **Groups** | Guruhlar, dars jadvali |
| **Attendance** | Davomat belgilash, statistika |
| **Payments** | Oylik to'lov, qarz hisoblash |
| **Dashboard** | Umumiy statistika API |

## 🚀 Tez ishga tushirish

```bash
# 1. Klonlash
git clone ... && cd erp_system

# 2. O'rnatish (bitta buyruq)
bash scripts/setup.sh

# 3. Server
python manage.py runserver
```

## 🌐 URL'lar

| URL | Tavsif |
|-----|--------|
| `/admin/` | Admin panel (Jazzmin) |
| `/api/v1/auth/login/` | Login |
| `/api/v1/students/` | O'quvchilar |
| `/api/v1/groups/` | Guruhlar |
| `/api/v1/attendance/` | Davomat |
| `/api/v1/payments/` | To'lovlar |
| `/api/v1/dashboard/` | Dashboard |

## 🔐 Rollar

| Rol | Huquqlar |
|-----|----------|
| **Admin** | Barcha amallar |
| **Teacher** | O'quvchilar, davomat belgilash |
| **Student** | Faqat o'z ma'lumotlari |

## 📁 Struktura

```
erp_system/
├── config/
│   ├── settings/
│   │   ├── base.py          ← Umumiy sozlamalar
│   │   ├── development.py   ← Local ishlab chiqish
│   │   └── production.py    ← Server sozlamalari
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── accounts/   ← User, JWT auth
│   ├── students/   ← O'quvchilar
│   ├── teachers/   ← O'qituvchilar
│   ├── groups/     ← Guruhlar + jadval
│   ├── attendance/ ← Davomat
│   ├── payments/   ← To'lovlar
│   └── dashboard/  ← Statistika
├── docs/
│   ├── API.md
│   └── DEPLOYMENT.md
├── scripts/
│   ├── setup.sh
│   └── create_sample_data.py
├── requirements.txt
└── .env.example
```

## 🛠️ Tech Stack

- **Backend**: Django 5.0 + DRF 3.15
- **Database**: PostgreSQL + UUID keys
- **Auth**: JWT (SimpleJWT)
- **Admin**: Jazzmin
- **Deploy**: Nginx + Gunicorn
