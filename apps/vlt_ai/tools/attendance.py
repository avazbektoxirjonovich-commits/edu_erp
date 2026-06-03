"""
VLT AI Tools — Attendance
==========================
Tools: get_group_attendance, get_my_attendance
"""
from __future__ import annotations

import logging
from datetime import date

from apps.vlt_ai.permissions import user_can
from apps.vlt_ai.tools.registry import ai_tool
from apps.vlt_ai.tools.schemas import GROUP_ATTENDANCE_SCHEMA, MY_ATTENDANCE_SCHEMA

logger = logging.getLogger("apps.vlt_ai.tools.attendance")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


@ai_tool(
    name="get_group_attendance",
    required_permission="attendance.view_own",
    description=GROUP_ATTENDANCE_SCHEMA["description"],
    schema=GROUP_ATTENDANCE_SCHEMA,
)
def get_group_attendance(
    user,
    group_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Return attendance statistics for a group.

    Row-level scope: teacher → own groups only; admin/dev → any group.
    """
    from django.db.models import Count, Q

    from apps.attendance.models import Attendance
    from apps.groups.models import Group

    try:
        group = Group.objects.get(pk=group_id)
    except Group.DoesNotExist:
        return {"error": "Guruh topilmadi"}

    # Row-level check: teacher can only access their own groups
    if not user_can(user, "attendance.view_any"):
        teacher = getattr(user, "teacher_profile", None)
        if teacher is None or group.teacher_id != teacher.pk:
            return {"error": "Sizda bunga ruxsat yo'q"}

    qs = Attendance.objects.filter(group=group)

    d_from = _parse_date(date_from)
    d_to = _parse_date(date_to)
    if d_from:
        qs = qs.filter(date__gte=d_from)
    if d_to:
        qs = qs.filter(date__lte=d_to)

    stats = qs.aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(status="present")),
        absent=Count("id", filter=Q(status="absent")),
        late=Count("id", filter=Q(status="late")),
        excused=Count("id", filter=Q(status="excused")),
    )

    total = stats["total"] or 0
    present = stats["present"] or 0

    return {
        "group_id": str(group.id),
        "group_name": group.name,
        "subject": group.subject,
        "period": {"from": date_from, "to": date_to},
        "total_records": total,
        "present": present,
        "absent": stats["absent"] or 0,
        "late": stats["late"] or 0,
        "excused": stats["excused"] or 0,
        "attendance_pct": round(present * 100 / total, 1) if total else 0,
    }


@ai_tool(
    name="get_my_attendance",
    required_permission="attendance.view_self",
    description=MY_ATTENDANCE_SCHEMA["description"],
    schema=MY_ATTENDANCE_SCHEMA,
)
def get_my_attendance(
    user,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Return the current student's own attendance records."""
    from django.db.models import Count, Q

    from apps.attendance.models import Attendance

    student = getattr(user, "student_profile", None)
    if student is None:
        return {"error": "O'quvchi profili topilmadi"}

    qs = Attendance.objects.filter(student=student)

    d_from = _parse_date(date_from)
    d_to = _parse_date(date_to)
    if d_from:
        qs = qs.filter(date__gte=d_from)
    if d_to:
        qs = qs.filter(date__lte=d_to)

    stats = qs.aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(status="present")),
        absent=Count("id", filter=Q(status="absent")),
        late=Count("id", filter=Q(status="late")),
        excused=Count("id", filter=Q(status="excused")),
    )

    total = stats["total"] or 0
    present = stats["present"] or 0

    recent = list(
        qs.order_by("-date").values("date", "status", "note")[:30]
    )

    return {
        "student_name": user.full_name,
        "period": {"from": date_from, "to": date_to},
        "total_records": total,
        "present": present,
        "absent": stats["absent"] or 0,
        "late": stats["late"] or 0,
        "excused": stats["excused"] or 0,
        "attendance_pct": round(present * 100 / total, 1) if total else 0,
        "recent_records": [
            {"date": str(r["date"]), "status": r["status"], "note": r["note"]}
            for r in recent
        ],
    }
