"""
VLT AI Tools — Kumush
======================
Tool: get_my_kumush
"""
from __future__ import annotations

import logging

from apps.vlt_ai.tools.registry import ai_tool
from apps.vlt_ai.tools.schemas import MY_KUMUSH_SCHEMA

logger = logging.getLogger("apps.vlt_ai.tools.kumush")


@ai_tool(
    name="get_my_kumush",
    required_permission="kumush.view_self",
    description=MY_KUMUSH_SCHEMA["description"],
    schema=MY_KUMUSH_SCHEMA,
)
def get_my_kumush(user) -> dict:
    """Return the current student's own Kumush balance and recent transactions.

    No ID argument — always resolved from the authenticated user's own
    student_profile.
    """
    from apps.store.models import KumushTransaction

    student = getattr(user, "student_profile", None)
    if student is None:
        return {"error": "O'quvchi profili topilmadi"}

    recent = list(
        KumushTransaction.objects.filter(student=student)
        .order_by("-created_at")
        .values("amount", "type", "reason", "created_at")[:20]
    )

    return {
        "balance": student.coins,
        "level": student.level,
        "xp_points": student.xp_points,
        "recent_transactions": [
            {
                "amount": t["amount"],
                "type": t["type"],
                "reason": t["reason"],
                "date": str(t["created_at"])[:16],
            }
            for t in recent
        ],
    }
