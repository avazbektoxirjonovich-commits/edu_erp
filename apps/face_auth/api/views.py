"""
Face Auth API views.

Endpoints
---------
POST   /api/v1/face-auth/enroll/          – enroll or re-enroll face (authenticated)
DELETE /api/v1/face-auth/enroll/delete/   – remove enrollment (authenticated)
GET    /api/v1/face-auth/status/          – enrolled status (authenticated)
POST   /api/v1/face-auth/verify-login/    – 2FA verification (unauthenticated, face_pending_token)
POST   /api/v1/face-auth/otp-request/     – request OTP fallback email
POST   /api/v1/face-auth/otp-verify/      – verify OTP and obtain full tokens
"""
import logging
import random

from django.conf import settings
from django.core import signing
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.face_auth.models import FaceAuthLog, FaceProfile
from apps.face_auth.services.embeddings import (
    decode_frame,
    extract_embedding,
    validate_frame_quality,
)
from apps.face_auth.services.verify import verify_login_face
from apps.face_auth.crypto import encrypt_embedding
from .serializers import (
    EnrollSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    VerifyLoginSerializer,
)

logger = logging.getLogger('apps.face_auth')

FACE_PENDING_SALT    = 'face_pending_v1'
FACE_PENDING_MAX_AGE = 300    # 5 minutes
FALLBACK_SALT        = 'face_fallback_v1'
FALLBACK_MAX_AGE     = 600    # 10 minutes — survives face_pending expiry
OTP_SALT             = 'face_otp_v1'
OTP_MAX_AGE          = 600    # 10 minutes


def _client_ip(request) -> str:
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')


def _is_locked_out(user) -> bool:
    """Temporary lockout after FACE_MAX_ATTEMPTS failed attempts in FACE_LOCKOUT_MINUTES."""
    from datetime import timedelta
    max_att  = int(getattr(settings, 'FACE_MAX_ATTEMPTS',    5))
    lock_min = int(getattr(settings, 'FACE_LOCKOUT_MINUTES', 5))
    since    = timezone.now() - timedelta(minutes=lock_min)
    recent   = FaceAuthLog.objects.filter(
        user=user, result=FaceAuthLog.Result.DENIED, timestamp__gte=since
    ).count()
    return recent >= max_att


def _resolve_user_from_auth_token(face_token: str, fallback_token: str):
    """
    Resolve a User from face_pending_token OR fallback_token.
    Returns (user, error_response) — one of them will be None.
    face_pending_token has 5-min TTL; fallback_token has 10-min TTL.
    Either is sufficient to identify the user for OTP operations.
    """
    from apps.accounts.models import User

    user_id = None

    if face_token:
        try:
            data    = signing.loads(face_token, salt=FACE_PENDING_SALT, max_age=FACE_PENDING_MAX_AGE)
            user_id = data.get('user_id')
        except (signing.SignatureExpired, signing.BadSignature):
            # Fall through to fallback_token; if that is also absent/invalid, error below
            pass

    if not user_id and fallback_token:
        try:
            data    = signing.loads(fallback_token, salt=FALLBACK_SALT, max_age=FALLBACK_MAX_AGE)
            user_id = data.get('user_id')
        except signing.SignatureExpired:
            return None, Response(
                {"detail": "Zaxira token muddati o'tgan. Qayta kirish bosqichini boshdan boshlang."},
                status=400,
            )
        except signing.BadSignature:
            return None, Response({"detail": "fallback_token noto'g'ri"}, status=400)

    if not user_id:
        return None, Response({"detail": "Token muddati o'tgan yoki noto'g'ri"}, status=400)

    try:
        user = User.objects.get(pk=user_id)
        return user, None
    except User.DoesNotExist:
        return None, Response({"detail": "Foydalanuvchi topilmadi"}, status=400)


def _log_attempt(user, liveness_passed, identity_matched, result, challenge, reason, ip):
    FaceAuthLog.objects.create(
        user             = user,
        liveness_passed  = liveness_passed,
        identity_matched = identity_matched,
        result           = result,
        challenge        = challenge,
        failure_reason   = reason or '',
        ip_address       = ip or None,
    )


# ── Enrollment ────────────────────────────────────────────────────────────────

class FaceEnrollView(APIView):
    """
    POST /api/v1/face-auth/enroll/
    Body: { frame: <base64 JPEG>, consent: true }
    Enrolls (or re-enrolls) the authenticated user's face.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = EnrollSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        frame_b64 = ser.validated_data['frame']
        consent   = ser.validated_data['consent']

        if not consent:
            return Response(
                {"detail": "Biometrik ma'lumotlarni saqlashga rozilik berilmagan"},
                status=400,
            )

        frame = decode_frame(frame_b64)
        if frame is None:
            return Response({"detail": "Kadrni o'qib bo'lmadi"}, status=400)

        valid, reason = validate_frame_quality(frame)
        if not valid:
            _log_attempt(request.user, None, None, FaceAuthLog.Result.DENIED,
                         'enroll', reason, _client_ip(request))
            return Response({"detail": reason}, status=400)

        embedding = extract_embedding(frame)
        if embedding is None:
            _log_attempt(request.user, None, None, FaceAuthLog.Result.DENIED,
                         'enroll', 'embedding_failed', _client_ip(request))
            return Response(
                {"detail": "Yuz aniqlanmadi yoki embedding chiqarib bo'lmadi"},
                status=400,
            )

        enc = encrypt_embedding(embedding)

        profile, _ = FaceProfile.objects.get_or_create(user=request.user)
        profile.encrypted_embedding = enc
        profile.status              = FaceProfile.Status.ENROLLED
        profile.enrolled_at         = timezone.now()
        profile.consent_given       = True
        profile.consent_at          = timezone.now()
        profile.save()

        logger.info("Yuz ro'yxatga olindi: user=%s", request.user.pk)
        _log_attempt(request.user, None, None, FaceAuthLog.Result.OK,
                     'enroll', '', _client_ip(request))
        return Response(
            {"detail": "Face ID muvaffaqiyatli o'rnatildi", "status": "enrolled"},
        )


class FaceDeleteView(APIView):
    """DELETE /api/v1/face-auth/enroll/delete/ – Remove enrollment."""
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        try:
            profile = request.user.face_profile
        except FaceProfile.DoesNotExist:
            return Response({"detail": "Yuz profili topilmadi"}, status=404)

        profile.encrypted_embedding = None
        profile.status              = FaceProfile.Status.NOT_ENROLLED
        profile.enrolled_at         = None
        profile.save()
        logger.info("Yuz o'chirildi: user=%s", request.user.pk)
        return Response({"detail": "Face ID o'chirildi"})


class FaceStatusView(APIView):
    """GET /api/v1/face-auth/status/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            profile     = request.user.face_profile
            enrolled    = profile.is_enrolled
            enrolled_at = profile.enrolled_at.isoformat() if profile.enrolled_at else None
        except FaceProfile.DoesNotExist:
            enrolled    = False
            enrolled_at = None

        return Response({
            "enrolled":    enrolled,
            "enrolled_at": enrolled_at,
            "label":       "Yoqilgan" if enrolled else "O'rnatilmagan",
        })


# ── Login second factor ───────────────────────────────────────────────────────

class FaceVerifyLoginView(APIView):
    """
    POST /api/v1/face-auth/verify-login/
    Body: { face_pending_token, frames: [b64, ...] }
    Verifies liveness + identity. On success returns full JWT tokens.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        ser = VerifyLoginSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        face_token = ser.validated_data['face_pending_token']
        frames_b64 = ser.validated_data['frames']

        # Validate the signed face_pending_token (server-issued, tamper-proof)
        try:
            token_data = signing.loads(
                face_token,
                salt=FACE_PENDING_SALT,
                max_age=FACE_PENDING_MAX_AGE,
            )
        except signing.SignatureExpired:
            return Response(
                {"detail": "Tasdiqlash vaqti tugadi. Qayta kirish bosqichini boshdan boshlang."},
                status=400,
            )
        except signing.BadSignature:
            return Response({"detail": "Noto'g'ri token"}, status=400)

        user_id = token_data.get('user_id')

        if not user_id:
            return Response({"detail": "Token ma'lumotlari noto'g'ri"}, status=400)

        from apps.accounts.models import User
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "Foydalanuvchi topilmadi"}, status=400)

        if _is_locked_out(user):
            return Response(
                {"detail": "Juda ko'p urinishlar. Bir oz kuting va qayta urinib ko'ring."},
                status=429,
            )

        ip = _client_ip(request)

        # ── Single-use: reject replays ─────────────────────────────────────
        from apps.face_auth.token_store import mark_used
        if not mark_used(face_token, FACE_PENDING_MAX_AGE):
            return Response(
                {"detail": "Bu token allaqachon ishlatilgan. Qayta kirish bosqichini boshdan boshlang."},
                status=400,
            )

        # Server-authoritative verification — challenge comes from token, not client
        passed, liveness_ok, identity_ok, error_msg = verify_login_face(
            user, frames_b64
        )

        result_code = FaceAuthLog.Result.OK if passed else FaceAuthLog.Result.DENIED
        _log_attempt(user, liveness_ok, identity_ok, result_code, challenge_action, error_msg, ip)

        if not passed:
            logger.warning("Yuz tekshiruvi rad etildi: user=%s reason=%s", user.pk, error_msg)

            # Count recent failures to decide whether to offer OTP fallback
            from datetime import timedelta
            recent_fails = FaceAuthLog.objects.filter(
                user=user,
                result=FaceAuthLog.Result.DENIED,
                timestamp__gte=timezone.now() - timedelta(minutes=10),
            ).count()

            resp = {"detail": error_msg or "Yuz tekshiruvi muvaffaqiyatsiz"}
            if recent_fails >= 3:
                resp["otp_available"] = True
                resp["detail_extra"]  = "Muammo davom etsa 'Zaxira kod' tugmasini bosing."
            return Response(resp, status=401)

        # Issue full JWT tokens
        from rest_framework_simplejwt.tokens import RefreshToken
        from apps.accounts.serializers import UserSerializer
        refresh = RefreshToken.for_user(user)
        logger.info("Yuz tekshiruvi muvaffaqiyatli: user=%s", user.pk)
        return Response({
            "access":  str(refresh.access_token),
            "refresh": str(refresh),
            "user":    UserSerializer(user).data,
        })


# ── OTP fallback ──────────────────────────────────────────────────────────────

class FaceOTPRequestView(APIView):
    """
    POST /api/v1/face-auth/otp-request/
    Accepts face_pending_token (5 min) OR fallback_token (10 min).
    fallback_token keeps OTP accessible even after face_pending_token expires.
    Returns otp_verification_token to the client.
    """
    permission_classes = [AllowAny]
    throttle_scope     = 'face_auth'

    def post(self, request):
        ser = OTPRequestSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        face_token     = ser.validated_data.get('face_pending_token', '')
        fallback_token = ser.validated_data.get('fallback_token', '')

        user, err = _resolve_user_from_auth_token(face_token, fallback_token)
        if err:
            return err

        # FIX B: fallback_token is single-use — reject second OTP request
        # with the same fallback_token within its lifetime.
        if fallback_token:
            from apps.face_auth.token_store import mark_used, is_used
            if is_used(fallback_token):
                return Response(
                    {"detail": "Bu zaxira token allaqachon ishlatilgan. Qayta kirish bosqichini boshdan boshlang."},
                    status=400,
                )
            mark_used(fallback_token, FALLBACK_MAX_AGE)

        otp = f"{random.randint(100000, 999999)}"
        otp_verification_token = signing.dumps(
            {'user_id': str(user.pk), 'otp': otp},
            salt=OTP_SALT,
        )

        # Log OTP request to FaceAuthLog (FIX 6)
        _log_attempt(user, None, None, FaceAuthLog.Result.DENIED, 'otp_request',
                     'OTP so\'rov', _client_ip(request))

        sent = _send_otp_email(user, otp)
        if not sent:
            return Response(
                {"detail": "OTP yuborishda xatolik. Adminga murojaat qiling."},
                status=500,
            )

        return Response({
            "detail":                 "OTP kod yuborildi",
            "otp_verification_token": otp_verification_token,
        })


def _send_otp_email(user, otp: str) -> bool:
    """
    Compatibility shim: existing tests mock this name.
    Routes to the pluggable OTP backend (console / sms / telegram).
    Backend is chosen by FACE_OTP_BACKEND setting (default: 'console').
    """
    from apps.face_auth.services.otp import send_otp
    return send_otp(user, otp)


class FaceOTPVerifyView(APIView):
    """
    POST /api/v1/face-auth/otp-verify/
    Body: { face_pending_token OR fallback_token, otp_verification_token, otp }
    Verify OTP and return full JWT tokens.
    """
    permission_classes = [AllowAny]
    throttle_scope     = 'face_auth'

    def post(self, request):
        ser = OTPVerifySerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        face_token     = ser.validated_data.get('face_pending_token', '')
        fallback_token = ser.validated_data.get('fallback_token', '')
        otp_verify_tok = ser.validated_data['otp_verification_token']
        otp_code       = ser.validated_data['otp']

        # Resolve the user from whichever auth token was supplied
        user, err = _resolve_user_from_auth_token(face_token, fallback_token)
        if err:
            return err

        try:
            otp_data = signing.loads(otp_verify_tok, salt=OTP_SALT, max_age=OTP_MAX_AGE)
        except signing.SignatureExpired:
            return Response({"detail": "OTP muddati o'tgan. Qayta so'rang."}, status=400)
        except signing.BadSignature:
            return Response({"detail": "OTP token noto'g'ri"}, status=400)

        if str(user.pk) != otp_data.get('user_id'):
            return Response({"detail": "Token mos kelmadi"}, status=400)

        if otp_data.get('otp') != otp_code:
            return Response({"detail": "OTP kod noto'g'ri"}, status=400)

        # Single-use: mark otp_verification_token used to prevent replay
        from apps.face_auth.token_store import mark_used
        if not mark_used(otp_verify_tok, OTP_MAX_AGE):
            return Response(
                {"detail": "Bu OTP allaqachon ishlatilgan. Qayta so'rang."},
                status=400,
            )

        # Log successful OTP fallback
        _log_attempt(user, None, None, FaceAuthLog.Result.OK, 'otp_verify',
                     '', _client_ip(request))

        from rest_framework_simplejwt.tokens import RefreshToken
        from apps.accounts.serializers import UserSerializer
        refresh = RefreshToken.for_user(user)
        logger.info("OTP zaxira orqali kirish: user=%s", user.pk)
        return Response({
            "access":  str(refresh.access_token),
            "refresh": str(refresh),
            "user":    UserSerializer(user).data,
        })
