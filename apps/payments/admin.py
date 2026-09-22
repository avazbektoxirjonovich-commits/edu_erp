from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Faqat ko'rish uchun. Pul — faqat chek orqali, narx/chegirma — ERP ichidan
    (audit jurnaliga yoziladi). Admin panel bu qoidalarni chetlab o'tmasligi kerak."""
    list_display   = ['student', 'group', 'month', 'year', 'amount',
                      'discount', 'paid_amount', 'debt_amount', 'status']
    list_filter    = ['status', 'month', 'year', 'group']
    search_fields  = ['student__user__full_name']
    ordering       = ['-year', '-month']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
