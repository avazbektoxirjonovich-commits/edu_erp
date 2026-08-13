from rest_framework import serializers

from .models import ErrorEvent, ErrorOccurrence


class ErrorOccurrenceSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True, default=None)

    class Meta:
        model = ErrorOccurrence
        fields = [
            'id', 'user', 'user_name', 'user_role', 'request_id', 'page',
            'endpoint', 'method', 'status_code', 'sanitized_message',
            'stack_trace', 'created_at',
        ]
        read_only_fields = fields


class ErrorEventListSerializer(serializers.ModelSerializer):
    status_display   = serializers.CharField(source='get_status_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    affected_users    = serializers.SerializerMethodField()
    last_role          = serializers.SerializerMethodField()
    last_user          = serializers.SerializerMethodField()

    class Meta:
        model = ErrorEvent
        fields = [
            'id', 'fingerprint', 'error_type', 'message', 'page', 'endpoint', 'method',
            'status_code', 'severity', 'severity_display', 'status', 'status_display',
            'occurrence_count', 'affected_users', 'last_role', 'last_user',
            'first_seen', 'last_seen',
        ]
        read_only_fields = fields

    def get_affected_users(self, obj):
        return obj.occurrences.exclude(user__isnull=True).values('user').distinct().count()

    def get_last_role(self, obj):
        last = obj.occurrences.first()
        return last.user_role if last else ''

    def get_last_user(self, obj):
        last = obj.occurrences.select_related('user').first()
        return getattr(last.user, 'full_name', None) if last and last.user else None


class ErrorEventDetailSerializer(ErrorEventListSerializer):
    recent_occurrences = serializers.SerializerMethodField()
    ai_analyzed_by_name = serializers.CharField(source='ai_analyzed_by.full_name', read_only=True, default=None)

    class Meta(ErrorEventListSerializer.Meta):
        fields = ErrorEventListSerializer.Meta.fields + [
            'recent_occurrences', 'ai_analysis', 'ai_analyzed_at', 'ai_analyzed_by_name',
        ]
        read_only_fields = fields

    def get_recent_occurrences(self, obj):
        return ErrorOccurrenceSerializer(obj.occurrences.all()[:20], many=True).data


class ErrorStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ErrorEvent
        fields = ['status']
