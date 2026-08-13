from rest_framework import serializers

from apps.students.models import Student

from .models import KumushTransaction, PurchaseRequest, StoreItem


class StoreItemSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default=None)
    sold_count       = serializers.SerializerMethodField()
    is_available      = serializers.ReadOnlyField()

    class Meta:
        model  = StoreItem
        fields = [
            'id', 'name', 'image', 'description', 'price', 'stock', 'is_active',
            'is_available', 'sold_count', 'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_sold_count(self, obj):
        return obj.purchase_requests.filter(status=PurchaseRequest.Status.APPROVED).count()


class PurchaseRequestSerializer(serializers.ModelSerializer):
    student_name     = serializers.CharField(source='student.user.full_name', read_only=True)
    item_name        = serializers.CharField(source='item.name', read_only=True)
    item_image       = serializers.ImageField(source='item.image', read_only=True)
    status_display   = serializers.CharField(source='get_status_display', read_only=True)
    decided_by_name  = serializers.CharField(source='decided_by.full_name', read_only=True, default=None)
    refunded_by_name = serializers.CharField(source='refunded_by.full_name', read_only=True, default=None)

    class Meta:
        model  = PurchaseRequest
        fields = [
            'id', 'student', 'student_name', 'item', 'item_name', 'item_image',
            'price_at_request', 'status', 'status_display', 'requested_at',
            'decided_at', 'decided_by', 'decided_by_name', 'rejection_reason',
            'cancelled_at', 'refunded_at', 'refunded_by', 'refunded_by_name', 'refund_reason',
        ]
        read_only_fields = [
            'id', 'student', 'price_at_request', 'status', 'requested_at',
            'decided_at', 'decided_by', 'rejection_reason',
            'cancelled_at', 'refunded_at', 'refunded_by', 'refund_reason',
        ]


class KumushTransactionSerializer(serializers.ModelSerializer):
    student_name    = serializers.CharField(source='student.user.full_name', read_only=True)
    type_display     = serializers.CharField(source='get_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default=None)

    class Meta:
        model  = KumushTransaction
        fields = ['id', 'student', 'student_name', 'amount', 'type', 'type_display',
                  'reason', 'purchase', 'created_by', 'created_by_name',
                  'balance_before', 'balance_after', 'source_type', 'source_id', 'created_at']
        read_only_fields = fields


class ManualKumushAdjustmentSerializer(serializers.Serializer):
    """Kirish uchun — ADMIN/DEVELOPER qo'lda Kumush tuzatishi.
    amount musbat = qo'shish, manfiy = ayirish. student.coins to'g'ridan-to'g'ri
    tahrirlanmaydi — faqat shu orqali, ledger yozuvi bilan birga."""
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    amount  = serializers.IntegerField()
    reason  = serializers.CharField(max_length=200, allow_blank=False, trim_whitespace=True)

    def validate_amount(self, value):
        if value == 0:
            raise serializers.ValidationError("Miqdor 0 bo'lishi mumkin emas.")
        return value

    def validate_reason(self, value):
        if not value.strip():
            raise serializers.ValidationError("Sabab ko'rsatilishi shart.")
        return value.strip()
