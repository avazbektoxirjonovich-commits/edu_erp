"""
Error Monitor — Views
=======================
All endpoints are developer-only (IsDeveloperRole).

Errors are NEVER sent to Claude automatically anywhere in this file except
ErrorAnalyzeView, which only runs when a developer explicitly clicks
"AI ORQALI TAHLIL QILISH" and POSTs to it.
"""
from __future__ import annotations

import json
import logging

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import ActivityLog
from apps.notifications.views import log_activity

from .models import ErrorEvent
from .permissions import IsDeveloperRole
from .serializers import (
    ErrorEventDetailSerializer,
    ErrorEventListSerializer,
    ErrorStatusUpdateSerializer,
)

logger = logging.getLogger("apps.error_monitor.views")


class ErrorEventListView(generics.ListAPIView):
    """GET /api/v1/error-monitor/errors/?status=&severity=&search="""
    serializer_class   = ErrorEventListSerializer
    permission_classes = [IsDeveloperRole]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = ['status', 'severity']
    search_fields       = ['error_type', 'message', 'endpoint']
    ordering            = ['-last_seen']

    def get_queryset(self):
        return ErrorEvent.objects.all()


class ErrorEventDetailView(generics.RetrieveAPIView):
    """GET /api/v1/error-monitor/errors/<id>/ — full technical detail
    (stack traces included) — developer only."""
    queryset            = ErrorEvent.objects.all()
    serializer_class     = ErrorEventDetailSerializer
    permission_classes   = [IsDeveloperRole]


class ErrorEventStatusView(APIView):
    """PATCH /api/v1/error-monitor/errors/<id>/status/ — {"status": "resolved"}"""
    permission_classes = [IsDeveloperRole]

    def patch(self, request, pk):
        try:
            event = ErrorEvent.objects.get(pk=pk)
        except ErrorEvent.DoesNotExist:
            return Response({'error': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)

        old_status = event.status
        serializer = ErrorStatusUpdateSerializer(event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        log_activity(
            request.user, ActivityLog.Action.UPDATE, 'ErrorEvent', event.pk,
            f"{event.error_type} | {event.endpoint}",
            changes={'status': {'old': old_status, 'new': event.status}},
            request=request,
        )
        return Response(ErrorEventDetailSerializer(event).data)


class ErrorStatsView(APIView):
    """GET /api/v1/error-monitor/stats/ — Developer Panel summary cards."""
    permission_classes = [IsDeveloperRole]

    def get(self, request):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timezone.timedelta(days=today_start.weekday())

        qs = ErrorEvent.objects.all()
        errors_today = qs.filter(last_seen__gte=today_start).count()
        errors_this_week = qs.filter(last_seen__gte=week_start).count()

        most_frequent = list(
            qs.order_by('-occurrence_count')[:5].values(
                'id', 'error_type', 'endpoint', 'occurrence_count', 'severity',
            )
        )
        affected_users_total = (
            ErrorEvent.objects.values('occurrences__user')
            .exclude(occurrences__user__isnull=True)
            .distinct()
            .count()
        )

        return Response({
            'total_errors':    qs.count(),
            'errors_today':    errors_today,
            'errors_this_week': errors_this_week,
            'open_errors':     qs.filter(status=ErrorEvent.Status.OPEN).count(),
            'resolved_errors': qs.filter(status=ErrorEvent.Status.RESOLVED).count(),
            'critical_errors': qs.filter(severity=ErrorEvent.Severity.CRITICAL).count(),
            'most_frequent':   most_frequent,
            'affected_users':  affected_users_total,
        })


ANALYSIS_SYSTEM_PROMPT = (
    "Siz tajribali Senior Software Engineer va Security Engineersiz. "
    "Sizga bitta aniq ERP xatoligi haqida ma'lumot beriladi. Faqat shu xatolikni tahlil qiling. "
    "Hech qanday fayl o'zgartirmang, kod ishga tushirmang, hech narsa deploy qilmang — "
    "faqat tahlil va tavsiyalar bering. "
    "Javobni FAQAT quyidagi JSON formatida qaytaring, boshqa hech qanday matn qo'shmang:\n"
    '{"probable_cause": "...", "affected_module": "...", "severity": "...", '
    '"reproduction_steps": "...", "recommended_fix": "...", '
    '"possible_side_effects": "...", "testing_recommendations": "..."}'
)


class ErrorAnalyzeView(APIView):
    """POST /api/v1/error-monitor/errors/<id>/analyze/

    Manual, developer-triggered AI analysis — the ONLY place in this app
    that calls Claude. Sends only this one error's minimal context (never
    other users' data, never the full occurrence list).
    """
    permission_classes = [IsDeveloperRole]

    def post(self, request, pk):
        try:
            event = ErrorEvent.objects.get(pk=pk)
        except ErrorEvent.DoesNotExist:
            return Response({'error': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)

        sample = event.occurrences.first()
        stack_trace = (sample.stack_trace if sample else '')[:4000]

        prompt = (
            f"Xatolik turi: {event.error_type}\n"
            f"Endpoint: {event.endpoint} ({event.method})\n"
            f"HTTP status: {event.status_code}\n"
            f"Jiddiylik: {event.get_severity_display()}\n"
            f"Xabar: {event.message}\n"
            f"Takrorlanish soni: {event.occurrence_count}\n"
            f"Birinchi marta ko'ringan: {event.first_seen}\n"
            f"Oxirgi marta ko'ringan: {event.last_seen}\n"
            f"Stack trace:\n{stack_trace}"
        )

        from apps.vlt_ai.services.llm_client import llm_client

        try:
            raw_text = llm_client.simple_complete(prompt, system=ANALYSIS_SYSTEM_PROMPT, max_tokens=1500)
        except Exception as exc:
            logger.error("Error analysis LLM call failed: %s", exc, exc_info=True)
            return Response(
                {'error': "AI tahlili amalga oshmadi. Iltimos, qayta urinib ko'ring."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        try:
            cleaned = raw_text.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.strip('`').removeprefix('json').strip()
            analysis = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            analysis = {'raw': raw_text}

        event.ai_analysis = analysis
        event.ai_analyzed_at = timezone.now()
        event.ai_analyzed_by = request.user
        event.save(update_fields=['ai_analysis', 'ai_analyzed_at', 'ai_analyzed_by'])

        log_activity(
            request.user, ActivityLog.Action.CREATE, 'ErrorAiAnalysis', event.pk,
            f"{event.error_type} | {event.endpoint}", request=request,
        )

        return Response(ErrorEventDetailSerializer(event).data)
