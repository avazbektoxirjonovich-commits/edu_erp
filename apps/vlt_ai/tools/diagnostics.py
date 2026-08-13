"""
VLT AI Tools — Developer diagnostics
=======================================
Tools: get_error_statistics, get_recent_errors

Developer-only (permission "errors.view", granted only via the developer
role bypass in apps.vlt_ai.permissions.user_can). Read-only — these tools
never trigger AI error analysis themselves; that stays a separate, manual,
developer-clicked action (apps/error_monitor/views.py::ErrorAnalyzeView).
"""
from __future__ import annotations

import logging

from apps.vlt_ai.tools.registry import ai_tool
from apps.vlt_ai.tools.schemas import ERROR_STATISTICS_SCHEMA, RECENT_ERRORS_SCHEMA

logger = logging.getLogger("apps.vlt_ai.tools.diagnostics")


@ai_tool(
    name="get_error_statistics",
    required_permission="errors.view",
    description=ERROR_STATISTICS_SCHEMA["description"],
    schema=ERROR_STATISTICS_SCHEMA,
)
def get_error_statistics(user) -> dict:
    """Error monitoring summary (developer only)."""
    from apps.error_monitor.models import ErrorEvent

    qs = ErrorEvent.objects.all()
    return {
        "total_errors": qs.count(),
        "open_errors": qs.filter(status=ErrorEvent.Status.OPEN).count(),
        "resolved_errors": qs.filter(status=ErrorEvent.Status.RESOLVED).count(),
        "critical_errors": qs.filter(severity=ErrorEvent.Severity.CRITICAL).count(),
    }


@ai_tool(
    name="get_recent_errors",
    required_permission="errors.view",
    description=RECENT_ERRORS_SCHEMA["description"],
    schema=RECENT_ERRORS_SCHEMA,
)
def get_recent_errors(user, limit: int = 10) -> dict:
    """Most recent error groups (developer only)."""
    from apps.error_monitor.models import ErrorEvent

    rows = list(
        ErrorEvent.objects.order_by("-last_seen")[:limit].values(
            "id", "error_type", "endpoint", "severity", "status",
            "occurrence_count", "last_seen",
        )
    )
    return {
        "count": len(rows),
        "errors": [
            {
                "id": str(r["id"]),
                "error_type": r["error_type"],
                "endpoint": r["endpoint"],
                "severity": r["severity"],
                "status": r["status"],
                "occurrence_count": r["occurrence_count"],
                "last_seen": str(r["last_seen"])[:16],
            }
            for r in rows
        ],
    }
