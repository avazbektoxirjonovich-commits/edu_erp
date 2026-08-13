"""
Error Monitor — Capture
=========================
capture_exception() is the single entry point that turns a Python exception
into a persisted ErrorEvent (grouped) + ErrorOccurrence (detail) row.

Never sends anything to Claude — this module only writes to the database.
Manual AI analysis is a separate, explicitly developer-triggered action
(apps/error_monitor/views.py::ErrorAnalyzeView).
"""
from __future__ import annotations

import logging
import traceback
import uuid

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.error_monitor.fingerprint import (
    compute_fingerprint,
    compute_severity,
    normalize_for_fingerprint,
    sanitize_message,
)

logger = logging.getLogger("apps.error_monitor")


def capture_exception(
    exc: Exception,
    *,
    user=None,
    endpoint: str = '',
    method: str = '',
    page: str = '',
    status_code: int | None = None,
):
    """Persist one occurrence of `exc`, grouped by a stable fingerprint.

    Safe to call from any exception handler — never raises (a failure to
    log an error must never itself crash the request being handled).
    """
    from apps.error_monitor.models import ErrorEvent, ErrorOccurrence

    try:
        error_type = type(exc).__name__
        raw_message = str(exc)
        sanitized = sanitize_message(raw_message)
        normalized = normalize_for_fingerprint(sanitized)
        fingerprint = compute_fingerprint(error_type, endpoint, normalized)
        severity = compute_severity(status_code)
        stack_trace = sanitize_message(traceback.format_exc())[:8000]

        role = getattr(user, 'role', '') or '' if user and getattr(user, 'is_authenticated', False) else ''
        occurrence_user = user if user and getattr(user, 'is_authenticated', False) else None

        with transaction.atomic():
            event, created = ErrorEvent.objects.select_for_update().get_or_create(
                fingerprint=fingerprint,
                defaults=dict(
                    error_type=error_type,
                    message=sanitized,
                    page=page,
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    severity=severity,
                    occurrence_count=0,
                    last_seen=timezone.now(),
                ),
            )
            ErrorEvent.objects.filter(pk=event.pk).update(
                occurrence_count=F('occurrence_count') + 1,
                last_seen=timezone.now(),
            )

            ErrorOccurrence.objects.create(
                error_event=event,
                user=occurrence_user,
                user_role=role,
                request_id=str(uuid.uuid4()),
                page=page,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                sanitized_message=sanitized,
                stack_trace=stack_trace,
            )

        if created:
            from apps.notifications.models import ActivityLog
            from apps.notifications.views import log_activity
            log_activity(
                user if occurrence_user else None, ActivityLog.Action.CREATE, 'ErrorEvent',
                event.pk, f"{error_type} | {endpoint}",
            )

        return event
    except Exception:
        # Logging infrastructure must never break the request it's observing.
        logger.error("capture_exception failed", exc_info=True)
        return None
