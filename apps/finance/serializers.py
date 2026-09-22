from decimal import Decimal

from rest_framework import serializers

from apps.payments.serializers import PaymentSerializer
from apps.payments.services import record_payment
from apps.students.models import Student

from .models import Asset, Expense, PaymentTransaction


class ExpenseSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    created_by_name   = serializers.CharField(source='created_by.full_name', read_only=True, default=None)
    # Olib kelingan narsani "Markaz buyumlari"ga ham qo'shish (faqat yaratishda)
    add_to_assets     = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model  = Expense
        fields = [
            'id', 'name', 'category', 'category_display', 'amount', 'expense_date',
            'description', 'is_recurring', 'recurring_source', 'quantity', 'asset', 'add_to_assets',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'recurring_source', 'asset', 'created_by', 'created_at', 'updated_at']

    def validate(self, data):
        category = data.get('category', getattr(self.instance, 'category', None))
        if 'category' in data and data['category'] == Expense.Category.SALARY:
            raise serializers.ValidationError({'category': [
                "Oylik bu yerda yozilmaydi — \"Ish haqi\" bo'limidan to'lang (aks holda ikki marta hisoblanadi)."
            ]})
        if category == Expense.Category.PURCHASE:
            qty = data.get('quantity', getattr(self.instance, 'quantity', None))
            if not qty:
                raise serializers.ValidationError({'quantity': ["Olib kelingan narsa miqdorini kiriting."]})
        elif data.get('add_to_assets'):
            raise serializers.ValidationError({'add_to_assets': [
                "Faqat \"Olib kelingan narsalar\" markaz buyumlariga qo'shiladi."
            ]})
        return data

    def create(self, validated_data):
        from django.db import transaction

        add_to_assets = validated_data.pop('add_to_assets', False)
        with transaction.atomic():
            expense = super().create(validated_data)
            if add_to_assets:
                expense.asset = Asset.objects.create(
                    name=expense.name, category=expense.get_category_display(),
                    quantity=expense.quantity,
                    purchase_price=expense.amount // expense.quantity,
                    purchase_date=expense.expense_date,
                    notes=expense.description, created_by=expense.created_by,
                )
                expense.save(update_fields=['asset'])
        return expense

    def update(self, instance, validated_data):
        validated_data.pop('add_to_assets', None)
        return super().update(instance, validated_data)


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
