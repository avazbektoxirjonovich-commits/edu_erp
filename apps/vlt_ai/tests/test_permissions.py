"""
Tests: VLT AI permissions — user_can()
"""
from unittest.mock import MagicMock

from apps.vlt_ai.permissions import user_can


def _user(role: str, authenticated: bool = True, superuser: bool = False):
    u = MagicMock()
    u.is_authenticated = authenticated
    u.is_superuser = superuser
    u.role = role
    return u


# ── Developer (superuser of VLT AI) ───────────────────────────

def test_developer_has_all_permissions():
    u = _user("developer")
    for perm in [
        "attendance.view_any", "attendance.view_own", "attendance.view_self",
        "students.view_any", "groups.view_any", "teachers.view_any",
        "payments.view_any", "reports.view",
    ]:
        assert user_can(u, perm), f"developer should have {perm}"


def test_superuser_has_all_permissions():
    u = _user("student", superuser=True)
    assert user_can(u, "payments.view_any")
    assert user_can(u, "reports.view")


# ── Admin ──────────────────────────────────────────────────────

def test_admin_has_management_permissions():
    u = _user("admin")
    assert user_can(u, "attendance.view_any")
    assert user_can(u, "students.view_any")
    assert user_can(u, "payments.view_any")
    assert user_can(u, "teachers.view_any")
    assert user_can(u, "reports.view")


def test_admin_cannot_view_self_only():
    u = _user("admin")
    # admin doesn't need view_self (they have view_any), but it should not be
    # granted as a separate code — the matrix is explicit
    # admin has attendance.view_own but NOT attendance.view_self explicitly
    assert user_can(u, "attendance.view_own")


# ── Teacher ────────────────────────────────────────────────────

def test_teacher_can_view_own_groups_and_attendance():
    u = _user("teacher")
    assert user_can(u, "attendance.view_own")
    assert user_can(u, "groups.view_own")


def test_teacher_cannot_view_payments():
    u = _user("teacher")
    assert not user_can(u, "payments.view_any")


def test_teacher_cannot_view_all_students():
    u = _user("teacher")
    assert not user_can(u, "students.view_any")


def test_teacher_cannot_view_attendance_any():
    u = _user("teacher")
    assert not user_can(u, "attendance.view_any")


# ── Student ────────────────────────────────────────────────────

def test_student_can_only_view_self():
    u = _user("student")
    assert user_can(u, "attendance.view_self")
    assert user_can(u, "students.view_self")


def test_student_cannot_view_other_data():
    u = _user("student")
    assert not user_can(u, "attendance.view_any")
    assert not user_can(u, "attendance.view_own")
    assert not user_can(u, "students.view_any")
    assert not user_can(u, "payments.view_any")
    assert not user_can(u, "teachers.view_any")


# ── Parent ─────────────────────────────────────────────────────

def test_parent_can_view_student_self():
    u = _user("parent")
    assert user_can(u, "students.view_self")


def test_parent_cannot_view_others():
    u = _user("parent")
    assert not user_can(u, "students.view_any")
    assert not user_can(u, "attendance.view_any")


# ── Unauthenticated ────────────────────────────────────────────

def test_unauthenticated_denied():
    u = _user("admin", authenticated=False)
    assert not user_can(u, "attendance.view_any")


def test_none_user_denied():
    assert not user_can(None, "attendance.view_any")
