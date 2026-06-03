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
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.vlt_ai.api.serializers import (
    ChatRequestSerializer,
    ConversationSerializer,
)
from apps.vlt_ai.models import Conversation
from apps.vlt_ai.services.chat_service import process_chat

logger = logging.getLogger("apps.vlt_ai.api.views")


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
