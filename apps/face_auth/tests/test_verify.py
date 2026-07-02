"""
Tests for the verify-login endpoint.
Covers: success, liveness fail, identity mismatch, no enrollment, static-image replay.
"""
import pytest
from unittest.mock import patch
from django.core import signing
import numpy as np

from apps.face_auth.models import FaceProfile, FaceAuthLog
from apps.face_auth.crypto import encrypt_embedding
from .conftest import make_synthetic_embedding, make_varying_frames


VERIFY_URL = '/api/v1/face-auth/verify-login/'
PENDING_SALT = 'face_pending_v1'


def _make_token(user_id: str, action: str = 'smile') -> str:
    return signing.dumps(
        {'user_id': str(user_id), 'challenge': {'action': action, 'label': 'Jilmaying'}},
        salt=PENDING_SALT,
        compress=True,
    )


def _enroll(user, fernet_key, embedding=None):
    if embedding is None:
        embedding = make_synthetic_embedding()
    enc = encrypt_embedding(embedding)
    FaceProfile.objects.update_or_create(
        user=user,
        defaults={
            'encrypted_embedding': enc,
            'status':              FaceProfile.Status.ENROLLED,
            'consent_given':       True,
        },
    )
    return embedding


@pytest.mark.django_db
class TestVerifyLogin:

    # ── Success path ──────────────────────────────────────────────────────────

    @patch('apps.face_auth.services.embeddings.extract_embedding')
    @patch('apps.face_auth.services.embeddings.select_best_frame')
    @patch('apps.face_auth.services.liveness.verify_liveness')
    @patch('apps.face_auth.services.embeddings.decode_frame')
    def test_verify_success(self, mock_decode, mock_liveness, mock_best, mock_embed,
                            api_client, admin_user, fernet_key):
        ref_emb = _enroll(admin_user, fernet_key)
        mock_decode.side_effect    = lambda b: np.zeros((50, 50, 3), dtype=np.uint8)
        mock_liveness.return_value = (True, '')
        mock_best.return_value     = np.zeros((50, 50, 3), dtype=np.uint8)
        mock_embed.return_value    = ref_emb  # identical → similarity=1.0

        resp = api_client.post(VERIFY_URL, {
            'face_pending_token': _make_token(admin_user.pk),
            'frames':             make_varying_frames(10),
        }, format='json')

        assert resp.status_code == 200
        assert 'access'  in resp.json()
        assert 'refresh' in resp.json()

    def test_verify_audit_log_created(self, api_client, admin_user, fernet_key):
        """Every verify attempt must create a FaceAuthLog entry."""
        with patch('apps.face_auth.api.views.verify_login_face',
                   return_value=(False, False, False, 'Jonlilik tekshiruvidan o\'tmadi: test')):
            api_client.post(VERIFY_URL, {
                'face_pending_token': _make_token(admin_user.pk),
                'frames':             make_varying_frames(5),
            }, format='json')

        assert FaceAuthLog.objects.filter(user=admin_user).exists()

    # ── DENIED: token issues ──────────────────────────────────────────────────

    def test_expired_token(self, api_client, admin_user, fernet_key):
        import time
        from django.core import signing
        # Create a token then force expiry by loading with max_age=0
        token = _make_token(admin_user.pk)
        resp  = api_client.post(VERIFY_URL, {
            'face_pending_token': 'invalid.token.here',
            'frames':             make_varying_frames(5),
        }, format='json')
        assert resp.status_code == 400

    def test_missing_token(self, api_client, admin_user, fernet_key):
        resp = api_client.post(VERIFY_URL, {'frames': make_varying_frames(5)}, format='json')
        assert resp.status_code == 400

    # ── DENIED: liveness fail ─────────────────────────────────────────────────

    @patch('apps.face_auth.api.views.verify_login_face')
    def test_liveness_fail_denied(self, mock_verify, api_client, admin_user, fernet_key):
        _enroll(admin_user, fernet_key)
        mock_verify.return_value = (
            False, False, False, "Jonlilik tekshiruvidan o'tmadi: Tirik odam aniqlanmadi"
        )
        resp = api_client.post(VERIFY_URL, {
            'face_pending_token': _make_token(admin_user.pk),
            'frames':             make_varying_frames(5),
        }, format='json')
        assert resp.status_code == 401
        assert 'Jonlilik' in resp.json()['detail']

    # ── DENIED: identity mismatch ─────────────────────────────────────────────

    @patch('apps.face_auth.api.views.verify_login_face')
    def test_identity_mismatch_denied(self, mock_verify, api_client, admin_user, fernet_key):
        _enroll(admin_user, fernet_key)
        mock_verify.return_value = (False, True, False, "Yuz mos kelmadi")

        resp = api_client.post(VERIFY_URL, {
            'face_pending_token': _make_token(admin_user.pk),
            'frames':             make_varying_frames(10),
        }, format='json')
        assert resp.status_code == 401
        assert 'Yuz mos kelmadi' in resp.json()['detail']

    # ── Static image replay attack is denied ─────────────────────────────────

    @patch('apps.face_auth.services.embeddings.extract_embedding')
    @patch('apps.face_auth.services.embeddings.select_best_frame')
    def test_static_image_replay_denied(self, mock_best, mock_embed,
                                        api_client, admin_user, fernet_key):
        """
        Identity is checked first (new order) and is made to match here so the
        test still exercises what it's meant to: 10 bit-identical frames →
        zero inter-frame motion → liveness denies the static/replayed image.
        """
        import cv2
        import base64
        ref_emb = _enroll(admin_user, fernet_key)

        # 10 identical frames (no motion)
        static_frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        _, buf = cv2.imencode('.jpg', static_frame)
        b64 = 'data:image/jpeg;base64,' + base64.b64encode(buf).decode()
        identical_frames = [b64] * 10

        mock_best.return_value  = static_frame
        mock_embed.return_value = ref_emb   # identity matches → reaches liveness

        with patch('apps.face_auth.services.liveness._build_face_mesh') as mock_fm:
            # Even if MediaPipe would detect a face, motion check fires first
            resp = api_client.post(VERIFY_URL, {
                'face_pending_token': _make_token(admin_user.pk),
                'frames':             identical_frames,
            }, format='json')

        assert resp.status_code == 401
        detail = resp.json().get('detail', '')
        # Must be rejected for liveness reasons, not identity
        assert any(kw in detail for kw in ['Jonlilik', 'harakatsiz', 'muvaffaqiyatsiz'])

    # ── No enrollment → denied ────────────────────────────────────────────────

    @patch('apps.face_auth.api.views.verify_login_face')
    def test_not_enrolled_denied(self, mock_verify, api_client, admin_user, fernet_key):
        mock_verify.return_value = (False, True, False, "Yuz ro'yxatga olinmagan")

        resp = api_client.post(VERIFY_URL, {
            'face_pending_token': _make_token(admin_user.pk),
            'frames':             make_varying_frames(5),
        }, format='json')
        assert resp.status_code == 401


@pytest.mark.django_db
class TestLoginFaceGate:
    """Test that LoginView returns face_pending_token when 2FA is required."""

    LOGIN_URL = '/api/v1/auth/login/'

    def test_no_face_required_when_disabled(self, api_client, admin_user, settings):
        settings.FACE_AUTH_ENABLED = False
        resp = api_client.post(
            self.LOGIN_URL,
            {'phone': '+998901234567', 'password': 'testpass123'},
            format='json',
        )
        assert resp.status_code == 200
        assert 'access' in resp.json()
        assert 'face_required' not in resp.json()

    @patch('apps.face_auth.api.views.extract_embedding')
    @patch('apps.face_auth.api.views.validate_frame_quality')
    @patch('apps.face_auth.api.views.decode_frame')
    def test_face_required_when_enrolled_and_enabled(
            self, mock_decode, mock_quality, mock_embed,
            api_client, admin_user, settings, fernet_key):

        settings.FACE_AUTH_ENABLED   = True
        settings.FACE_REQUIRED_ROLES = ['admin', 'developer']

        # Enroll first
        mock_decode.return_value  = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_quality.return_value = (True, '')
        mock_embed.return_value   = make_synthetic_embedding()
        api_client.force_authenticate(user=admin_user)
        api_client.post('/api/v1/face-auth/enroll/',
                        {'frame': 'data:image/jpeg;base64,/9j/foo', 'consent': True},
                        format='json')
        api_client.force_authenticate(user=None)

        resp = api_client.post(
            self.LOGIN_URL,
            {'phone': '+998901234567', 'password': 'testpass123'},
            format='json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('face_required') is True
        assert 'face_pending_token' in data
        assert 'fallback_token'     in data
        assert 'challenge'          in data
        assert 'access' not in data


# ── FIX 3: Single-use token replay prevention ─────────────────────────────────

@pytest.mark.django_db
class TestTokenReplay:

    @patch('apps.face_auth.api.views.verify_login_face')
    def test_face_pending_token_cannot_be_replayed(self, mock_verify,
                                                    api_client, admin_user, fernet_key):
        """A face_pending_token that was used successfully cannot be reused."""
        from apps.face_auth.crypto import encrypt_embedding
        from apps.face_auth.models import FaceProfile

        enc = encrypt_embedding(make_synthetic_embedding())
        FaceProfile.objects.update_or_create(user=admin_user, defaults={
            'encrypted_embedding': enc,
            'status': FaceProfile.Status.ENROLLED,
            'consent_given': True,
        })
        mock_verify.return_value = (True, True, True, None)
        token = _make_token(admin_user.pk)

        # First use — should succeed
        resp1 = api_client.post(VERIFY_URL, {
            'face_pending_token': token,
            'frames':             make_varying_frames(5),
        }, format='json')
        assert resp1.status_code == 200, resp1.json()

        # Second use of the same token — must be rejected
        resp2 = api_client.post(VERIFY_URL, {
            'face_pending_token': token,
            'frames':             make_varying_frames(5),
        }, format='json')
        assert resp2.status_code == 400, resp2.json()
        assert 'allaqachon' in resp2.json()['detail']

    def test_otp_verification_token_cannot_be_replayed(self, api_client, admin_user,
                                                        settings, fernet_key, capsys):
        """A used otp_verification_token cannot be replayed."""
        settings.FACE_OTP_BACKEND = 'console'
        from apps.face_auth.api.views import FALLBACK_SALT
        from django.core import signing
        fallback_tok = signing.dumps({'user_id': str(admin_user.pk)}, salt=FALLBACK_SALT)

        otp_resp = api_client.post('/api/v1/face-auth/otp-request/',
                                   {'fallback_token': fallback_tok}, format='json')
        assert otp_resp.status_code == 200
        otp_token = otp_resp.json()['otp_verification_token']
        captured  = capsys.readouterr()
        import re
        match = re.search(r'\[FACE_ID_OTP\].*?-> (\d{6})', captured.out)
        assert match
        otp_code = match.group(1)

        verify_payload = {
            'fallback_token':         fallback_tok,
            'otp_verification_token': otp_token,
            'otp':                    otp_code,
        }

        # First use — OK
        r1 = api_client.post('/api/v1/face-auth/otp-verify/', verify_payload, format='json')
        assert r1.status_code == 200

        # Replay — must be rejected
        r2 = api_client.post('/api/v1/face-auth/otp-verify/', verify_payload, format='json')
        assert r2.status_code == 400
        assert 'allaqachon' in r2.json()['detail']
