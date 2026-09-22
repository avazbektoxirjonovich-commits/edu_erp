from decimal import Decimal

from rest_framework import serializers

from .models import Payment
from .services import get_or_create_invoice


class PaymentSerializer(serializers.ModelSerializer):
    student_name     = serializers.CharField(source='student.user.full_name', read_only=True)
    group_name       = serializers.CharField(source='group.name', read_only=True, allow_null=True)
    status_display   = serializers.CharField(source='get_status_display', read_only=True)
    is_overdue       = serializers.BooleanField(read_only=True)
    effective_status = serializers.CharField(read_only=True)
    due_date         = serializers.DateField(read_only=True)

    class Meta:
        model  = Payment
        fields = [
            'id', 'student', 'student_name', 'group', 'group_name',
            'month', 'year', 'amount', 'discount', 'paid_amount', 'debt_amount',
            'status', 'status_display', 'is_overdue', 'effective_status', 'due_date',
            'payment_date', 'note', 'received_by', 'created_at'
        ]
        read_only_fields = ['id', 'paid_amount', 'debt_amount', 'status', 'created_at']


PAID_AMOUNT_READ_ONLY = (
    "To'langan summani qo'lda o'zgartirib bo'lmaydi — to'lov faqat chek orqali "
    "qabul qilinadi (/api/v1/finance/transactions/record/)."
)


class PaymentCreateSerializer(serializers.ModelSerializer):
    """Oylik HISOB ochish (pul qabul qilish emas). Shu oy uchun hisob bo'lsa —
    mavjudi qaytariladi. Summa ko'rsatilmasa — o'quvchi narxi (shaxsiy yoki guruh)."""
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=0, required=False, min_value=Decimal('0')
    )

    class Meta:
        model  = Payment
        fields = ['id', 'student', 'month', 'year', 'amount', 'note']
        read_only_fields = ['id']

    def validate(self, data):
        if self.initial_data.get('paid_amount') not in (None, '', 0, '0'):
            raise serializers.ValidationError({'paid_amount': [PAID_AMOUNT_READ_ONLY]})
        if not (1 <= data['month'] <= 12):
            raise serializers.ValidationError({'month': ["Oy 1 dan 12 gacha bo'lishi kerak."]})
        return data

    def create(self, validated_data):
        invoice, created = get_or_create_invoice(
            validated_data['student'], validated_data['month'], validated_data['year'],
        )
        self.was_created = created
        if created and ('amount' in validated_data or validated_data.get('note')):
            if 'amount' in validated_data:
                invoice.amount = validated_data['amount']
            invoice.note = validated_data.get('note', '')
            invoice.save()
        return invoice


class PaymentUpdateSerializer(serializers.ModelSerializer):
    """Hisobni tahrirlash: izoh — moliyachi/admin; narx va chegirma — faqat admin.
    To'langan summa bu yerda o'zgarmaydi (faqat chek orqali)."""
    ADMIN_ONLY = ('amount', 'discount')

    amount   = serializers.DecimalField(max_digits=10, decimal_places=0, min_value=Decimal('0'), required=False)
    discount = serializers.DecimalField(max_digits=10, decimal_places=0, min_value=Decimal('0'), required=False)

    class Meta:
        model  = Payment
        fields = ['amount', 'discount', 'note']

    def validate(self, data):
        if 'paid_amount' in self.initial_data:
            raise serializers.ValidationError({'paid_amount': [PAID_AMOUNT_READ_ONLY]})
        user = self.context['request'].user
        if any(f in data for f in self.ADMIN_ONLY) and not (user.is_admin or user.is_developer):
            raise serializers.ValidationError(
                {'detail': "Narx va chegirmani faqat administrator o'zgartira oladi."}
            )
        amount   = data.get('amount', self.instance.amount)
        discount = data.get('discount', self.instance.discount)
        if discount > amount:
            raise serializers.ValidationError({'discount': ["Chegirma summadan katta bo'lishi mumkin emas."]})
        if amount - discount < self.instance.paid_amount:
            raise serializers.ValidationError({'amount': [
                f"To'lanishi kerak summa to'langan summadan ({self.instance.paid_amount:,.0f}) kam "
                f"bo'lib qoladi. Avval ortiqcha chekni bekor qiling."
            ]})
        return data


class MonthlyPaymentSummarySerializer(serializers.Serializer):
    """Dashboard uchun oylik to'lov xulosasi"""
    month          = serializers.IntegerField()
    year           = serializers.IntegerField()
    total_amount   = serializers.DecimalField(max_digits=14, decimal_places=0)
    total_paid     = serializers.DecimalField(max_digits=14, decimal_places=0)
    total_debt     = serializers.DecimalField(max_digits=14, decimal_places=0)
    paid_count     = serializers.IntegerField()
    partial_count  = serializers.IntegerField()
    unpaid_count   = serializers.IntegerField()
