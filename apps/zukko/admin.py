from django.contrib import admin
from django.utils.html import format_html

from .models import (
    AntiCheatEvent,
    BugFindChallenge,
    ChallengeCategory,
    ChallengeSession,
    ChallengeSubmission,
    CodingChallenge,
    StudentProgress,
)


@admin.register(ChallengeCategory)
class ChallengeCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_by', 'created_at']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(BugFindChallenge)
class BugFindChallengeAdmin(admin.ModelAdmin):
    list_display = ['title', 'difficulty', 'bug_type', 'programming_language', 'points', 'is_active', 'created_at']
    list_filter = ['difficulty', 'bug_type', 'is_active', 'category']
    search_fields = ['title', 'description']
    readonly_fields = ['created_by', 'created_at', 'updated_at']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CodingChallenge)
class CodingChallengeAdmin(admin.ModelAdmin):
    list_display = ['title', 'difficulty', 'programming_language', 'points', 'is_active', 'created_at']
    list_filter = ['difficulty', 'is_active', 'category']
    search_fields = ['title', 'description']
    readonly_fields = ['created_by', 'created_at', 'updated_at']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ChallengeSession)
class ChallengeSessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'group', 'session_type', 'status', 'share_link', 'created_at']
    list_filter = ['session_type', 'status', 'group']
    list_editable = ['status']
    search_fields = ['title', 'share_link']
    filter_horizontal = ['bugfind_pool', 'coding_pool']
    readonly_fields = ['share_link', 'created_by', 'created_at']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class SuspicionLevelFilter(admin.SimpleListFilter):
    """Shubha darajasi bo'yicha tezkor filtr — yashil (toza) / sariq / qizil (yuqori shubha)"""
    title = "Shubha darajasi"
    parameter_name = 'suspicion_level'

    def lookups(self, request, model_admin):
        return [
            ('low', "🟢 Past (< 0.3)"),
            ('medium', "🟡 O'rta (0.3 — 0.7)"),
            ('high', "🔴 Yuqori (> 0.7)"),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'low':
            return queryset.filter(suspicion_score__lt=0.3)
        if self.value() == 'medium':
            return queryset.filter(suspicion_score__gte=0.3, suspicion_score__lte=0.7)
        if self.value() == 'high':
            return queryset.filter(suspicion_score__gt=0.7)
        return queryset


class AntiCheatEventInline(admin.TabularInline):
    """Bitta javobga (va shu orqali sessiyaga) bog'langan anti-cheat hodisalarni guruhlab ko'rsatadi"""
    model = AntiCheatEvent
    fk_name = 'submission'
    extra = 0
    can_delete = False
    fields = ['event_type', 'severity', 'details', 'timestamp']
    readonly_fields = ['event_type', 'severity', 'details', 'timestamp']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ChallengeSubmission)
class ChallengeSubmissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'submission_type', 'status', 'points_earned', 'colored_suspicion', 'started_at']
    list_filter = ['submission_type', 'status', 'session', SuspicionLevelFilter]
    search_fields = ['user__full_name', 'user__phone']
    readonly_fields = [f.name for f in ChallengeSubmission._meta.fields]
    date_hierarchy = 'started_at'
    inlines = [AntiCheatEventInline]

    def has_add_permission(self, request):
        return False

    def colored_suspicion(self, obj):
        color = '#16a34a' if obj.suspicion_score < 0.3 else '#d97706' if obj.suspicion_score <= 0.7 else '#dc2626'
        return format_html('<b style="color: {}">{}</b>', color, obj.suspicion_score)
    colored_suspicion.short_description = "Shubha darajasi"
    colored_suspicion.admin_order_field = 'suspicion_score'


@admin.register(AntiCheatEvent)
class AntiCheatEventAdmin(admin.ModelAdmin):
    list_display = ['user', 'event_type', 'severity', 'submission', 'session_of_submission', 'timestamp']
    list_filter = ['event_type']
    search_fields = ['user__full_name', 'user__phone']
    readonly_fields = ['id', 'timestamp']

    def session_of_submission(self, obj):
        return obj.submission.session if obj.submission else None
    session_of_submission.short_description = "Sessiya"


@admin.register(StudentProgress)
class StudentProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'category', 'mastery_percentage', 'total_attempts', 'total_xp', 'last_activity']
    list_filter = ['category']
    search_fields = ['user__full_name', 'user__phone']
    readonly_fields = ['last_activity', 'created_at']
