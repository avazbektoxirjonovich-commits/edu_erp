"""
VLT AI Tools — Groups
======================
Tool: get_teacher_groups
"""
from __future__ import annotations

import logging

from apps.vlt_ai.permissions import user_can
from apps.vlt_ai.tools.registry import ai_tool
from apps.vlt_ai.tools.schemas import MY_SCHEDULE_SCHEMA, TEACHER_GROUPS_SCHEMA

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


@ai_tool(
    name="get_my_schedule",
    required_permission="students.view_self",
    description=MY_SCHEDULE_SCHEMA["description"],
    schema=MY_SCHEDULE_SCHEMA,
)
def get_my_schedule(user) -> dict:
    """Return the current student's own group's lesson schedule.

    No ID argument — always resolved from the authenticated user's own
    student_profile → group.
    """
    student = getattr(user, "student_profile", None)
    if student is None:
        return {"error": "O'quvchi profili topilmadi"}
    group = student.group
    if group is None:
        return {"error": "Sizda hozircha guruh biriktirilmagan"}

    schedules = list(
        group.schedules.order_by("day_of_week").values("day_of_week", "room")
    )
    day_labels = dict(group.DayOfWeek.choices)

    return {
        "group_name": group.name,
        "subject": group.subject,
        "start_time": str(group.start_time),
        "end_time": str(group.end_time),
        "days": [
            {"day": day_labels.get(s["day_of_week"], s["day_of_week"]), "room": s["room"]}
            for s in schedules
        ],
    }
