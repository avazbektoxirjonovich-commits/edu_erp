from django.utils import timezone
from rest_framework import serializers

from apps.groups.models import Group

from .models import Payment


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
            'month', 'year', 'amount', 'paid_amount', 'debt_amount',
            'status', 'status_display', 'is_overdue', 'effective_status', 'due_date',
            'payment_date', 'note', 'received_by', 'created_at'
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
            # Snapshot pre-overwrite state so the caller (PaymentViewSet.create) can
            # log this as an UPDATE with an old/new changes payload instead of a CREATE.
            self.was_update = True
            self.previous_state = {
                'paid_amount': existing.paid_amount,
                'amount':      existing.amount,
                'note':        existing.note,
                'status':      existing.status,
                'debt_amount': existing.debt_amount,
            }
            existing.paid_amount  = validated_data['paid_amount']
            existing.amount       = validated_data.get('amount', existing.amount)
            existing.note         = validated_data.get('note', existing.note)
            existing.received_by  = validated_data['received_by']
            existing.payment_date = validated_data['payment_date']
            existing.save()
            return existing

        self.was_update = False
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
