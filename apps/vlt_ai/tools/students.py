"""
VLT AI Tools — Students
========================
Tools: get_students_list, get_student_stats
"""
from __future__ import annotations

import logging

from apps.vlt_ai.permissions import user_can
from apps.vlt_ai.tools.registry import ai_tool
from apps.vlt_ai.tools.schemas import (
    MY_PROFILE_SCHEMA,
    MY_STUDENTS_SCHEMA,
    STUDENT_STATS_SCHEMA,
    STUDENTS_LIST_SCHEMA,
)

logger = logging.getLogger("apps.vlt_ai.tools.students")


@ai_tool(
    name="get_students_list",
    required_permission="students.view_any",
    description=STUDENTS_LIST_SCHEMA["description"],
    schema=STUDENTS_LIST_SCHEMA,
)
def get_students_list(
    user,
    group_id: str | None = None,
    status: str | None = None,
) -> dict:
    """Return a filtered list of students (admin/dev only)."""
    from apps.students.models import Student

    qs = Student.objects.select_related("user", "group")

    if group_id:
        qs = qs.filter(group_id=group_id)
    if status:
        qs = qs.filter(status=status)

    rows = list(
        qs.values(
            "id",
            "user__full_name",
            "phone",
            "status",
            "group__name",
            "xp_points",
            "level",
            "joined_date",
        )[:100]
    )

    return {
        "count": len(rows),
        "students": [
            {
                "id": str(r["id"]),
                "name": r["user__full_name"],
                "phone": r["phone"],
                "status": r["status"],
                "group": r["group__name"],
                "xp": r["xp_points"],
                "level": r["level"],
                "joined": str(r["joined_date"]),
            }
            for r in rows
        ],
    }


@ai_tool(
    name="get_student_stats",
    required_permission="students.view_any",
    description=STUDENT_STATS_SCHEMA["description"],
    schema=STUDENT_STATS_SCHEMA,
)
def get_student_stats(user, student_id: str) -> dict:
    """Return detailed stats for a single student (admin/dev only).

    Defense-in-depth: this tool is currently only reachable by callers
    holding students.view_any (enforced by execute_tool before this function
    ever runs). The explicit self-only fallback below is not load-bearing
    today, but protects against a future change that attaches this same
    function to a students.view_self-gated tool entry, or a bug in
    ROLE_PERMISSIONS — a caller without students.view_any can only ever
    read their own student_id, never an arbitrary one from the LLM.
    """
    from apps.students.models import Student

    if not user_can(user, "students.view_any"):
        own_student = getattr(user, "student_profile", None)
        if own_student is None or str(own_student.pk) != str(student_id):
            return {"error": "Sizda bunga ruxsat yo'q"}

    try:
        student = Student.objects.select_related("user", "group").get(pk=student_id)
    except Student.DoesNotExist:
        return {"error": "O'quvchi topilmadi"}

    return {
        "id": str(student.id),
        "name": student.full_name,
        "group": student.group.name if student.group else None,
        "status": student.status,
        "xp_points": student.xp_points,
        "coins": student.coins,
        "level": student.level,
        "xp_to_next_level": student.xp_to_next_level,
        "level_progress_pct": student.level_progress_pct,
        "attendance_pct": student.attendance_percentage,
        "total_debt": float(student.total_debt),
        "joined": str(student.joined_date),
    }


@ai_tool(
    name="get_my_profile",
    required_permission="students.view_self",
    description=MY_PROFILE_SCHEMA["description"],
    schema=MY_PROFILE_SCHEMA,
)
def get_my_profile(user) -> dict:
    """Return the current student's own profile. No ID argument — always
    resolved from the authenticated user's student_profile, so there is
    nothing here an LLM tool-call argument could spoof."""
    student = getattr(user, "student_profile", None)
    if student is None:
        return {"error": "O'quvchi profili topilmadi"}

    return {
        "id": str(student.id),
        "name": student.full_name,
        "phone": student.phone,
        "group": student.group.name if student.group else None,
        "status": student.status,
        "xp_points": student.xp_points,
        "coins": student.coins,
        "level": student.level,
        "xp_to_next_level": student.xp_to_next_level,
        "level_progress_pct": student.level_progress_pct,
        "joined": str(student.joined_date),
    }


@ai_tool(
    name="get_my_students",
    required_permission="students.view_own",
    description=MY_STUDENTS_SCHEMA["description"],
    schema=MY_STUDENTS_SCHEMA,
)
def get_my_students(user, group_id: str | None = None) -> dict:
    """Return students in the calling teacher's own groups only.

    Row-level scope: always filtered through teacher_profile.groups — a
    group_id argument outside the teacher's own groups yields zero rows,
    it is never used to bypass ownership.
    """
    from apps.students.models import Student

    teacher = getattr(user, "teacher_profile", None)
    if teacher is None:
        return {"error": "O'qituvchi profili topilmadi"}

    own_group_ids = list(teacher.groups.values_list("id", flat=True))
    if group_id and group_id not in {str(g) for g in own_group_ids}:
        return {"error": "Bu guruh sizga tegishli emas"}

    qs = Student.objects.select_related("user", "group").filter(
        group_id__in=([group_id] if group_id else own_group_ids)
    )

    rows = list(
        qs.values(
            "id", "user__full_name", "phone", "status",
            "group__name", "xp_points", "level",
        )[:200]
    )

    return {
        "count": len(rows),
        "students": [
            {
                "id": str(r["id"]),
                "name": r["user__full_name"],
                "phone": r["phone"],
                "status": r["status"],
                "group": r["group__name"],
                "xp": r["xp_points"],
                "level": r["level"],
            }
            for r in rows
        ],
    }
