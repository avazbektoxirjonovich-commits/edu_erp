from django.contrib import admin

from .models import KumushTransaction, PurchaseRequest, StoreItem


@admin.register(StoreItem)
class StoreItemAdmin(admin.ModelAdmin):
    list_display  = ['name', 'price', 'stock', 'is_active', 'created_by', 'created_at']
    list_filter   = ['is_active']
    search_fields = ['name', 'description']
    ordering      = ['-created_at']


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display  = ['student', 'item', 'price_at_request', 'status', 'requested_at', 'decided_by']
    list_filter   = ['status']
    search_fields = ['student__user__full_name', 'item__name']
    ordering      = ['-requested_at']


@admin.register(KumushTransaction)
class KumushTransactionAdmin(admin.ModelAdmin):
    list_display  = ['student', 'amount', 'type', 'reason', 'created_at']
    list_filter   = ['type']
    search_fields = ['student__user__full_name', 'reason']
    ordering      = ['-created_at']
