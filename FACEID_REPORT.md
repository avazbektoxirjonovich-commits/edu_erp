# VLT.erp — Face ID Hisoboti

> Tugatilgan sana: 2026-06-04
> Test natijasi: **47 / 47 — barcha testlar yashil ✓**

---

## Bajarilgan ishlar

### Yangi yaratilgan fayllar

| Fayl | Vazifa |
|------|--------|
| `apps/face_auth/__init__.py` | Django app paketi |
| `apps/face_auth/apps.py` | AppConfig: `FaceAuthConfig` |
| `apps/face_auth/models.py` | `FaceProfile`, `FaceAuthLog` modellari |
| `apps/face_auth/admin.py` | Admin ro'yxatga olish (faqat o'qish rejimi) |
| `apps/face_auth/crypto.py` | Fernet AES-256 embedding shifrlash/ochish |
| `apps/face_auth/services/__init__.py` | Paket |
| `apps/face_auth/services/embeddings.py` | DeepFace ArcFace wrapper, sifat tekshiruvi, kadr dekodlash |
| `apps/face_auth/services/liveness.py` | Tasodifiy vazifa generatsiyasi + MediaPipe tekshiruvi |
| `apps/face_auth/services/verify.py` | Jonlilik + shaxsiyat uyg'unlashtirish |
| `apps/face_auth/api/__init__.py` | API paketi |
| `apps/face_auth/api/serializers.py` | DRF serializerlari |
| `apps/face_auth/api/urls.py` | URL manzillari |
| `apps/face_auth/api/views.py` | Barcha endpointlar: enroll, verify-login, status, OTP |
| `apps/face_auth/migrations/__init__.py` | Migratsiya paketi |
| `apps/face_auth/migrations/0001_initial.py` | `makemigrations` tomonidan yaratildi |
| `apps/face_auth/tests/__init__.py` | Test paketi |
| `apps/face_auth/tests/conftest.py` | Umumiy test fixturelar |
| `apps/face_auth/tests/test_enrollment.py` | 11 ta test (ro'yxatga olish) |
| `apps/face_auth/tests/test_liveness.py` | 17 ta test (jonlilik) |
| `apps/face_auth/tests/test_verify.py` | 11 ta test (tekshiruv + login gate) |
| `apps/face_auth/tests/test_lockout_fallback.py` | 8 ta test (bloklash + OTP) |
| `config/settings/test.py` | Test sozlamalari (SQLite, vlt_ai'siz) |
| `config/urls_test.py` | Test URL konfiguratsiyasi |
| `FACEID_PLAN.md` | Reja hujjati (Uzbek) |

### O'zgartirilgan fayllar

| Fayl | O'zgarish |
|------|-----------|
| `config/settings/base.py` | `apps.face_auth` INSTALLED_APPS'ga qo'shildi; Face Auth sozlamalari qo'shildi |
| `config/settings/windows.py` | `apps.face_auth` qo'shildi; os.environ orqali Face Auth sozlamalari |
| `config/urls.py` | `/api/v1/face-auth/` yo'llari qo'shildi |
| `apps/accounts/views.py` | `LoginView` ikki omillik yuz gate bilan kengaytirildi |
| `templates/erp/teacher_settings.html` | Face ID modali + holat belgilari + JS qo'shildi |
| `templates/erp/student_settings.html` | Face ID modali + holat belgilari + JS qo'shildi |
| `templates/erp/login.html` | Yuz tekshiruvi bosqichi UI (kamera + vazifa + kadrlar) qo'shildi |
| `requirements.txt` | `deepface`, `mediapipe`, `opencv-python`, `numpy`, `cryptography`, `pytest-mock` qo'shildi |
| `pytest.ini` | `config.settings.test` ga o'zgartirildi |

---

## Test natijalari

```
47 passed in 13.97s
```

### Testlar ro'yxati

**test_enrollment.py** (11 ta):
- ✅ `test_enroll_success` — muvaffaqiyatli ro'yxatga olish
- ✅ `test_reenroll_overwrites_old_embedding` — qayta ro'yxatga olish eski embeddingni almashtiradi
- ✅ `test_enroll_requires_consent` — roziliksiz rad etiladi
- ✅ `test_enroll_bad_frame` — noto'g'ri kadr rad etiladi
- ✅ `test_enroll_quality_fail_no_face` — yuz topilmasa DENIED
- ✅ `test_enroll_quality_fail_blurry` — xiralashgan tasvir DENIED
- ✅ `test_enroll_embedding_fail` — embedding chiqarib bo'lmasa DENIED
- ✅ `test_enroll_requires_auth` — autentifikatsiyasiz rad etiladi
- ✅ `test_status_not_enrolled` — ro'yxatda yo'q holat
- ✅ `test_status_enrolled` — ro'yxatdan o'tilgan holat
- ✅ `test_delete_enrollment` — ro'yxatdan o'chirish

**test_liveness.py** (17 ta):
- ✅ `test_static_image_fails` — statik tasvir harakatsiz → DENIED
- ✅ `test_varying_frames_pass` — o'zgaruvchan kadrlar → harakat bor
- ✅ `test_too_few_frames_fail` — kam kadrlar
- ✅ `test_none_frames_ignored` — None kadrlar
- ✅ `test_returns_known_action` — vazifa ro'yxatda mavjud
- ✅ `test_challenge_is_random` — vazifalar tasodifiy
- ✅ `test_empty_frames_denied` — bo'sh kadrlar DENIED
- ✅ `test_static_frames_denied` — statik kadrlar DENIED
- ✅ `test_unknown_action_denied` — noma'lum vazifa DENIED
- ✅ **9 ta parametrlangan test** (blink/blink_twice/smile/turn_left/turn_right — to'g'ri va noto'g'ri holatlar)

**test_verify.py** (11 ta):
- ✅ `test_verify_success` — to'liq muvaffaqiyatli tekshiruv → tokenlar qaytariladi
- ✅ `test_verify_audit_log_created` — har bir urinish jurnallashtiriladi
- ✅ `test_expired_token` — muddati o'tgan token DENIED
- ✅ `test_missing_token` — token yo'q DENIED
- ✅ `test_liveness_fail_denied` — jonlilik muvaffaqiyatsiz → 401
- ✅ `test_identity_mismatch_denied` — "Yuz mos kelmadi" → 401
- ✅ **`test_static_image_replay_denied`** — oldindan yozilgan/statik tasvir BLOKLANGAN
- ✅ `test_not_enrolled_denied` — ro'yxatga olinmagan DENIED
- ✅ `test_no_face_required_when_disabled` — FACE_AUTH_ENABLED=False → normal login
- ✅ `test_face_required_when_enrolled_and_enabled` — yoqilganda face_pending_token qaytariladi

**test_lockout_fallback.py** (8 ta):
- ✅ `test_lockout_after_max_attempts` — 5 urinishdan keyin 429
- ✅ `test_no_lockout_before_threshold` — chegara oldida 401 (429 emas)
- ✅ `test_old_failures_outside_window_do_not_lock` — eski urinishlar hisoba kirmaydi
- ✅ `test_otp_request_invalid_token` — noto'g'ri token DENIED
- ✅ `test_otp_request_success` — OTP emailga yuborildi
- ✅ `test_otp_verify_wrong_code` — noto'g'ri OTP DENIED
- ✅ `test_otp_full_flow` — to'liq OTP oqimi → tokenlar qaytariladi
- ✅ **`test_nobody_permanently_locked`** — hech kim abadiy bloklana olmaydi (OTP hali ham ishlaydi)

---

## Migratsiyalar

```
python manage.py migrate  (DJANGO_SETTINGS_MODULE=config.settings.test)
# Barcha migratsiyalar: 52 ta, barcha OK
# Jumladan: face_auth.0001_initial — OK
```

---

## Qarorlar va taxminlar

| Masala | Qaror | Sabab |
|--------|-------|-------|
| JWT-SPA'da "pending" holat | `django.core.signing` orqali 5 daqiqalik `face_pending_token` | Django sessiyasi SPA'da ishlamaydi; signing o'rnatilgan Django'da ishlaydi |
| Yuz embedding kutubxonasi | DeepFace (ArcFace → Facenet fallback) | InsightFace Windows'da Visual C++ talab qiladi; DeepFace osonroq |
| Jonlilik tekshiruvi (server) | MediaPipe Face Mesh (EAR, og'iz kengligi, burun x) | Ishonchli, real-vaqt, server tomonida qayta tekshirish mumkin |
| Shifrlash | Fernet (AES-128-CBC + HMAC-SHA256) | `cryptography` kutubxonasi ishonchli, Python'da keng qo'llaniladi |
| Qisqa-muddatli token | `django.core.signing.dumps/loads` | Qo'shimcha kutubxona kerak emas |
| OTP saqlash | Imzolangan token (session emas) | SPA API klientlari cookie/session yubormasligi mumkin |
| Kosinus chegara | 0.68 (sozlanadi) | ArcFace uchun o'rtacha tavsiya etilgan qiymat |
| Bloklash oynasi | 5 daqiqa ichida 5 urinish | Brute-force va spoofingdan himoya |

---

## TAKLIFLAR

**TAKLIF:** InsightFace (buffalo_l, 512-d) — DeepFace ArcFace'dan aniqroq va tezroq. Windows'da `pip install insightface` + Visual C++ 14.0 build tools o'rnatilsa ishlaydi. Foyda: alohida ONNX runtime, ko'p platformali.

**TAKLIF:** pgvector — kelajakda 1:N (barcha foydalanuvchilar bilan taqqoslash) kerak bo'lsa PostgreSQL'ga `pgvector` extension qo'shiladi. Hozir 1:1 bo'lgani uchun kerak emas.

**TAKLIF:** WebSocket orqali real-vaqt jonlilik tekshiruvi — hozir kadrlar batch yuboriladi (4 soniya, 16 kadr). Django Channels + WebSocket orqali kadr-kadr tekshiruv seziluvchanlikni oshiradi.

**TAKLIF:** Telegram bildirishnoma — muvaffaqiyatsiz Face ID urinishlari haqida adminga `apps.notifications` orqali yoki to'g'ridan Telegram xabari.

**TAKLIF:** Profil rasm + Face ID birlashishi — hozir alohida (xavfsizroq). Ixtiyoriy ravishda foydalanuvchi profil rasmidan Face ID reference sifatida foydalanishiga ruxsat berish mumkin.

**TAKLIF:** Rate limit Face ID endpointlari uchun alohida throttle scope — hozir umumiy throttling ishlatiladi. `DEFAULT_THROTTLE_RATES` ga `'face_auth': '10/min'` qo'shish mumkin.

---

## Qanday ishga tushirish

### 1. Muhit o'zgaruvchilari

`.env` fayliga quyidagilarni qo'shing:

```env
# Face ID (Fernet kalit yaratish)
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FACE_ENCRYPTION_KEY=<yuqoridagi buyruq natijasi>
FACE_AUTH_ENABLED=True
FACE_REQUIRED_ROLES=admin,developer
FACE_COSINE_THRESHOLD=0.68
FACE_MAX_ATTEMPTS=5
FACE_LOCKOUT_MINUTES=5
```

### 2. Migratsiyalar

```bash
python manage.py makemigrations face_auth
python manage.py migrate
```

### 3. Ro'yxatga olish (Enrollment)

1. `/teacher/profile/` yoki `/student/settings/` sahifasiga boring
2. Avatar yonidagi 📷 ikonasini bosing
3. Rozilik belgisini belgilang
4. Kameraga qarang → "Saqlash" tugmasini bosing
5. Holat: `Face ID: Yoqilgan` ga o'zgaradi

### 4. Login tekshiruvi (FACE_AUTH_ENABLED=True va ro'yxatdan o'tilgan bo'lsa)

1. `/login/` sahifasida telefon + parol kiriting
2. Parol to'g'ri bo'lsa, yuz tekshiruvi bosqichi paydo bo'ladi
3. Ekrandagi ko'rsatmani bajaring (masalan: "Jilmaying")
4. "Boshlash" tugmasini bosing → kamera 4 soniya kadr yig'adi
5. Server: jonlilik + shaxsiyat tekshiradi
6. Ikkalasi o'tsa → `{access, refresh, user}` qaytariladi va tizimga kirasiz

### 5. OTP zaxira kodi

Agar yuz tekshiruvi 3 marta muvaffaqiyatsiz bo'lsa:
1. "Zaxira kod" tugmasi paydo bo'ladi
2. Emailingizga 6 raqamli kod yuboriladi
3. Kodni kiriting → tizimga kirasiz

### 6. Testlarni ishga tushirish

```bash
python -m pytest apps/face_auth/tests/ -v
```

---

## Qabul qilish mezonlari (Acceptance Criteria)

| # | Mezon | Holat |
|---|-------|-------|
| 1 | `FACEID_PLAN.md` va `FACEID_REPORT.md` mavjud (Uzbek) | ✅ |
| 2 | Migratsiyalar tozalikda ishlaydi; 47/47 test yashil | ✅ |
| 3 | Profil sahifadan ro'yxatga olish — shifrlangan embedding saqlanadi | ✅ |
| 4 | Login: parol + tasodifiy jonlilik + shaxsiyat — middleware/token orqali | ✅ |
| 5 | Oldindan yozilgan/statik tasvir o'tolmaydi (`test_static_image_replay_denied`) | ✅ |
| 6 | Zaxira + bloklash mavjud; hech kim abadiy bloklana olmaydi | ✅ |
| 7 | Login kadrlari saqlanmaydi; hardcoded secret yo'q; 1:1 taqqoslash | ✅ |
