from decimal import Decimal

from rest_framework import serializers

from .models import Application


class ApplicationListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model  = Application
        fields = ['id', 'full_name', 'phone', 'age', 'direction',
                  'status', 'status_display', 'created_at']


class ApplicationDetailSerializer(serializers.ModelSerializer):
    status_display  = serializers.CharField(source='get_status_display', read_only=True)
    handled_by_name = serializers.CharField(source='handled_by.full_name', read_only=True, default=None)
    student_id      = serializers.UUIDField(source='student.id', read_only=True, default=None)

    class Meta:
        model  = Application
        fields = ['id', 'full_name', 'phone', 'address', 'parent_name', 'age', 'direction',
                  'status', 'status_display', 'note', 'student_id',
                  'handled_by_name', 'handled_at', 'created_at']
        read_only_fields = [f for f in fields if f != 'note']


class ConvertSerializer(serializers.Serializer):
    """Panel ochish: kurs to'lovi majburiy, qolgani ixtiyoriy."""
    monthly_fee = serializers.DecimalField(max_digits=10, decimal_places=0,
                                           min_value=Decimal('1'),
                                           error_messages={
                                               'required': "Kurs to'lovini kiriting — busiz panel ochilmaydi.",
                                               'null': "Kurs to'lovini kiriting — busiz panel ochilmaydi.",
                                               'min_value': "Kurs to'lovi 0 dan katta bo'lsin.",
                                           })
    discount    = serializers.DecimalField(max_digits=10, decimal_places=0,
                                           min_value=Decimal('0'), required=False,
                                           default=Decimal('0'))
    group       = serializers.UUIDField(required=False, allow_null=True)
    password    = serializers.CharField(required=False, allow_blank=True, min_length=4, max_length=50)

    def validate(self, data):
        if data.get('discount', Decimal('0')) > data['monthly_fee']:
            raise serializers.ValidationError({'discount': [
                "Chegirma kurs to'lovidan katta bo'lishi mumkin emas."]})
        return data
