"""
Error Monitor — DRF exception handler
========================================
Wraps DRF's default exception_handler:
  - Expected 4xx (validation, permission, not-found, throttling) pass through
    unchanged — those are not "ERP errors", they're normal client outcomes.
  - Any 5xx or genuinely unhandled exception is captured (grouped, logged)
    and converted into ONE safe, generic Uzbek message — never a stack
    trace, DB error, internal path, or credential.
"""
from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.error_monitor.capture import capture_exception

SAFE_ERROR_MESSAGE = (
    "Texnik xatolik yuz berdi.\n"
    "Muammo qayd etildi. Iltimos, birozdan so'ng qayta urinib ko'ring."
)


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    request = context.get('request')
    view = context.get('view')

    endpoint = request.path if request is not None else ''
    method = request.method if request is not None else ''
    page = (request.META.get('HTTP_REFERER', '') if request is not None else '')[:300]
    user = getattr(request, 'user', None) if request is not None else None

    if response is not None:
        # Already a well-formed DRF response. Only 5xx counts as an ERP
        # error worth grouping — 4xx are expected outcomes (bad input,
        # denied permission, not found, rate limited) with their own safe,
        # already-serialized body.
        if response.status_code >= 500:
            capture_exception(
                exc, user=user, endpoint=endpoint, method=method,
                page=page, status_code=response.status_code,
            )
        return response

    # DRF didn't recognize this exception type at all — without this
    # handler it would propagate to Django and could surface a raw
    # traceback (in DEBUG) or an unbranded error page. Capture it and
    # always return the safe generic message instead.
    view_name = view.__class__.__name__ if view is not None else ''
    capture_exception(
        exc, user=user, endpoint=endpoint or view_name, method=method,
        page=page, status_code=500,
    )
    return Response({'error': SAFE_ERROR_MESSAGE}, status=500)
