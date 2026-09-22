from decimal import Decimal

from rest_framework import serializers

from apps.payments.serializers import PaymentSerializer
from apps.payments.services import record_payment
from apps.students.models import Student

from .models import Asset, Expense, PaymentTransaction


class ExpenseSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    created_by_name   = serializers.CharField(source='created_by.full_name', read_only=True, default=None)

    class Meta:
        model  = Expense
        fields = [
            'id', 'name', 'category', 'category_display', 'amount', 'expense_date',
            'description', 'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class AssetSerializer(serializers.ModelSerializer):
    condition_display = serializers.CharField(source='get_condition_display', read_only=True)
    created_by_name    = serializers.CharField(source='created_by.full_name', read_only=True, default=None)
    total_value         = serializers.ReadOnlyField()

    class Meta:
        model  = Asset
        fields = [
            'id', 'name', 'category', 'quantity', 'purchase_date', 'purchase_price',
            'total_value', 'condition', 'condition_display', 'notes',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class PaymentTransactionSerializer(serializers.ModelSerializer):
    received_by_name     = serializers.CharField(source='received_by.full_name', read_only=True, default=None)
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    student_name          = serializers.CharField(source='payment.student.user.full_name', read_only=True)
    group_name            = serializers.CharField(source='payment.group.name', read_only=True, default=None)
    receipt_url            = serializers.SerializerMethodField()
    cancelled_by_name      = serializers.CharField(source='cancelled_by.full_name', read_only=True, default=None)

    class Meta:
        model  = PaymentTransaction
        fields = [
            'id', 'payment', 'student_name', 'group_name', 'amount', 'payment_type',
            'payment_type_display', 'receipt_number', 'note', 'received_by', 'received_by_name',
            'debt_after', 'paid_at', 'created_at', 'receipt_url',
            'is_cancelled', 'cancelled_at', 'cancelled_by_name', 'cancel_reason',
        ]
        read_only_fields = fields

    def get_receipt_url(self, obj):
        return f'/finance/receipt/{obj.id}/'


class DebtorPaymentSerializer(PaymentSerializer):
    """Qarzdorlar ro'yxati uchun — PaymentSerializer + telefon + umumiy (barcha oylar) qarz."""
    phone      = serializers.CharField(source='student.phone', read_only=True)
    total_debt = serializers.SerializerMethodField()

    class Meta(PaymentSerializer.Meta):
        fields = PaymentSerializer.Meta.fields + ['phone', 'total_debt']

    def get_total_debt(self, obj):
        return float(obj.student.total_debt)


class RecordPaymentSerializer(serializers.Serializer):
    """
    Moliyachi tomonidan to'lov qabul qilish.
    Shu student/guruh/oy/yil uchun Payment (hisob) mavjud bo'lmasa — avtomatik
    yaratiladi (guruh oylik to'lovi asosida), so'ng bitta PaymentTransaction
    (chek) yoziladi. Bir oyga bir nechta marta chaqirilsa — har biri alohida
    chek, Payment.paid_amount esa avtomatik yig'indiga tenglashadi.
    """
    student      = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    month        = serializers.IntegerField(min_value=1, max_value=12)
    year         = serializers.IntegerField(min_value=2000, max_value=2100)
    amount       = serializers.DecimalField(max_digits=10, decimal_places=0, min_value=Decimal('1'))
    payment_type = serializers.ChoiceField(
        choices=[c for c in PaymentTransaction.PaymentType.choices
                 if c[0] != PaymentTransaction.PaymentType.UNKNOWN],
        default=PaymentTransaction.PaymentType.CASH,
    )
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')

    def create(self, validated_data):
        return record_payment(
            student=validated_data['student'],
            month=validated_data['month'],
            year=validated_data['year'],
            amount=validated_data['amount'],
            payment_type=validated_data['payment_type'],
            note=validated_data.get('note', ''),
            user=self.context['request'].user,
        )


class CancelTransactionSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200)
