from django.contrib import admin

from .models import AILog, Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display  = ("user", "title", "created_at", "updated_at")
    list_filter   = ("created_at",)
    search_fields = ("user__full_name", "user__phone", "title")
    raw_id_fields = ("user",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display  = ("conversation", "role", "created_at")
    list_filter   = ("role", "created_at")
    raw_id_fields = ("conversation",)


@admin.register(AILog)
class AILogAdmin(admin.ModelAdmin):
    list_display  = ("user", "tool_name", "status", "created_at")
    list_filter   = ("status", "tool_name", "created_at")
    search_fields = ("user__full_name", "user__phone", "tool_name")
    readonly_fields = ("user", "tool_name", "args", "status", "result_summary", "created_at")
