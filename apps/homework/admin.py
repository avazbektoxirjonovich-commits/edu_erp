from django.contrib import admin
from .models import Assignment, Submission


class SubmissionInline(admin.TabularInline):
    model  = Submission
    extra  = 0
    fields = ['student', 'status', 'score', 'submitted_at']
    readonly_fields = ['submitted_at']


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display   = ['title', 'group', 'teacher', 'due_date', 'status', 'submission_count']
    list_filter    = ['status', 'group', 'teacher']
    search_fields  = ['title', 'description']
    ordering       = ['-created_at']
    inlines        = [SubmissionInline]
    readonly_fields = ['created_at', 'updated_at']

    def submission_count(self, obj):
        return obj.submissions.count()
    submission_count.short_description = "Topshiriqlar"


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display   = ['student', 'assignment', 'status', 'score', 'submitted_at']
    list_filter    = ['status', 'assignment__group']
    search_fields  = ['student__user__full_name', 'assignment__title']
    ordering       = ['-submitted_at']
    readonly_fields = ['submitted_at', 'graded_at']
