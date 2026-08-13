"""
VLT AI — API Views
===================
POST /api/v1/vlt-ai/chat/            → streaming SSE chat
GET  /api/v1/vlt-ai/conversations/   → current user's conversation list
GET  /api/v1/vlt-ai/conversations/<id>/ → single conversation with messages
"""
from __future__ import annotations

import json
import logging

from django.http import StreamingHttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import ActivityLog
from apps.notifications.views import log_activity
from apps.vlt_ai.api.serializers import (
    ChatRequestSerializer,
    ConversationSerializer,
)
from apps.vlt_ai.models import Conversation
from apps.vlt_ai.rate_limit import RATE_LIMIT_MESSAGE, check_ai_rate_limit
from apps.vlt_ai.services.chat_service import process_chat

logger = logging.getLogger("apps.vlt_ai.api.views")


class IsDeveloperRole(IsAuthenticated):
    """Global AI history is a Developer Panel feature — developer role or
    superuser only, not admin. Mirrors apps.error_monitor.permissions
    (kept local here rather than cross-imported, matching this codebase's
    per-app permissions.py convention)."""
    message = "Bu bo'lim faqat dasturchi uchun"

    def has_permission(self, request, view):
        u = request.user
        return bool(
            u and u.is_authenticated and
            (getattr(u, 'is_developer', False) or u.is_superuser)
        )


class ChatView(APIView):
    """Streaming SSE chat endpoint.

    POST body:
      { "message": "...", "conversation_id": "<uuid or null>" }

    Response: text/event-stream
      data: {"type": "conversation_id", "id": "..."}
      data: {"type": "text", "text": "..."}
      ...
      data: [DONE]
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Rate limit is checked BEFORE any validation/LLM work — a rejected
        # request must never reach the Anthropic API. Backend-enforced only;
        # the frontend counter (if any) is never trusted.
        limit_status = check_ai_rate_limit(request.user)
        if not limit_status.allowed:
            log_activity(
                request.user, ActivityLog.Action.RATE_LIMITED, 'VltAiChat',
                object_repr=f"limit={limit_status.limit}", request=request,
            )
            return Response(
                {"error": RATE_LIMIT_MESSAGE},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_message: str = serializer.validated_data["message"]
        conversation_id = serializer.validated_data.get("conversation_id")

        if conversation_id:
            try:
                conversation = Conversation.objects.get(
                    pk=conversation_id, user=request.user
                )
            except Conversation.DoesNotExist:
                return Response(
                    {"error": "Suhbat topilmadi"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            conversation = Conversation.objects.create(
                user=request.user,
                title=user_message[:80],
            )

        def event_stream():
            # First event announces the conversation id so the client can link replies
            yield (
                f"data: {json.dumps({'type': 'conversation_id', 'id': str(conversation.id)})}\n\n"
            )
            yield from process_chat(request.user, conversation, user_message)

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream; charset=utf-8",
        )
        response["Cache-Control"]    = "no-cache"
        response["X-Accel-Buffering"] = "no"
        response["Access-Control-Allow-Origin"] = "*"
        return response


class ConversationListView(APIView):
    """List the authenticated user's conversations (no messages, newest first)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = (
            Conversation.objects.filter(user=request.user)
            .order_by("-updated_at")[:50]
        )
        serializer = ConversationSerializer(
            conversations, many=True, context={"request": request}
        )
        # Exclude messages from list view for performance
        data = [
            {
                "id": c["id"],
                "title": c["title"],
                "created_at": c["created_at"],
                "updated_at": c["updated_at"],
            }
            for c in serializer.data
        ]
        return Response(data)


class ConversationDetailView(APIView):
    """Retrieve a single conversation with all messages."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            conversation = Conversation.objects.get(pk=pk, user=request.user)
        except Conversation.DoesNotExist:
            return Response(
                {"error": "Suhbat topilmadi"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ConversationSerializer(
            conversation, context={"request": request}
        )
        return Response(serializer.data)


class AdminConversationListView(generics.ListAPIView):
    """GET /api/v1/vlt-ai/admin/conversations/ — developer only: every user's
    conversations (metadata only, no messages). Ordinary users (including
    admin) cannot reach this view at all — IsDeveloperRole is checked
    before any queryset runs. Filter by ?user=<uuid>.
    """

    permission_classes  = [IsDeveloperRole]
    filter_backends     = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields    = ["user"]
    ordering            = ["-updated_at"]

    def get_queryset(self):
        return Conversation.objects.select_related("user").order_by("-updated_at")

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())[:200]
        data = [
            {
                "id": c.id,
                "user": c.user_id,
                "user_name": getattr(c.user, "full_name", None),
                "title": c.title,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            }
            for c in qs
        ]
        return Response(data)


class AdminConversationDetailView(APIView):
    """GET /api/v1/vlt-ai/admin/conversations/<id>/ — developer only: any
    single conversation with full messages, regardless of owner."""

    permission_classes = [IsDeveloperRole]

    def get(self, request, pk):
        try:
            conversation = Conversation.objects.select_related("user").get(pk=pk)
        except Conversation.DoesNotExist:
            return Response(
                {"error": "Suhbat topilmadi"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ConversationSerializer(
            conversation, context={"request": request}
        )
        data = serializer.data
        data["user"] = conversation.user_id
        data["user_name"] = getattr(conversation.user, "full_name", None)
        return Response(data)
