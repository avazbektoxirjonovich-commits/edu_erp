from django.contrib import admin

from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    """Faqat ko'rish uchun — arizalar ERP paneli orqali boshqariladi."""
    list_display  = ['full_name', 'phone', 'age', 'direction', 'status', 'created_at']
    list_filter   = ['status', 'created_at']
    search_fields = ['full_name', 'phone', 'direction']
    readonly_fields = [f.name for f in Application._meta.fields]

    def has_add_permission(self, request):
        return False
