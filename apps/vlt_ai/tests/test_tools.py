"""
Tests: VLT AI tool registry & tool execution
"""
import pytest
from django.contrib.auth import get_user_model

from apps.vlt_ai.models import AILog
from apps.vlt_ai.tools.registry import TOOL_REGISTRY, execute_tool

User = get_user_model()


# ── Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        phone="+998901110001",
        password="testpass123",
        full_name="Test Admin",
        role="admin",
    )


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        phone="+998901110002",
        password="testpass123",
        full_name="Test Teacher",
        role="teacher",
    )


@pytest.fixture
def student_user(db):
    return User.objects.create_user(
        phone="+998901110003",
        password="testpass123",
        full_name="Test Student",
        role="student",
    )


# ── Registry sanity ────────────────────────────────────────────

def test_tools_registered():
    """All expected tools must appear in the registry."""
    expected = {
        "get_group_attendance",
        "get_my_attendance",
        "get_students_list",
        "get_student_stats",
        "get_teacher_groups",
        "get_payment_summary",
        "get_teachers_list",
    }
    assert expected.issubset(set(TOOL_REGISTRY.keys()))


def test_each_tool_has_schema():
    for name, spec in TOOL_REGISTRY.items():
        assert spec["schema"], f"Tool {name!r} has no schema"
        assert "name" in spec["schema"], f"Tool {name!r} schema missing 'name'"
        assert "input_schema" in spec["schema"], f"Tool {name!r} schema missing 'input_schema'"


# ── DENIED path (critical security test) ──────────────────────

@pytest.mark.django_db
def test_student_denied_students_list(student_user):
    """Student must NOT be able to call get_students_list."""
    result = execute_tool(student_user, "get_students_list", {})
    assert result.get("error") == "Sizda bunga ruxsat yo'q"


@pytest.mark.django_db
def test_student_denied_logs_to_db(student_user):
    """Every DENIED call must be recorded in AILog."""
    execute_tool(student_user, "get_students_list", {})
    assert AILog.objects.filter(
        user=student_user,
        tool_name="get_students_list",
        status=AILog.Status.DENIED,
    ).exists()


@pytest.mark.django_db
def test_student_denied_payment_summary(student_user):
    result = execute_tool(student_user, "get_payment_summary", {})
    assert result.get("error") == "Sizda bunga ruxsat yo'q"


@pytest.mark.django_db
def test_teacher_denied_payment_summary(teacher_user):
    result = execute_tool(teacher_user, "get_payment_summary", {})
    assert result.get("error") == "Sizda bunga ruxsat yo'q"


@pytest.mark.django_db
def test_teacher_denied_students_list(teacher_user):
    result = execute_tool(teacher_user, "get_students_list", {})
    assert result.get("error") == "Sizda bunga ruxsat yo'q"


# ── OK path ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_admin_students_list_ok(admin_user):
    """Admin must receive an empty students list (no students in test DB)."""
    result = execute_tool(admin_user, "get_students_list", {})
    assert "error" not in result
    assert "students" in result
    assert result["count"] == 0


@pytest.mark.django_db
def test_admin_payment_summary_ok(admin_user):
    result = execute_tool(admin_user, "get_payment_summary", {})
    assert "error" not in result
    assert "total_count" in result


@pytest.mark.django_db
def test_admin_teachers_list_ok(admin_user):
    result = execute_tool(admin_user, "get_teachers_list", {})
    assert "error" not in result
    assert "teachers" in result


@pytest.mark.django_db
def test_admin_ok_logs_to_db(admin_user):
    execute_tool(admin_user, "get_students_list", {})
    assert AILog.objects.filter(
        user=admin_user,
        tool_name="get_students_list",
        status=AILog.Status.OK,
    ).exists()


# ── Unknown tool ───────────────────────────────────────────────

@pytest.mark.django_db
def test_unknown_tool_returns_error(admin_user):
    result = execute_tool(admin_user, "does_not_exist", {})
    assert "error" in result
