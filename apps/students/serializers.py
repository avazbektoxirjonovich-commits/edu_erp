from rest_framework import serializers
from apps.accounts.serializers import UserSerializer
from apps.common.utils import calculate_attendance_pct
from .models import Student


class StudentListSerializer(serializers.ModelSerializer):
    full_name      = serializers.CharField(source='user.full_name', read_only=True)
    group_name     = serializers.CharField(source='group.name', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_debt            = serializers.SerializerMethodField()
    attendance_percentage = serializers.SerializerMethodField()

    class Meta:
        model  = Student
        fields = [
            'id', 'full_name', 'phone', 'group', 'group_name',
            'status', 'status_display', 'attendance_percentage',
            'total_debt', 'joined_date',
        ]

    def get_total_debt(self, obj):
        annotated = getattr(obj, '_total_debt', None)
        if annotated is not None:
            return annotated
        return obj.total_debt

    def get_attendance_percentage(self, obj):
        total   = getattr(obj, '_total_attend', None)
        present = getattr(obj, '_present', None)
        if total is None:
            return obj.attendance_percentage
        return calculate_attendance_pct(present, total)


class StudentDetailSerializer(serializers.ModelSerializer):
    user                  = UserSerializer(read_only=True)
    group_name            = serializers.CharField(source='group.name', read_only=True, allow_null=True)
    attendance_percentage = serializers.FloatField(read_only=True)
    total_debt            = serializers.DecimalField(max_digits=12, decimal_places=0, read_only=True)

    class Meta:
        model  = Student
        fields = '__all__'


class StudentCreateSerializer(serializers.ModelSerializer):
    full_name    = serializers.CharField()
    phone        = serializers.CharField()
    parent_name  = serializers.CharField(required=False, allow_blank=True, default='')
    parent_phone = serializers.CharField(required=False, allow_blank=True, default='')
    password     = serializers.CharField(write_only=True, min_length=4, default='erp12345')

    class Meta:
        model  = Student
        fields = [
            'full_name', 'phone', 'parent_name', 'parent_phone',
            'group', 'birth_date', 'address', 'notes', 'password',
        ]

    def validate_phone(self, value):
        import re
        if not re.match(r'^\+998\d{9}$', value):
            raise serializers.ValidationError("Format: +998901234567 (masalan: +998901234567)")
        from apps.accounts.models import User
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Bu telefon raqam allaqachon ro'yxatda bor")
        return value

    def validate_parent_phone(self, value):
        import re
        if value and not re.match(r'^\+998\d{9}$', value):
            raise serializers.ValidationError("Format: +998901234567")
        return value

    def create(self, validated_data):
        from apps.accounts.models import User
        full_name   = validated_data.pop('full_name')
        password    = validated_data.pop('password', 'erp12345')
        phone       = validated_data['phone']
        user = User.objects.create_user(
            phone=phone, password=password,
            full_name=full_name, role=User.Role.STUDENT
        )
        return Student.objects.create(user=user, **validated_data)


class StudentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Student
        fields = ['phone', 'parent_phone', 'parent_name', 'group',
                  'status', 'birth_date', 'address', 'notes', 'parent_user']

    def validate_parent_user(self, value):
        from apps.accounts.models import User
        if value and value.role != User.Role.PARENT:
            raise serializers.ValidationError("Bu foydalanuvchi ota-ona roliga ega emas")
        return value
