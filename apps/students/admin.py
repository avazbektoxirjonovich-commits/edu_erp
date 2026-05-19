from django.contrib import admin
from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display   = ['full_name', 'phone', 'group', 'status',
                      'attendance_percentage', 'total_debt', 'joined_date']
    list_filter    = ['status', 'group']
    search_fields  = ['user__full_name', 'phone']
    ordering       = ['-created_at']
    readonly_fields = ['id', 'joined_date', 'created_at', 'updated_at',
                       'attendance_percentage', 'total_debt']

    fieldsets = (
        ("Asosiy", {'fields': ('id', 'user', 'group', 'status')}),
        ("Kontakt", {'fields': ('phone', 'parent_phone', 'address')}),
        ("Boshqa", {'fields': ('birth_date', 'notes', 'attendance_percentage', 'total_debt')}),
        ("Vaqt", {'fields': ('joined_date', 'created_at', 'updated_at')}),
    )
