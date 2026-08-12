from django.contrib import admin

from .models import Asset, Expense, PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display  = ['receipt_number', 'payment', 'amount', 'payment_type', 'received_by', 'paid_at']
    list_filter   = ['payment_type']
    search_fields = ['receipt_number', 'payment__student__user__full_name']
    ordering      = ['-paid_at']


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
