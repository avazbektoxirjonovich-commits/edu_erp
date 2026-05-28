from rest_framework import serializers
from .models import Teacher, TeacherSalaryPayment
from apps.accounts.serializers import UserSerializer


class TeacherSerializer(serializers.ModelSerializer):
    full_name   = serializers.CharField(source='user.full_name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True, allow_null=True)
    group_count = serializers.SerializerMethodField()

    class Meta:
        model  = Teacher
        fields = ['id', 'full_name', 'phone', 'subject', 'salary',
                  'branch', 'branch_name',
                  'is_active', 'group_count', 'notes', 'created_at']

    def get_group_count(self, obj):
        v = getattr(obj, '_group_count', None)
        return v if v is not None else obj.groups.filter(status='active').count()


class TeacherCreateSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField()
    password  = serializers.CharField(write_only=True, min_length=4, default='erp12345')

    class Meta:
        model  = Teacher
        fields = ['full_name', 'phone', 'subject', 'salary', 'branch', 'notes', 'password']

    def validate_phone(self, value):
        from apps.accounts.models import User
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Bu telefon allaqachon ro'yxatda")
        return value

    def create(self, validated_data):
        from apps.accounts.models import User
        full_name = validated_data.pop('full_name')
        password  = validated_data.pop('password', 'erp12345')
        phone     = validated_data['phone']
        user = User.objects.create_user(
            phone=phone, password=password,
            full_name=full_name, role=User.Role.TEACHER
        )
        return Teacher.objects.create(user=user, **validated_data)


class TeacherSalaryPaymentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.full_name', read_only=True)
    paid_by_name = serializers.CharField(source='paid_by.full_name', read_only=True, default=None)
    total        = serializers.ReadOnlyField()

    class Meta:
        model  = TeacherSalaryPayment
        fields = ['id', 'teacher', 'teacher_name', 'month', 'year',
                  'amount', 'bonus', 'total', 'note', 'paid_by', 'paid_by_name', 'paid_at', 'created_at']
        read_only_fields = ['paid_by', 'paid_at', 'created_at']

    def create(self, validated_data):
        validated_data['paid_by'] = self.context['request'].user
        return super().create(validated_data)
