"""
ACCOUNTS — API ko'rinishlari (Views)
"""
import logging
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import (
    UserSerializer, UserCreateSerializer,
    LoginSerializer, ChangePasswordSerializer
)
from .permissions import IsAdmin

logger = logging.getLogger('apps.accounts')


def _log(user, action, model='User', object_id='', object_repr='', request=None):
    try:
        from apps.notifications.views import log_activity
        log_activity(user, action, model, object_id, object_repr, request=request)
    except Exception:
        pass


class LoginView(APIView):
    """
    POST /api/v1/auth/login/
    Body: { "phone": "+998901234567", "password": "secret123" }
    Javob: { "access": "...", "refresh": "...", "user": {...} }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user   = serializer.validated_data['user']
            tokens = serializer.get_tokens(user)
            logger.info(f"Kirdi: {user.phone}")
            _log(user, 'login', 'User', user.pk, str(user), request)
            return Response({
                **tokens,
                'user': UserSerializer(user).data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    Body: { "refresh": "..." }
    Refresh tokenni blacklist ga qo'shadi.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.data.get('refresh'))
            token.blacklist()
            logger.info(f"Chiqdi: {request.user.phone}")
            _log(request.user, 'logout', 'User', request.user.pk, str(request.user), request)
            return Response({'detail': 'Muvaffaqiyatli chiqildi'})
        except Exception:
            return Response(
                {'detail': 'Token noto\'g\'ri'},
                status=status.HTTP_400_BAD_REQUEST
            )


class MeView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/v1/auth/me/   — O'z profilini ko'rish
    PUT  /api/v1/auth/me/   — O'z profilini yangilash
    """
    serializer_class   = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """POST /api/v1/auth/change-password/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            _log(request.user, 'update', 'User', request.user.pk, 'Parol o\'zgartirildi', request)
            return Response({'detail': 'Parol muvaffaqiyatli o\'zgartirildi'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/auth/users/   — Foydalanuvchilar ro'yxati (admin)
    POST /api/v1/auth/users/   — Yangi foydalanuvchi yaratish (admin)
    """
    queryset           = User.objects.all()
    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        qs   = super().get_queryset()
        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role=role)
        return qs

    def perform_create(self, serializer):
        user = serializer.save()
        _log(self.request.user, 'create', 'User', user.pk, str(user), self.request)


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/auth/users/{id}/  — Bitta foydalanuvchi
    PUT    /api/v1/auth/users/{id}/  — Yangilash
    DELETE /api/v1/auth/users/{id}/  — O'chirish
    """
    queryset           = User.objects.all()
    serializer_class   = UserSerializer
    permission_classes = [IsAdmin]

    def perform_update(self, serializer):
        user = serializer.save()
        _log(self.request.user, 'update', 'User', user.pk, str(user), self.request)

    def perform_destroy(self, instance):
        _log(self.request.user, 'delete', 'User', instance.pk, str(instance), self.request)
        instance.delete()