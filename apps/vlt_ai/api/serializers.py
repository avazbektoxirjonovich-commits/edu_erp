from rest_framework import serializers

from apps.vlt_ai.models import Conversation, Message


class ChatRequestSerializer(serializers.Serializer):
    message         = serializers.CharField(min_length=1, max_length=2000)
    conversation_id = serializers.UUIDField(required=False, allow_null=True)


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Message
        fields = ("id", "role", "content", "tool_calls", "created_at")


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model  = Conversation
        fields = ("id", "title", "created_at", "updated_at", "messages")
