"""
VLT AI Tools — Teachers
========================
Tool: get_teachers_list
"""
from __future__ import annotations

import logging

from apps.vlt_ai.tools.registry import ai_tool
from apps.vlt_ai.tools.schemas import TEACHERS_LIST_SCHEMA

logger = logging.getLogger("apps.vlt_ai.tools.teachers")


@ai_tool(
    name="get_teachers_list",
    required_permission="teachers.view_any",
    description=TEACHERS_LIST_SCHEMA["description"],
    schema=TEACHERS_LIST_SCHEMA,
)
def get_teachers_list(user) -> dict:
    """Return active teachers with their group counts (admin/dev only)."""
    from apps.teachers.models import Teacher

    teachers = (
        Teacher.objects.filter(is_active=True)
        .select_related("user")
        .prefetch_related("groups")
    )

    return {
        "count": teachers.count(),
        "teachers": [
            {
                "id": str(t.id),
                "name": t.full_name,
                "subject": t.subject,
                "phone": t.phone,
                "group_count": t.group_count,
            }
            for t in teachers
        ],
    }
