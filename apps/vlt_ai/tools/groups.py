"""
VLT AI Tools — Groups
======================
Tool: get_teacher_groups
"""
from __future__ import annotations

import logging

from apps.vlt_ai.permissions import user_can
from apps.vlt_ai.tools.registry import ai_tool
from apps.vlt_ai.tools.schemas import TEACHER_GROUPS_SCHEMA

logger = logging.getLogger("apps.vlt_ai.tools.groups")


@ai_tool(
    name="get_teacher_groups",
    required_permission="groups.view_own",
    description=TEACHER_GROUPS_SCHEMA["description"],
    schema=TEACHER_GROUPS_SCHEMA,
)
def get_teacher_groups(user, teacher_id: str | None = None) -> dict:
    """Return active groups for a teacher.

    Row-level scope: teacher → own groups only; admin/dev → any (or filtered by teacher_id).
    """
    from apps.groups.models import Group

    qs = Group.objects.filter(status="active").select_related("teacher__user")

    if not user_can(user, "groups.view_any"):
        # Teacher can only see their own groups
        teacher = getattr(user, "teacher_profile", None)
        if teacher is None:
            return {"error": "O'qituvchi profili topilmadi"}
        qs = qs.filter(teacher=teacher)
    elif teacher_id:
        qs = qs.filter(teacher_id=teacher_id)

    rows = list(
        qs.values(
            "id",
            "name",
            "subject",
            "status",
            "teacher__user__full_name",
            "max_students",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
        )
    )

    return {
        "count": len(rows),
        "groups": [
            {
                "id": str(g["id"]),
                "name": g["name"],
                "subject": g["subject"],
                "teacher": g["teacher__user__full_name"],
                "max_students": g["max_students"],
                "start_date": str(g["start_date"]),
                "end_date": str(g["end_date"]) if g["end_date"] else None,
                "time": f"{g['start_time']} – {g['end_time']}",
            }
            for g in rows
        ],
    }
