from django.contrib import admin
from .models import FaceProfile, FaceAuthLog


@admin.register(FaceProfile)
class FaceProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'status', 'enrolled_at', 'consent_given')
    list_filter   = ('status', 'consent_given')
    search_fields = ('user__full_name', 'user__phone')
    readonly_fields = ('enrolled_at', 'consent_at', 'updated_at')

    def has_change_permission(self, request, obj=None):
        # Prevent editing the encrypted embedding through admin
        return request.user.is_superuser


@admin.register(FaceAuthLog)
class FaceAuthLogAdmin(admin.ModelAdmin):
    list_display  = ('user', 'result', 'challenge', 'liveness_passed', 'identity_matched', 'timestamp', 'ip_address')
    list_filter   = ('result', 'liveness_passed', 'identity_matched', 'challenge')
    search_fields = ('user__full_name', 'user__phone', 'ip_address')
    readonly_fields = ('user', 'timestamp', 'liveness_passed', 'identity_matched',
                       'result', 'challenge', 'failure_reason', 'ip_address')
    ordering      = ('-timestamp',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
