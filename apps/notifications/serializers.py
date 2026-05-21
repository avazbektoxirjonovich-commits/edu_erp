from rest_framework import serializers
from .models import Notification, ActivityLog


class NotificationSerializer(serializers.ModelSerializer):
    channel_display  = serializers.CharField(source='get_channel_display', read_only=True)
    type_display     = serializers.CharField(source='get_notif_type_display', read_only=True)
    sender_id        = serializers.UUIDField(source='sender.id', read_only=True, default=None)
    sender_name      = serializers.CharField(source='sender.full_name', read_only=True, default=None)
    sender_role      = serializers.CharField(source='sender.role', read_only=True, default=None)
    reply_count      = serializers.SerializerMethodField()

    class Meta:
        model  = Notification
        fields = [
            'id', 'channel', 'channel_display', 'notif_type', 'type_display',
            'title', 'message', 'status', 'is_read', 'sent_at', 'created_at',
            'sender_id', 'sender_name', 'sender_role', 'reply_count', 'parent',
        ]
        read_only_fields = fields

    def get_reply_count(self, obj):
        return obj.replies.count()


class SupportMessageSerializer(serializers.Serializer):
    message = serializers.CharField(min_length=1)


class SupportReplySerializer(serializers.Serializer):
    message = serializers.CharField(min_length=1)


class ActivityLogSerializer(serializers.ModelSerializer):
    user_name    = serializers.CharField(source='user.full_name', read_only=True, default='Nomalum')
    user_role    = serializers.CharField(source='user.role', read_only=True, default=None)
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model  = ActivityLog
        fields = [
            'id', 'user_name', 'user_role', 'action', 'action_display',
            'model_name', 'object_repr', 'changes', 'ip_address', 'created_at',
        ]
        read_only_fields = fields