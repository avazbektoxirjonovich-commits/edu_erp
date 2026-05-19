from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    type_display    = serializers.CharField(source='get_notif_type_display', read_only=True)

    class Meta:
        model  = Notification
        fields = ['id', 'channel', 'channel_display', 'notif_type', 'type_display',
                  'title', 'message', 'status', 'is_read', 'sent_at', 'created_at']
        read_only_fields = fields
