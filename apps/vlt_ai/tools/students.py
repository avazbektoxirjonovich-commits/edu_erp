"""
VLT AI Tools — Students
========================
Tools: get_students_list, get_student_stats
"""
from __future__ import annotations

import logging

from apps.vlt_ai.tools.registry import ai_tool
from apps.vlt_ai.tools.schemas import STUDENT_STATS_SCHEMA, STUDENTS_LIST_SCHEMA

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
    """Return detailed stats for a single student (admin/dev only)."""
    from apps.students.models import Student

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
