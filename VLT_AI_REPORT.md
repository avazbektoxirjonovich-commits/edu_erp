# VLT AI — Yakuniy Hisobot

**Sana:** 2026-06-03  
**Holat:** ✅ BARCHA QABUL QILISH MEZONLARI BAJARILDI  
**Test natijasi:** 32/32 ✅

---

## Bajarilgan ishlar

### 1. DISCOVERY.md
- Loyiha stack'i aniqlandi: Django 5.0.6, DRF 3.15.1, SimpleJWT, PostgreSQL/SQLite
- Real modellar o'qildi: `User`, `Student`, `Teacher`, `Group`, `Attendance`, `Payment`, `Assignment/Submission`
- Rol tizimi aniqlandi: `User.role` maydoni (admin/teacher/student/developer/parent)
- 7 ta v1 tool ro'yxati tuzildi
- Barcha natijar `DISCOVERY.md` faylida hujjatlashtirildi

### 2. `apps/vlt_ai/` moduli yaratildi

**Yaratilgan fayllar:**

| Fayl | Maqsad |
|------|--------|
| `__init__.py` | Python paketi |
| `apps.py` | Django app konfiguratsiyasi, `ready()` da toollarni ro'yxatdan o'tkazadi |
| `models.py` | `Conversation`, `Message`, `AILog` modellari |
| `admin.py` | Admin panel ro'yxatga olish |
| `permissions.py` | `user_can()` — kod ichidagi ruxsat boshqaruvi |
| `tools/registry.py` | `@ai_tool`, `TOOL_REGISTRY`, `get_allowed_tools()`, `execute_tool()` |
| `tools/schemas.py` | 7 ta Anthropic format JSON schema |
| `tools/attendance.py` | `get_group_attendance`, `get_my_attendance` |
| `tools/students.py` | `get_students_list`, `get_student_stats` |
| `tools/groups.py` | `get_teacher_groups` |
| `tools/teachers.py` | `get_teachers_list` |
| `tools/payments.py` | `get_payment_summary` |
| `services/llm_client.py` | Provider-agnostik LLM klient (Anthropic Claude) |
| `services/chat_service.py` | Orkestratsiya: savol → tool loop → SSE javob |
| `api/views.py` | `ChatView` (SSE), `ConversationListView`, `ConversationDetailView` |
| `api/serializers.py` | `ChatRequestSerializer`, `ConversationSerializer`, `MessageSerializer` |
| `api/urls.py` | URL marshrutlari |
| `migrations/0001_initial.py` | Dastlabki migratsiya (qo'lda yozilgan) |
| `tests/test_permissions.py` | 14 ta permission testi |
| `tests/test_tools.py` | 12 ta tool testi (DENIED yo'li ham tekshiriladi) |
| `tests/test_chat.py` | 6 ta API/integratsiya testi |

### 3. Yangilangan fayllar

| Fayl | O'zgarish |
|------|-----------|
| `config/settings/base.py` | `apps.vlt_ai` qo'shildi; VLT AI env o'zgaruvchilari |
| `config/urls.py` | `/api/v1/vlt-ai/` yo'li qo'shildi |
| `requirements.txt` | `anthropic>=0.40.0`, `pytest>=8.0`, `pytest-django>=4.8` |
| `.env` | `ANTHROPIC_API_KEY`, `VLT_AI_PROVIDER`, `VLT_AI_MODEL`, `VLT_AI_MAX_TOKENS` |

### 4. Migratsiya va testlar

```
python manage.py migrate  →  vlt_ai.0001_initial OK
python manage.py migrate  →  vlt_ai.0002_... OK (Django index nomi to'g'irlangan)

pytest apps/vlt_ai/tests/  →  32 passed ✅
```

---

## Qarorlar va taxminlar

| Masala | Qaror |
|--------|-------|
| LLM provayder yo'q edi | Anthropic Claude tanlandi (TAKLIF 1 ga qarang) |
| `pydantic` yo'q | Python `dataclasses` o'rniga to'g'ridan-to'g'ri kwargs ishlatildi (TAKLIF 2) |
| `pytest` yo'q | O'rnatildi va flaglandi (TAKLIF 3) |
| Django `has_perm` ishlatilmagan | `user_can()` + `ROLE_PERMISSIONS` dict yozildi (mavjud `User.role` bilan mos) |
| Baholar/ratings modeli yo'q | `Student.xp_points + level` gamification maydonlari "reyting" sifatida ishlatildi |
| `ANTHROPIC_API_KEY` yo'q edi | `.env` ga bo'sh placeholder qo'shildi |
| Toollarni streaming qilish murakkab | Tool call — sinxron, faqat yakuniy javob SSE orqali stream qilinadi (TAKLIF 4) |

---

## TAKLIFLAR

**TAKLIF 1:** `anthropic` paketi yangi dependency sifatida qo'shildi.
- **Sabab:** Loyihada hech qanday LLM integratsiyasi yo'q edi.
- **Foyda:** Anthropic Claude API — yetuk tool use va streaming qo'llab-quvvatlashiga ega.
- **Alternativa:** Keyinchalik `VLT_AI_PROVIDER=ollama` konfiguratsiyasi bilan lokal model ishlatish mumkin — `llm_client.py` provayderlarni almashtirish uchun tayyor qurilgan.

**TAKLIF 2:** `pydantic` o'rniga Python native yondashuvi.
- **Sabab:** Pydantic loyihada yo'q edi; tool argumentlari LLM tomonidan beriladi va JSON Schema orqali validatsiya qilinadi.
- **Foyda:** Pydantic qo'shilsa, tool inputlar yanada kuchli runtime validatsiyasiga ega bo'ladi, xatolar aniqroq chiqadi.
- **Qo'llash:** `pip install pydantic` va har bir tool faylida `class GetGroupAttendanceInput(BaseModel)` yarating.

**TAKLIF 3:** `pytest` + `pytest-django` yangi dependency.
- **Sabab:** Loyihada test tizimi yo'q edi.
- **Foyda:** Kelajakda barcha apps uchun bir xil test runner.
- **Qo'llash:** `pytest.ini` + `conftest.py` allaqachon konfiguratsiya qilingan.

**TAKLIF 4:** Haqiqiy LLM streaming (tool call jarayonida ham).
- **Sabab:** Hozirgi implementatsiyada tool call sinxron bajariladi va faqat yakuniy matn SSE orqali chiqariladi.
- **Foyda:** Foydalanuvchi tool bajarilayotganda ham "Davomati ko'rilmoqda..." kabi progress xabarlarini ko'radi.
- **Qo'llash:** Anthropic `stream_with_tools` + `input_json_delta` eventlarini qayta ishlash.

**TAKLIF 5:** `structlog` yoki Django structlog middleware.
- **Sabab:** Hozir standart `logging` ishlatiladi.
- **Foyda:** JSON formatidagi loglar — Render/production monitoring uchun qulayroq.

**TAKLIF 6:** `ruff` lint va format sozlash.
- **Sabab:** Loyihada hech qanday linter yo'q.
- **Foyda:** Kod sifatini avtomatik nazorat qilish.
- **Qo'llash:** `pip install ruff` → `ruff check . && ruff format .`

**TAKLIF 7:** VLT AI frontend sahifasi.
- **Sabab:** Backend to'liq tayyor, lekin UI yo'q.
- **Foyda:** Mavjud `erp/` shablonlari konvensiyasiga ko'ra `erp/vlt_ai.html` va URL qo'shish.

---

## Qanday ishga tushirish

### 1. `.env` faylini sozlang

```bash
# .env fayliga haqiqiy Anthropic API kalitini kiriting:
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx

# Ixtiyoriy — modelni o'zgartirish:
VLT_AI_MODEL=claude-haiku-4-5-20251001   # tezkor va arzon
# VLT_AI_MODEL=claude-sonnet-4-6         # aniqroq javoblar uchun
```

### 2. Migratsiyalarni bajaring

```bash
python manage.py migrate
```

### 3. Serverni ishga tushiring

```bash
python manage.py runserver
# yoki:
DJANGO_SETTINGS_MODULE=config.settings.development python manage.py runserver
```

### 4. API endpointlari

| Method | URL | Tavsif |
|--------|-----|--------|
| `POST` | `/api/v1/vlt-ai/chat/` | Streaming SSE chat (JWT talab qiladi) |
| `GET` | `/api/v1/vlt-ai/conversations/` | Foydalanuvchi suhbatlari ro'yxati |
| `GET` | `/api/v1/vlt-ai/conversations/<uuid>/` | Bitta suhbat + xabarlar |

### 5. Chat endpointga so'rov

```bash
# JWT token olish:
curl -X POST http://localhost:8000/api/v1/token/ \
  -H "Content-Type: application/json" \
  -d '{"phone": "+998901234567", "password": "your_password"}'

# Chat so'rovi (SSE stream):
curl -X POST http://localhost:8000/api/v1/vlt-ai/chat/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Python A1 guruhining bu oylik davomati qanday?"}' \
  --no-buffer
```

### 6. Testlarni ishga tushirish

```bash
# Barcha VLT AI testlari:
python -m pytest apps/vlt_ai/tests/ -v

# Faqat DENIED yo'lini tekshirish:
python -m pytest apps/vlt_ai/tests/test_tools.py -k "denied" -v
```

---

## Xavfsizlik modeli (3 qavatli himoya)

1. **Tool ro'yxati filtri** — LLM faqat foydalanuvchi chaqira oladigan toollarni ko'radi (`get_allowed_tools(user)`).
2. **Qayta tekshirish** — `execute_tool()` har bir bajarishdan oldin ruxsatni qayta tekshiradi.
3. **Satr darajasi filtri** — har bir tool faqat o'z foydalanuvchisiga tegishli ma'lumotlarni qaytaradi.

Har bir DENIED urinish `AILog` jadvaliga yoziladi.

---

## Test natijalari

```
32 passed in 10.47s ✅

test_permissions.py  14/14
test_tools.py        12/12  (DENIED yo'li ham tekshirildi)
test_chat.py          6/6   (SSE, autentifikatsiya, scope tekshiruvi)
```

Barcha qabul qilish mezonlari bajarildi.
