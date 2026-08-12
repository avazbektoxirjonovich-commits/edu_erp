from rest_framework import serializers

from .models import Teacher, TeacherSalaryPayment


class TeacherSerializer(serializers.ModelSerializer):
    full_name   = serializers.CharField(source='user.full_name', read_only=True)
    group_count = serializers.SerializerMethodField()

    class Meta:
        model  = Teacher
        fields = ['id', 'full_name', 'phone', 'subject', 'salary_type', 'salary', 'hourly_rate',
                  'is_active', 'group_count', 'notes', 'created_at']

    def get_group_count(self, obj):
        v = getattr(obj, '_group_count', None)
        return v if v is not None else obj.groups.filter(status='active').count()


class TeacherCreateSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField()
    password  = serializers.CharField(write_only=True, min_length=4, default='erp12345')

    class Meta:
        model  = Teacher
        fields = ['id', 'full_name', 'phone', 'subject', 'salary_type', 'salary', 'hourly_rate',
                  'notes', 'password']
        read_only_fields = ['id']

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


class TeacherUpdateSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(required=False)

    class Meta:
        model  = Teacher
        fields = ['id', 'full_name', 'phone', 'subject', 'salary_type', 'salary', 'hourly_rate',
                  'notes', 'is_active']
        read_only_fields = ['id']

    def validate_phone(self, value):
        from apps.accounts.models import User
        teacher = self.instance
        if teacher and User.objects.filter(phone=value).exclude(pk=teacher.user.pk).exists():
            raise serializers.ValidationError("Bu telefon allaqachon ro'yxatda")
        return value

    def update(self, instance, validated_data):
        from django.db import transaction
        full_name = validated_data.pop('full_name', None)
        phone     = validated_data.get('phone')
        with transaction.atomic():
            if full_name and instance.user.full_name != full_name:
                instance.user.full_name = full_name
                instance.user.save(update_fields=['full_name'])
            if phone and instance.user.phone != phone:
                instance.user.phone = phone
                instance.user.save(update_fields=['phone'])
        return super().update(instance, validated_data)


class TeacherSalaryPaymentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.full_name', read_only=True)
    paid_by_name = serializers.CharField(source='paid_by.full_name', read_only=True, default=None)
    salary_type  = serializers.CharField(source='teacher.salary_type', read_only=True)
    total        = serializers.ReadOnlyField()
    amount       = serializers.DecimalField(max_digits=12, decimal_places=0, required=False)

    class Meta:
        model  = TeacherSalaryPayment
        fields = ['id', 'teacher', 'teacher_name', 'salary_type', 'month', 'year',
                  'amount', 'worked_hours', 'bonus', 'deductions', 'total', 'status',
                  'note', 'paid_by', 'paid_by_name', 'paid_at', 'created_at']
        read_only_fields = ['paid_by', 'paid_at', 'created_at']

    def validate(self, data):
        teacher = data.get('teacher') or (self.instance.teacher if self.instance else None)
        month   = data.get('month') or (self.instance.month if self.instance else None)
        year    = data.get('year') or (self.instance.year if self.instance else None)

        qs = TeacherSalaryPayment.objects.filter(teacher=teacher, month=month, year=year)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                f"{year}/{month:02d} oy uchun ish haqi allaqachon to'langan."
            )

        # Soatlik o'qituvchi uchun: amount berilmasa, hourly_rate * worked_hours'dan hisoblanadi.
        if not data.get('amount') and teacher and teacher.salary_type == Teacher.SalaryType.HOURLY:
            hours = data.get('worked_hours')
            if hours is None and self.instance:
                hours = self.instance.worked_hours
            data['amount'] = teacher.hourly_rate * (hours or 0)

        if not data.get('amount') and not self.instance:
            raise serializers.ValidationError({'amount': "Summani kiriting yoki ishlagan soatni belgilang."})

        return data

    def create(self, validated_data):
        validated_data['paid_by'] = self.context['request'].user
        return super().create(validated_data)
