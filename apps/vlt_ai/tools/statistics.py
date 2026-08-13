"""
VLT AI Tools — Admin statistics
================================
Tools: get_student_statistics, get_attendance_statistics
"""
from __future__ import annotations

import logging

from apps.vlt_ai.tools.registry import ai_tool
from apps.vlt_ai.tools.schemas import (
    ATTENDANCE_STATISTICS_SCHEMA,
    STUDENT_STATISTICS_SCHEMA,
)

logger = logging.getLogger("apps.vlt_ai.tools.statistics")


@ai_tool(
    name="get_student_statistics",
    required_permission="students.view_any",
    description=STUDENT_STATISTICS_SCHEMA["description"],
    schema=STUDENT_STATISTICS_SCHEMA,
)
def get_student_statistics(user) -> dict:
    """Overall student counts by status and by group (admin/dev only)."""
    from django.db.models import Count

    from apps.students.models import Student

    by_status = dict(
        Student.objects.values_list("status").annotate(n=Count("id")).order_by()
    )
    top_groups = list(
        Student.objects.filter(status="active", group__isnull=False)
        .values("group__name")
        .annotate(n=Count("id"))
        .order_by("-n")[:10]
    )

    return {
        "total_students": Student.objects.count(),
        "by_status": by_status,
        "top_groups": [{"group": g["group__name"], "count": g["n"]} for g in top_groups],
    }


@ai_tool(
    name="get_attendance_statistics",
    required_permission="attendance.view_any",
    description=ATTENDANCE_STATISTICS_SCHEMA["description"],
    schema=ATTENDANCE_STATISTICS_SCHEMA,
)
def get_attendance_statistics(user, month: int | None = None, year: int | None = None) -> dict:
    """Overall attendance statistics across all groups (admin/dev only)."""
    from django.db.models import Count, Q
    from django.utils import timezone

    from apps.attendance.models import Attendance

    now = timezone.localdate()
    month = month or now.month
    year = year or now.year

    qs = Attendance.objects.filter(date__month=month, date__year=year)
    agg = qs.aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(status="present")),
        absent=Count("id", filter=Q(status="absent")),
        late=Count("id", filter=Q(status="late")),
        excused=Count("id", filter=Q(status="excused")),
    )
    total = agg["total"] or 0
    present = agg["present"] or 0

    return {
        "period": {"month": month, "year": year},
        "total_records": total,
        "present": present,
        "absent": agg["absent"] or 0,
        "late": agg["late"] or 0,
        "excused": agg["excused"] or 0,
        "attendance_pct": round(present * 100 / total, 1) if total else 0,
    }
