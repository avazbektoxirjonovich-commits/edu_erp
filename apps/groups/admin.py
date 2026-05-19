from django.contrib import admin
from .models import Group, LessonSchedule


class LessonScheduleInline(admin.TabularInline):
    model = LessonSchedule
    extra = 1


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display  = ['name', 'teacher', 'status', 'student_count', 'max_students', 'monthly_fee']
    list_filter   = ['status']
    search_fields = ['name']
    inlines       = [LessonScheduleInline]
