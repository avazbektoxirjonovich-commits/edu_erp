# EduERP — API Hujjatlar

## Asosiy ma'lumot
- **Base URL**: `http://localhost:8000/api/v1/`
- **Auth**: JWT Bearer token
- **Format**: JSON

---

## 1. Autentifikatsiya

### Login
```
POST /api/v1/auth/login/
Body: { "phone": "+998901234567", "password": "secret" }
Javob: { "access": "...", "refresh": "...", "user": {...} }
```

### Token yangilash
```
POST /api/v1/token/refresh/
Body: { "refresh": "..." }
Javob: { "access": "..." }
```

### Chiqish
```
POST /api/v1/auth/logout/
Headers: Authorization: Bearer <access_token>
Body: { "refresh": "..." }
```

### Mening profilim
```
GET /api/v1/auth/me/
PUT /api/v1/auth/me/
```

---

## 2. O'quvchilar

| Method | URL | Tavsif |
|--------|-----|--------|
| GET    | `/api/v1/students/` | Ro'yxat (filter: status, group) |
| POST   | `/api/v1/students/` | Yangi qo'shish |
| GET    | `/api/v1/students/{id}/` | Bitta o'quvchi |
| PUT    | `/api/v1/students/{id}/` | Yangilash |
| DELETE | `/api/v1/students/{id}/` | O'chirish (nofaol) |
| GET    | `/api/v1/students/{id}/payments/` | To'lovlar tarixi |
| GET    | `/api/v1/students/{id}/attendances/` | Davomat tarixi |

**Filter parametrlar**: `?status=active&group=uuid&search=Asilbek`

---

## 3. Guruhlar

| Method | URL | Tavsif |
|--------|-----|--------|
| GET    | `/api/v1/groups/` | Barcha guruhlar |
| POST   | `/api/v1/groups/` | Yangi guruh |
| GET    | `/api/v1/groups/{id}/` | Bitta guruh |
| PUT    | `/api/v1/groups/{id}/` | Yangilash |

---

## 4. Davomat

| Method | URL | Tavsif |
|--------|-----|--------|
| GET    | `/api/v1/attendance/` | Davomat ro'yxati |
| POST   | `/api/v1/attendance/` | Yozuv qo'shish |
| POST   | `/api/v1/attendance/bulk/` | Guruh davomati (batch) |
| PUT    | `/api/v1/attendance/{id}/` | Yangilash |

**Bulk Body**:
```json
{
  "group": "uuid",
  "date": "2025-05-14",
  "records": [
    {"student": "uuid", "status": "present"},
    {"student": "uuid", "status": "absent"}
  ]
}
```

---

## 5. To'lovlar

| Method | URL | Tavsif |
|--------|-----|--------|
| GET    | `/api/v1/payments/` | To'lovlar ro'yxati |
| POST   | `/api/v1/payments/` | Yangi to'lov |
| GET    | `/api/v1/payments/unpaid/` | Qarzdorlar |
| GET    | `/api/v1/payments/summary/` | Oylik xulosa |
| PUT    | `/api/v1/payments/{id}/` | To'lovni yangilash |

**Filter**: `?month=5&year=2025&status=unpaid&group=uuid`

---

## 6. Dashboard

```
GET /api/v1/dashboard/
```
Javob:
```json
{
  "students": { "total": 102, "active": 98, "new": 8 },
  "groups": { "total": 8, "active": 6 },
  "payments": { "income": 48200000, "debt": 8400000, "unpaid_count": 12 },
  "attendance": { "percentage": 87.5 },
  "monthly_income": [...],
  "top_groups": [...],
  "unpaid_students": [...]
}
```

---

## Holat kodlari

| Kod | Ma'no |
|-----|-------|
| 200 | OK |
| 201 | Yaratildi |
| 400 | Xato so'rov |
| 401 | Autentifikatsiya kerak |
| 403 | Ruxsat yo'q |
| 404 | Topilmadi |
