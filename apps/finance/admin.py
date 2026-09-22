from django.contrib import admin

from .models import Asset, Expense, PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    """Faqat ko'rish uchun — chek ERP ichida yoziladi va bekor qilinadi (o'chirilmaydi)."""
    list_display  = ['receipt_number', 'payment', 'amount', 'payment_type', 'received_by',
                     'paid_at', 'is_cancelled']
    list_filter   = ['payment_type', 'is_cancelled']
    search_fields = ['receipt_number', 'payment__student__user__full_name']
    ordering      = ['-paid_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display  = ['name', 'category', 'amount', 'expense_date', 'created_by']
    list_filter   = ['category']
    search_fields = ['name', 'description']
    ordering      = ['-expense_date']


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display  = ['name', 'quantity', 'purchase_price', 'total_value', 'condition']
    list_filter   = ['condition']
    search_fields = ['name', 'category']
    ordering      = ['-created_at']
