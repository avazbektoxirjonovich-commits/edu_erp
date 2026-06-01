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
    group = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), required=False, allow_null=True, default=None
    )

    class Meta:
        model  = Payment
        fields = ['id', 'student', 'group', 'month', 'year', 'amount', 'paid_amount', 'note']
        read_only_fields = ['id']

    def validate(self, data):
        student = data['student']

        # group ko'rsatilmasa — student ning joriy guruhidan olish
        if not data.get('group'):
            data['group'] = student.group

        # amount ko'rsatilmasa — guruh oylik to'lovidan olish
        if not data.get('amount'):
            data['amount'] = data['group'].monthly_fee if data.get('group') else 0

        return data

    def create(self, validated_data):
        validated_data['received_by'] = self.context['request'].user
        validated_data['payment_date'] = timezone.now().date()

        student = validated_data['student']
        group   = validated_data.get('group')
        month   = validated_data['month']
        year    = validated_data['year']

        # Mavjud bo'lsa — yangilash (upsert); bo'lmasa — yaratish
        existing = Payment.objects.filter(
            student=student, group=group, month=month, year=year
        ).first()
        if existing:
            existing.paid_amount  = validated_data['paid_amount']
            existing.amount       = validated_data.get('amount', existing.amount)
            existing.note         = validated_data.get('note', existing.note)
            existing.received_by  = validated_data['received_by']
            existing.payment_date = validated_data['payment_date']
            existing.save()
            return existing

        return Payment.objects.create(**validated_data)


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
