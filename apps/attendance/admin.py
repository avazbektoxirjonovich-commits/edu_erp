from django.contrib import admin
from .models import Attendance

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display  = ['student', 'group', 'date', 'status', 'marked_by']
    list_filter   = ['status', 'date', 'group']
    search_fields = ['student__user__full_name']
    ordering      = ['-date']
