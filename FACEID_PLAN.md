# VLT.erp — Face ID Rejasi

> Yozilgan sana: 2026-06-04
> Muallif: Senior Django + CV Engineer (Avazbek Yoqubov)

---

## 1. Mavjud tizimni o'rganish natijalari

### Loyiha arxitekturasi
| Komponent | Texnologiya |
|-----------|-------------|
| Backend | Django 5.0.6, DRF 3.15.1 |
| Autentifikatsiya | JWT — SimpleJWT 5.3.1 (localStorage'da saqlanadi) |
| Ma'lumotlar bazasi | PostgreSQL (prod) / SQLite (dev/test) |
| Frontend | SPA — Django Template + vanilla JavaScript |
| Token saqlash | `localStorage`: `erp_access`, `erp_refresh`, `erp_user` |

### Login oqimi (mavjud)
1. Foydalanuvchi `/login/` sahifasiga kiradi
2. `POST /api/v1/auth/login/` → `{access, refresh, user}` qaytariladi
3. Tokenlar `localStorage`'ga saqlanadi
4. Rol bo'yicha yo'naltiriladi (teacher/student/parent/admin)

### Foydalanuvchi modeli
- **Birlamchi kalit**: UUID
- **Autentifikatsiya**: telefon raqami + parol
- **Rollar**: `admin`, `teacher`, `student`, `developer`, `parent`
- **Fayil**: `apps/accounts/models.py`

### Profil sahifalari (ro'yxatga olish UI)
| Rol | URL | Fayl | Avatar element |
|-----|-----|------|----------------|
| O'qituvchi | `/teacher/profile/` | `templates/erp/teacher_settings.html` | `.ts-av-wrap` + `.ts-av-edit` (📷 ikonasi) |
| O'quvchi | `/student/settings/` | `templates/erp/student_settings.html` | `.sett-av` |

**MUHIM:** O'qituvchi sahifasida allaqachon kamera ikonasi (`.ts-av-edit`) mavjud — Face ID ro'yxatga olish modali shu tugmaga ulanadi.

### Mavjud dependencies (requirements.txt)
- `Django==5.0.6`, `djangorestframework==3.15.1`
- `Pillow==11.2.1` (rasm ishlash)
- Yuz aniqlash uchun hech narsa yo'q → qo'shish kerak

### Pytest konfiguratsiyasi
- `pytest.ini` → `DJANGO_SETTINGS_MODULE = config.settings.development`
- Development DB: SQLite (`db.sqlite3`)

---

## 2. Arxitektura qo'shimcha to'g'rilovchi masalalar

### "Pending face verification" holati — SPA muammosi
Mavjud tizim to'liq JWT-asosli SPA. Django sessiyasi API uchun ishlatilmaydi.
**Muammo**: `pending_face_verification` holatini qanday saqlash?

**Yechim**: `django.core.signing` orqali qisqa muddatli `face_pending_token`:
```
POST /api/v1/auth/login/
  ↓ Parol to'g'ri + yuz talab etiladi
  ↓ face_pending_token (5 daqiqa, imzolangan) + challenge qaytariladi
  ↓ Client yuz tekshiruvini bajaradi
POST /api/v1/face-auth/verify-login/
  ↓ face_pending_token + kadrlar
  ↓ Server: jonlilik + shaxsiyat tekshiruvi
  ↓ O'tdi → {access, refresh, user} qaytariladi
```

**Afzalliklar**:
- Django sessiyasi kerak emas
- SPA bilan mos
- `face_pending_token` faqat `/verify-login/` endpointi'da qabul qilinadi
- Django `SECRET_KEY` bilan imzolangan → buzib bo'lmaydi

---

## 3. Yangi modul tuzilmasi

```
apps/face_auth/
├── __init__.py
├── apps.py
├── models.py              # FaceProfile, FaceAuthLog
├── admin.py
├── crypto.py              # Fernet AES encrypt/decrypt
├── services/
│   ├── __init__.py
│   ├── embeddings.py      # DeepFace/ArcFace: aniqlash, validatsiya, embedding
│   ├── liveness.py        # Tasodifiy vazifa + MediaPipe tekshiruvi
│   └── verify.py          # Jonlilik + shaxsiyat uyg'unlashtirish
├── api/
│   ├── __init__.py
│   ├── serializers.py
│   ├── urls.py
│   └── views.py           # enroll, verify-login, status, OTP fallback
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_enrollment.py
│   ├── test_liveness.py
│   ├── test_verify.py
│   └── test_lockout_fallback.py
└── migrations/
    ├── __init__.py
    └── 0001_initial.py
```

### O'zgartirilgan fayllar
| Fayl | O'zgarish |
|------|-----------|
| `config/settings/base.py` | Face Auth sozlamalari qo'shiladi |
| `config/urls.py` | `/api/v1/face-auth/` yo'llari qo'shiladi |
| `apps/accounts/views.py` | `LoginView` → face_pending_token oqimi |
| `templates/erp/teacher_settings.html` | Face ID modali + holat ko'rsatkich |
| `templates/erp/student_settings.html` | Face ID modali + holat ko'rsatkich |
| `templates/erp/login.html` | Yuz tekshiruvi UI (kamera + vazifa) |
| `requirements.txt` | `deepface`, `mediapipe`, `opencv-python`, `cryptography` |

---

## 4. Ma'lumotlar modellari

### FaceProfile
```python
FaceProfile:
  - id: UUIDField (PK)
  - user: OneToOneField(User) → related_name='face_profile'
  - encrypted_embedding: TextField (Fernet-shifrlangan JSON float massivi)
  - status: 'enrolled' | 'not_enrolled'
  - enrolled_at: DateTimeField (null)
  - consent_given: BooleanField
  - consent_at: DateTimeField (null)
  - updated_at: DateTimeField (auto)
```

### FaceAuthLog
```python
FaceAuthLog:
  - id: UUIDField (PK)
  - user: ForeignKey(User)
  - timestamp: DateTimeField (auto)
  - liveness_passed: BooleanField (null)
  - identity_matched: BooleanField (null)
  - result: 'OK' | 'DENIED'
  - challenge: CharField (qaysi vazifa ishlatilgan)
  - failure_reason: CharField
  - ip_address: GenericIPAddressField (null)
```

---

## 5. Xavfsizlik arxitekturasi

### Jonlilik tekshiruvi (server-side, MediaPipe Face Mesh)
| Vazifa | Aniqlash usuli |
|--------|----------------|
| `blink` | EAR < 0.25 kamida 1 marta (ko'z jihatiga nisbati) |
| `blink_twice` | EAR 2 marta pasayib ko'tariladi |
| `smile` | Og'iz kengligi / yuz kengligi > 0.48 (5+ kadrda) |
| `turn_left` | Burun uchi x koordinatasi markazdan -0.12 ga og'adi |
| `turn_right` | Burun uchi x koordinatasi markazdan +0.12 ga og'adi |

**Anti-spoofing**: Kadrlar o'rtasida piksel farqi > 0.5 (statik fotodan himoya).

### Shaxsiyat tekshiruvi
- **Model**: DeepFace ArcFace (512-o'lchovli embedding)
- **Taqqoslash**: Kosinus o'xshashligi (numpy)
- **Chegara**: 0.68 (sozlanadi `FACE_COSINE_THRESHOLD`)
- **1:1 taqqoslash**: Faqat kirmoqchi bo'lgan foydalanuvchining embedding'i bilan taqqoslanadi

### Shifrlash
- **Algoritm**: Fernet (AES-128-CBC + HMAC-SHA256)
- **Kalit**: `FACE_ENCRYPTION_KEY` muhit o'zgaruvchisi (base64-encoded)
- **Saqlash**: `FaceProfile.encrypted_embedding` — matn ustun (shifrlangan)

### Zaxira (Fallback)
1. **OTP email**: 3 marta muvaffaqiyatsizlikdan keyin "Zaxira kod" tugmasi paydo bo'ladi
2. **Admin override**: Admin Django admin panelidan yuz profilini o'chirishi mumkin
3. **Hech kim abadiy bloklana olmaydi**: Yuz talab qilinmaydigan rollarda ishlash mumkin

### Cheklov va bloklash
- **Bloklash**: 5 daqiqa ichida 5 ta muvaffaqiyatsiz urinish → 5 daqiqa kutish
- **Mavjud throttling**: `login: 5/min` (settings.py'da) bilan birgalikda ishlaydi

---

## 6. Ro'yxatga olish oqimi (Enrollment)

1. O'qituvchi `/teacher/profile/` → `.ts-av-edit` (📷) tugmasini bosadi
2. Modal ochiladi: rozilik matni ko'rsatiladi + kamera feed
3. Sifat tekshiruvi real vaqtda (1 yuz, to'g'ridan, aniq, yoritilgan)
4. "Saqlash" tugmasi → bir kadr serverga yuboriladi
5. Server: sifat → embedding → Fernet shifrlash → `FaceProfile`'ga saqlash
6. Profil sahifada holat: `Face ID: Yoqilgan` / `Face ID: O'rnatilmagan`

**Holat ko'rsatkichlari (Uzbek)**:
- Ro'yxatda yo'q: "Face ID: O'rnatilmagan"
- Ro'yxatdan o'tilgan: "Face ID: Yoqilgan"

---

## 7. Login tekshiruvi oqimi (2FA)

```
1. Parol to'g'ri → {face_required: true, face_pending_token, challenge}
2. Login sahifada kamera ochiladi
3. Ekranda Uzbek ko'rsatma: "Jilmaying" / "Ko'zingizni yuming" ...
4. Client 15 kadr to'playdi (3 sekund davomida)
5. POST /api/v1/face-auth/verify-login/ ← kadrlar + face_pending_token
6. Server:
   a. face_pending_token imzosini tekshiradi (max 5 daqiqa)
   b. Bloklash tekshiruvi
   c. Jonlilik: MediaPipe → vazifa bajarilganmi?
   d. Shaxsiyat: DeepFace ArcFace → kosinus o'xshashligi
   e. Ikkisi ham o'tdi → {access, refresh, user}
7. Client → localStorage'ga saqlaydi → yo'naltiradi
```

---

## 8. Sozlamalar (settings.py)

```python
FACE_AUTH_ENABLED       = False   # (muhit o'zgaruvchisi, default False)
FACE_ENCRYPTION_KEY     = ''      # (majburiy, Fernet key)
FACE_COSINE_THRESHOLD   = 0.68    # (sozlanadi)
FACE_MAX_ATTEMPTS       = 5       # bloklash uchun
FACE_LOCKOUT_MINUTES    = 5       # bloklash muddati
FACE_REQUIRED_ROLES     = 'admin,developer'  # (vergul bilan ajratilgan)
```

**Rol bo'yicha boshqarish**: `FACE_REQUIRED_ROLES` orqali qaysi rollar Face ID'ni talab qilishini belgilash.

---

## 9. Qo'shimcha kutubxonalar

| Kutubxona | Maqsad | Holat |
|-----------|--------|-------|
| `deepface>=0.0.89` | ArcFace embedding | Asosiy |
| `mediapipe>=0.10` | Yuz to'r nuqtalari (jonlilik) | Asosiy |
| `opencv-python>=4.8` | Rasm ishlash, yuz aniqlash | Asosiy |
| `cryptography>=42` | Fernet shifrlash | Asosiy |
| `numpy>=1.24` | Vektor hisob-kitoblari | Asosiy |

---

## 10. TAKLIFLAR (keyinchalik amalga oshirish uchun)

**TAKLIF:** InsightFace (buffalo_l) — ArcFace'dan ham aniqroq, ONNX bilan ishlaydi. Hozir DeepFace ishlatilmoqda, chunki Windows'da InsightFace o'rnatish murakkab (Visual C++ build tools talab qiladi). Foyda: DeepFace ArcFace bilan bir xil model, lekin to'g'ridan API.

**TAKLIF:** pgvector (PostgreSQL) — 1:N tekshiruvi kerak bo'lganda (masalan, tizimga kirishga urinayotgan yuzni barcha foydalanuvchilar bilan taqqoslash uchun). Hozir 1:1 bo'lgani uchun kerak emas.

**TAKLIF:** Profil rasm va Face ID referenceni ulash — foydalanuvchi xohlasa, profil rasmi Face ID referencesi sifatida ham ishlatilishi mumkin. Default: alohida (xavfsizroq).

**TAKLIF:** WebSocket orqali real-vaqt jonlilik tekshiruvi — hozir kadrlar batch yuboriladi. WS kanali orqali kadr-kadr tekshiruv yanada sezgirlik beradi.

**TAKLIF:** Telegram bildirishnoma — muvaffaqiyatsiz Face ID urinishi haqida adminga Telegram xabari. `apps/notifications/` orqali amalga oshirish mumkin.
