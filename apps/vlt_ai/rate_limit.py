"""
VLT AI — Per-role rate limiting
=================================
Backend-enforced only — the frontend must never be trusted to self-limit.

DB-based (counts this user's own Message rows in the trailing hour) rather
than cache-based: this project has no CACHES backend configured anywhere
(confirmed — Django would silently fall back to per-process LocMemCache),
which would under-count across multiple app-server workers in production.
Counting real Message rows works correctly regardless of process count and
needs no new infrastructure.
"""
from __future__ import annotations

from datetime import timedelta
from typing import NamedTuple

from django.utils import timezone

# None = unlimited (developer only).
RATE_LIMITS: dict[str, int | None] = {
    "developer": None,
    "admin": 10,
    "teacher": 5,
    "student": 2,
    "parent": 2,
    "finance": 5,
}

RATE_LIMIT_MESSAGE = (
    "Sizning AI savol limitingiz tugadi.\n"
    "Keyingi soatda qayta urinib ko'ring."
)


class RateLimitStatus(NamedTuple):
    allowed: bool
    limit: int | None
    used: int
    remaining: int | None


def check_ai_rate_limit(user) -> RateLimitStatus:
    """Return whether `user` may ask another AI question right now.

    Developer role and superusers are always unlimited. Every other role is
    capped by RATE_LIMITS against a rolling 1-hour window, counted from
    persisted Message rows — never from anything the client reports.
    """
    from apps.vlt_ai.models import Message

    role: str = getattr(user, "role", "") or ""
    if getattr(user, "is_superuser", False) or role == "developer":
        return RateLimitStatus(True, None, 0, None)

    limit = RATE_LIMITS.get(role)
    if limit is None:
        return RateLimitStatus(True, None, 0, None)

    window_start = timezone.now() - timedelta(hours=1)
    used = Message.objects.filter(
        conversation__user=user,
        role=Message.Role.USER,
        created_at__gte=window_start,
    ).count()

    return RateLimitStatus(used < limit, limit, used, max(0, limit - used))
