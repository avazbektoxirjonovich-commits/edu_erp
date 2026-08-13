from django.contrib import admin

from .models import ErrorEvent, ErrorOccurrence


class ErrorOccurrenceInline(admin.TabularInline):
    model = ErrorOccurrence
    extra = 0
    readonly_fields = ['user', 'user_role', 'endpoint', 'method', 'status_code', 'created_at']
    fields = readonly_fields
    can_delete = False
    max_num = 20
    ordering = ['-created_at']


@admin.register(ErrorEvent)
class ErrorEventAdmin(admin.ModelAdmin):
    list_display  = ['error_type', 'endpoint', 'severity', 'status', 'occurrence_count', 'last_seen']
    list_filter   = ['severity', 'status']
    search_fields = ['error_type', 'message', 'endpoint', 'fingerprint']
    readonly_fields = ['fingerprint', 'first_seen', 'last_seen', 'occurrence_count',
                        'ai_analysis', 'ai_analyzed_at', 'ai_analyzed_by']
    inlines = [ErrorOccurrenceInline]
    ordering = ['-last_seen']


@admin.register(ErrorOccurrence)
class ErrorOccurrenceAdmin(admin.ModelAdmin):
    list_display  = ['error_event', 'user', 'endpoint', 'status_code', 'created_at']
    list_filter   = ['status_code', 'created_at']
    search_fields = ['user__full_name', 'endpoint', 'sanitized_message']
    readonly_fields = [f.name for f in ErrorOccurrence._meta.fields]
