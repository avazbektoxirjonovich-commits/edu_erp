from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display   = ['student', 'group', 'month', 'year', 'amount',
                      'paid_amount', 'debt_amount', 'status']
    list_filter    = ['status', 'month', 'year', 'group']
    search_fields  = ['student__user__full_name']
    ordering       = ['-year', '-month']
    readonly_fields = ['id', 'debt_amount', 'status', 'created_at', 'updated_at']
