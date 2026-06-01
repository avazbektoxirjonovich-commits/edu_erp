from rest_framework import serializers
from django.utils import timezone
from .models import Payment
from apps.groups.models import Group


class PaymentSerializer(serializers.ModelSerializer):
    student_name   = serializers.CharField(source='student.user.full_name', read_only=True)
    group_name     = serializers.CharField(source='group.name', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model  = Payment
        fields = [
            'id', 'student', 'student_name', 'group', 'group_name',
            'month', 'year', 'amount', 'paid_amount', 'debt_amount',
            'status', 'status_display', 'payment_date', 'note',
            'received_by', 'created_at'
        ]
        read_only_fields = ['id', 'debt_amount', 'status', 'created_at']


class PaymentCreateSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=0, required=False, default=0
    )

    class Meta:
        model  = Payment
        fields = ['student', 'group', 'month', 'year', 'amount', 'paid_amount', 'note']
        extra_kwargs = {
            'group': {'required': False, 'allow_null': True},
        }

    def validate(self, data):
        student = data['student']

        # group ko'rsatilmasa — student ning joriy guruhidan olish
        if not data.get('group'):
            data['group'] = student.group

        # amount ko'rsatilmasa — guruh oylik to'lovidan olish
        if not data.get('amount'):
            data['amount'] = data['group'].monthly_fee if data.get('group') else 0

        # Bir oy uchun ikki marta yozuv bo'lmasin
        if data.get('group') and Payment.objects.filter(
            student=student,
            group=data['group'],
            month=data['month'],
            year=data['year'],
        ).exists():
            raise serializers.ValidationError(
                f"{data['year']}/{data['month']:02d} uchun to'lov allaqachon mavjud."
            )
        return data

    def create(self, validated_data):
        validated_data['received_by'] = self.context['request'].user
        validated_data['payment_date'] = timezone.now().date()
        return super().create(validated_data)


class PaymentUpdateSerializer(serializers.ModelSerializer):
    """To'lovga pul qo'shish"""
    class Meta:
        model  = Payment
        fields = ['paid_amount', 'note', 'payment_date']


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
