"""
ACCOUNTS — Serializerlar
"""
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Foydalanuvchi ma'lumotlarini ko'rsatish uchun"""
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model  = User
        fields = ['id', 'phone', 'full_name', 'role', 'role_display',
                  'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class UserCreateSerializer(serializers.ModelSerializer):
    """Yangi foydalanuvchi yaratish"""
    password  = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model  = User
        fields = ['phone', 'full_name', 'role', 'password', 'password2']

    def validate(self, data):
        if data['password'] != data.pop('password2'):
            raise serializers.ValidationError("Parollar mos kelmadi")

        request_user = self.context.get('request') and self.context['request'].user
        target_role  = data.get('role', User.Role.STUDENT)
        if request_user and target_role == User.Role.DEVELOPER:
            if request_user.role != User.Role.DEVELOPER:
                raise serializers.ValidationError(
                    "Dasturchi akkaunt faqat dasturchi tomonidan yaratilishi mumkin."
                )
        return data

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    """Login: phone + password → JWT tokens"""
    phone    = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        # authenticate() nofaol userni None qaytaradi — is_active tekshiruvi ishlamaydi.
        # To'g'ri yondashuv: User ni topib, parol va holat alohida tekshiriladi.
        try:
            user = User.objects.get(phone=data['phone'])
        except User.DoesNotExist:
            raise serializers.ValidationError("Telefon yoki parol noto'g'ri")
        if not user.check_password(data['password']):
            raise serializers.ValidationError("Telefon yoki parol noto'g'ri")
        if not user.is_active:
            raise serializers.ValidationError(
                "Hisob faol emas. Iltimos adminga murojaat qiling."
            )
        data['user'] = user
        return data

    def get_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        # Token ichiga qo'shimcha ma'lumot qo'shish
        refresh['full_name'] = user.full_name
        refresh['role']      = user.role
        return {
            'refresh': str(refresh),
            'access':  str(refresh.access_token),
        }


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Profil tahrirlash — faqat ism va telefon"""
    class Meta:
        model  = User
        fields = ['full_name', 'phone']

    def validate_phone(self, value):
        user = self.instance
        if user and User.objects.filter(phone=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("Bu telefon raqam allaqachon ro'yxatdan o'tgan.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """Parol almashtirish"""
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Joriy parol noto'g'ri")
        return value

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user
