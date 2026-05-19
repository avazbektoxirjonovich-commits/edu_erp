from django.contrib import admin
from .models import Teacher

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display  = ['full_name', 'phone', 'subject', 'group_count', 'salary', 'is_active']
    list_filter   = ['is_active', 'subject']
    search_fields = ['user__full_name', 'phone']
