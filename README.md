# EduERP

**A multi-module ERP for education centers, built on Django + DRF, with optional biometric authentication, an AI admin assistant, and a sandboxed coding-challenge platform.**

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.0-092E20?logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/DRF-3.15-A30000)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-production-4169E1?logo=postgresql&logoColor=white)
![Tests](https://img.shields.io/badge/tests-35%20files-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)

[English](README.md) | [O'zbek](README.uz.md)

## Description

EduERP manages the day-to-day operations of an education center: student and teacher records, group schedules, attendance, payments, and finance/accounting. Three optional extensions are layered on top of the core ERP — they are separate, independently-toggleable modules, not part of the basic ERP:

- **Biometric authentication** (`face_auth`) — face-based 2FA with liveness detection
- **AI admin assistant** (`vlt_ai`) — a Claude-powered chat assistant with tool access, scoped by role permissions
- **ZUKKO** (`zukko`) — a sandboxed code-execution environment for coding challenges

## Demo

![Demo](docs/gifs/demo.gif)

Captured against a real running instance (SQLite dev settings, seed data from `scripts/create_sample_data.py`). Video: not captured in the current environment — no screen-recording tooling was available; see [docs/video/README.md](docs/video/README.md).

## Screenshots

| Feature | Preview |
|---|---|
| Login | ![Login](docs/screenshots/01-login.png) |
| Dashboard | ![Dashboard](docs/screenshots/02-dashboard.png) |
| Students | ![Students](docs/screenshots/03-students.png) |
| Attendance | ![Attendance](docs/screenshots/04-attendance.png) |
| Finance | ![Finance](docs/screenshots/05-finance.png) |

AI Assistant and face-auth screens are not captured here — both require a live Anthropic API call / an enrolled face respectively, neither of which this pass exercised.

## Features

- Student, teacher, and group management with role-based access (Admin / Teacher / Student)
- Attendance tracking and statistics
- Payments, debts, and a dedicated finance module (expenses, assets, audit trail, receipts)
- A points/rewards system ("KUMUSH") tied into attendance, homework, and the store
- An in-app store with purchase lifecycle and manual balance adjustments
- Homework assignment and tracking
- Leaderboards, notifications, and PDF report export
- Error monitoring module with fingerprinted error capture and manual analysis tooling
- Parent portal and dedicated student/teacher self-service portals
- **Extension:** face-based 2FA login with liveness and cosine-similarity verification
- **Extension:** an AI chat assistant for admins, with rate-limited, permission-scoped tool access
- **Extension:** ZUKKO — teacher-assigned coding challenges executed in a `RestrictedPython` sandbox, with focus-mode sessions and shareable results

## Architecture

![Architecture](docs/architecture/system-architecture.svg)

Summary:

```
Browser (server-rendered templates + REST clients)
    ↓
Django / DRF  (apps/*, /api/v1/*)
    ↓
Per-app service & model layer
    ↓
PostgreSQL (production) / SQLite (local dev)
```

## AI/ML Pipeline

Two independent, optional subsystems — neither is part of the ERP's core request/response path:

**AI Assistant** — see [docs/architecture/ai-assistant-flow.svg](docs/architecture/ai-assistant-flow.svg)
```
Admin chat request
    ↓
apps.vlt_ai  (permission check, rate limit)
    ↓
Anthropic Claude API  (configurable model, default claude-haiku-4-5-20251001)
    ↓
Tool-scoped response
```

**Face Authentication** — see [docs/architecture/face-auth-flow.svg](docs/architecture/face-auth-flow.svg)
```
Camera capture
    ↓
Liveness check (MiniFASNetV2)
    ↓
Face embedding (InsightFace / onnxruntime)
    ↓
Encrypted embedding store, cosine-similarity match
    ↓
Login decision (with attempt limits + lockout)
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.0.6, Django REST Framework 3.15.1 |
| Auth | djangorestframework-simplejwt 5.3.1 |
| Database | PostgreSQL (`psycopg2-binary`, `dj-database-url`); SQLite for local/test |
| Admin UI | django-jazzmin |
| AI Assistant | Anthropic Claude API |
| Biometric | InsightFace, onnxruntime, OpenCV, `cryptography` |
| Sandbox | RestrictedPython |
| Exports | openpyxl, reportlab (PDF) |
| Static/Media | WhiteNoise (static), Cloudinary (production media, optional) |
| Server | Gunicorn |
| Config | python-decouple |
| Testing | pytest, pytest-django, pytest-mock |

## Database

PostgreSQL in production (`DATABASE_URL` or discrete `DB_*` variables), SQLite for local development and the test suite. Schema is managed through Django migrations, one app per domain (see Project Structure).

## API

All endpoints are namespaced under `/api/v1/`:

| Path | Purpose |
|---|---|
| `auth/`, `token/`, `token/refresh/`, `token/verify/` | JWT authentication |
| `students/`, `teachers/`, `groups/`, `attendance/` | Core ERP resources |
| `payments/`, `finance/` | Billing and accounting |
| `dashboard/`, `notifications/`, `leaderboard/` | Aggregated views |
| `homework/`, `store/`, `reports/monthly-pdf/` | Learning & rewards |
| `vlt-ai/` | AI assistant chat (extension) |
| `face-auth/` | Biometric login (extension) |
| `challenges/` | ZUKKO coding challenges (extension) |
| `error-monitor/` | Error capture/analysis |

The same functionality is also exposed as server-rendered pages (dashboard, portals, ZUKKO sessions) — see `config/urls.py` for the full route list.

## Security

- `SECRET_KEY` has **no fallback value** in production — deployment fails immediately if it is unset, rather than silently running with a known default.
- `.env` is git-ignored; only `.env.example` (variable names, no values) is committed.
- Production enforces HSTS, secure cookies, SSL redirect, and an explicit CORS allow-list (`CORS_ALLOW_ALL_ORIGINS = False`).
- Face embeddings are stored encrypted (`FACE_ENCRYPTION_KEY`), with configurable attempt limits and lockout.
- The ZUKKO sandbox executes submitted code through `RestrictedPython`, not a raw `exec`.

## Testing

35 test files across `attendance`, `error_monitor`, `face_auth`, `finance`, `homework`, `store`, `students`, `teachers`, `vlt_ai`, and `zukko`, run with `pytest-django`:

```bash
pytest
```

## Deployment

Configured for [Render.com](https://render.com) (`render.yaml`, `Procfile`, `runtime.txt`): Gunicorn + WhiteNoise for static files, optional Cloudinary storage for media, PostgreSQL via `DATABASE_URL`.

## Installation

```bash
git clone https://github.com/avazbektoxirjonovich-commits/edu_erp.git
cd edu_erp
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # then fill in your own values
python manage.py migrate
python manage.py runserver
```

## Environment Variables

See [`.env.example`](.env.example) for the full list. Required for a minimal local run: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, database settings. The AI assistant and face-auth extensions require their own keys (`ANTHROPIC_API_KEY`, `FACE_ENCRYPTION_KEY`) and are disabled by default (`FACE_AUTH_ENABLED=False`).

## Project Structure

```
erp_system/
├── config/
│   └── settings/
│       ├── base.py          # shared settings
│       ├── development.py   # local dev
│       └── production.py    # Render deployment
├── apps/
│   ├── accounts/     teachers/    groups/       attendance/
│   ├── students/     payments/    finance/      dashboard/
│   ├── homework/     store/       notifications/ error_monitor/
│   ├── face_auth/    # extension — biometric 2FA
│   ├── vlt_ai/       # extension — AI admin assistant
│   └── zukko/        # extension — coding-challenge sandbox
├── docs/
│   ├── architecture/  screenshots/  gifs/  video/
│   ├── API.md  DEPLOYMENT.md
├── templates/erp/     # server-rendered pages
├── requirements.txt
└── .env.example
```

## Roadmap

- [ ] Automated CI (test suite currently runs locally only)
- [ ] Recorded demo GIF/video and captured screenshots
- [ ] Expanded API documentation

## License

MIT — see [LICENSE](LICENSE).
