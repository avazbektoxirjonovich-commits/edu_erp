from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ['recipient', 'channel', 'notif_type', 'title', 'status', 'is_read', 'created_at']
    list_filter   = ['channel', 'status', 'is_read', 'notif_type']
    search_fields = ['recipient__full_name', 'title']
    ordering      = ['-created_at']
