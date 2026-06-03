# VLT AI — DISCOVERY REPORT

Generated: 2026-06-03 (autonomous discovery step)

---

## 1. Detected Stack

| Component       | Value                          |
|-----------------|--------------------------------|
| Python          | 3.x (venv detected)            |
| Django          | 5.0.6                          |
| API Framework   | djangorestframework 3.15.1     |
| Auth            | SimpleJWT (djangorestframework-simplejwt 5.3.1) |
| Database (dev)  | SQLite (config/settings/development.py) |
| Database (prod) | PostgreSQL 5432                |
| Config          | python-decouple                |
| Admin           | django-jazzmin 3.0.0           |
| LLM (new)       | anthropic SDK (to be added)    |

---

## 2. Apps Path Convention

All apps live under `apps/`. The new module will be created as `apps/vlt_ai/`.

---

## 3. Role / Permission System

The project uses a **custom role field** on `User` model — NOT Django's `Group`/`Permission` system.

```python
class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN     = 'admin'
        TEACHER   = 'teacher'
        STUDENT   = 'student'
        DEVELOPER = 'developer'
        PARENT    = 'parent'

    role = models.CharField(max_length=10, choices=Role.choices, ...)
```

Helper properties: `is_admin`, `is_teacher`, `is_student`, `is_developer`, `is_parent`, `is_staff_level`.

Existing DRF permission classes: `IsStaffLevel`, `IsAdmin`, `IsTeacher`, `IsStudent`, `IsAdminOrTeacher`, etc. — all in `apps/accounts/permissions.py`.

**Decision:** VLT AI will define its own `user_can(user, permission_code)` helper that maps role → set of permission codes. This is consistent with the existing pattern and avoids Django's `has_perm` which is not used in this project.

---

## 4. Real Models Found

### accounts.User
- `id` (UUID PK), `phone` (unique login), `full_name`, `role`, `is_active`, `is_staff`
- Related: `student_profile` (OneToOne → Student), `teacher_profile` (OneToOne → Teacher)

### students.Student
- `id` (UUID), `user` (OneToOne → User), `group` (FK → Group), `phone`, `parent_phone`
- `status` (active/inactive/frozen), `joined_date`
- **Gamification:** `xp_points`, `coins`, `level`
- Property: `attendance_percentage`, `total_debt`

### teachers.Teacher
- `id` (UUID), `user` (OneToOne → User), `phone`, `subject`, `salary`, `is_active`
- Reverse: `groups` (Teacher.groups → Group queryset)
- Property: `group_count`

### groups.Group
- `id` (UUID), `name`, `subject`, `description`
- `teacher` (FK → Teacher), `status` (active/inactive/completed)
- `max_students`, `monthly_fee`, `start_date`, `end_date`, `start_time`, `end_time`
- Reverse: `students`, `attendances`, `payments`, `schedules`, `assignments`

### groups.LessonSchedule
- `id` (UUID), `group` (FK), `day_of_week` (int), `room`

### attendance.Attendance
- `id` (UUID), `student` (FK → Student), `group` (FK → Group), `date`
- `status` (present/absent/late/excused), `note`, `marked_by` (FK → User)
- Unique: (student, group, date)

### payments.Payment
- `id` (UUID), `student` (FK), `group` (FK), `month`, `year`
- `amount`, `paid_amount`, `debt_amount`, `discount`
- `status` (paid/partial/unpaid), `payment_date`, `received_by` (FK → User)
- Unique: (student, group, month, year)

### homework.Assignment + Submission
- Assignment: `title`, `description`, `due_date`, `max_score`, `xp_reward`, `status`, `group`, `teacher`
- Submission: `answer`, `score`, `feedback`, `status`, `assignment`, `student`, `graded_by`

### notifications.Notification + ActivityLog
- Notification: SMS/Telegram/System notifications
- ActivityLog: System-wide action log

---

## 5. V1 Tools (6 tools)

| # | Tool Name              | Permission Code       | Data Scope                        | Model(s)               |
|---|------------------------|-----------------------|-----------------------------------|------------------------|
| 1 | `get_group_attendance` | `attendance.view_own` | admin/dev: any; teacher: own only | Attendance, Group      |
| 2 | `get_my_attendance`    | `attendance.view_self`| student: self only                | Attendance             |
| 3 | `get_students_list`    | `students.view_any`   | admin/dev only                    | Student, Group         |
| 4 | `get_student_stats`    | `students.view_any`   | admin/dev only                    | Student                |
| 5 | `get_teacher_groups`   | `groups.view_own`     | admin/dev: any; teacher: own only | Group, Teacher         |
| 6 | `get_payment_summary`  | `payments.view_any`   | admin/dev only                    | Payment                |
| 7 | `get_teachers_list`    | `teachers.view_any`   | admin/dev only                    | Teacher                |

---

## 6. Permission Matrix

| Role      | attendance.view_any | attendance.view_own | attendance.view_self | students.view_any | students.view_self | groups.view_any | groups.view_own | teachers.view_any | payments.view_any |
|-----------|--------------------|--------------------|---------------------|------------------|--------------------|----------------|----------------|------------------|------------------|
| developer | ✓                  | ✓                  | ✓                   | ✓                | ✓                  | ✓              | ✓              | ✓                | ✓                |
| admin     | ✓                  | ✓                  | -                   | ✓                | -                  | ✓              | ✓              | ✓                | ✓                |
| teacher   | -                  | ✓                  | -                   | -                | -                  | -              | ✓              | -                | -                |
| student   | -                  | -                  | ✓                   | -                | ✓                  | -              | -              | -                | -                |
| parent    | -                  | -                  | -                   | -                | ✓                  | -              | -              | -                | -                |

---

## 7. Missing Fields / Assumptions

| Issue | Decision |
|-------|----------|
| No AI/LLM dependency in requirements.txt | Add `anthropic` SDK — flagged as TAKLIF |
| No `pydantic` in requirements.txt | Use Python `dataclasses` for input validation — Pydantic flagged as TAKLIF |
| No `pytest-django` in requirements.txt | Add `pytest` + `pytest-django` for tests — flagged as TAKLIF |
| `ANTHROPIC_API_KEY` not in `.env` | Added as empty placeholder — user must set it |
| No grades/rating model found | Using gamification fields (xp_points, level) on Student as "rating" proxy |
| branches app exists but not fully explored | Ignored for v1 — no FK in core models |

---

## 8. Module Location

```
apps/vlt_ai/          ← new module (following apps/ convention)
```

INSTALLED_APPS entry: `'apps.vlt_ai'`
URL prefix: `/api/v1/vlt-ai/`
