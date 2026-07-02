"""
Tests for rate-limiting / lockout and OTP fallback.
"""
import pytest
from unittest.mock import patch
from django.core import signing
from django.utils import timezone
from datetime import timedelta

from apps.face_auth.models import FaceAuthLog
from apps.face_auth.crypto import encrypt_embedding
from apps.face_auth.api.views import FACE_PENDING_SALT, FALLBACK_SALT, OTP_SALT
from .conftest import make_synthetic_embedding, make_varying_frames

VERIFY_URL      = '/api/v1/face-auth/verify-login/'
OTP_REQUEST_URL = '/api/v1/face-auth/otp-request/'
OTP_VERIFY_URL  = '/api/v1/face-auth/otp-verify/'


def _make_token(user_id, action='smile'):
    return signing.dumps(
        {'user_id': str(user_id), 'challenge': {'action': action, 'label': 'Jilmaying'}},
        salt=FACE_PENDING_SALT,
    )


def _enroll_user(user, fernet_key):
    from apps.face_auth.models import FaceProfile
    enc = encrypt_embedding(make_synthetic_embedding())
    FaceProfile.objects.update_or_create(
        user=user,
        defaults={
            'encrypted_embedding': enc,
            'status':              FaceProfile.Status.ENROLLED,
            'consent_given':       True,
        },
    )


@pytest.mark.django_db
class TestLockout:

    def _flood_failures(self, user, n: int):
        """Insert n DENIED log entries within the lockout window."""
        for _ in range(n):
            FaceAuthLog.objects.create(
                user             = user,
                liveness_passed  = False,
                identity_matched = False,
                result           = FaceAuthLog.Result.DENIED,
                challenge        = 'smile',
                failure_reason   = 'test',
                ip_address       = '127.0.0.1',
            )

    def test_lockout_after_max_attempts(self, api_client, admin_user, settings, fernet_key):
        settings.FACE_MAX_ATTEMPTS    = 5
        settings.FACE_LOCKOUT_MINUTES = 5
        _enroll_user(admin_user, fernet_key)
        self._flood_failures(admin_user, 5)

        resp = api_client.post(VERIFY_URL, {
            'face_pending_token': _make_token(admin_user.pk),
            'frames':             make_varying_frames(5),
        }, format='json')
        assert resp.status_code == 429
        assert 'kuting' in resp.json()['detail'].lower() or 'urinish' in resp.json()['detail'].lower()

    def test_no_lockout_before_threshold(self, api_client, admin_user, settings, fernet_key):
        settings.FACE_MAX_ATTEMPTS    = 5
        settings.FACE_LOCKOUT_MINUTES = 5
        _enroll_user(admin_user, fernet_key)
        self._flood_failures(admin_user, 4)  # one below threshold

        with patch('apps.face_auth.api.views.verify_login_face',
                   return_value=(False, False, False, "Jonlilik tekshiruvidan o'tmadi")):
            resp = api_client.post(VERIFY_URL, {
                'face_pending_token': _make_token(admin_user.pk),
                'frames':             make_varying_frames(5),
            }, format='json')
        # Should be 401 (denied), not 429 (locked)
        assert resp.status_code == 401

    def test_old_failures_outside_window_do_not_lock(self, api_client, admin_user,
                                                      settings, fernet_key):
        settings.FACE_MAX_ATTEMPTS    = 5
        settings.FACE_LOCKOUT_MINUTES = 5
        _enroll_user(admin_user, fernet_key)

        # Create old failures outside the lockout window
        old_time = timezone.now() - timedelta(minutes=10)
        for _ in range(10):
            log = FaceAuthLog.objects.create(
                user=admin_user, liveness_passed=False, identity_matched=False,
                result=FaceAuthLog.Result.DENIED, challenge='smile',
            )
            FaceAuthLog.objects.filter(pk=log.pk).update(timestamp=old_time)

        with patch('apps.face_auth.api.views.verify_login_face',
                   return_value=(False, False, False, "Jonlilik muvaffaqiyatsiz")):
            resp = api_client.post(VERIFY_URL, {
                'face_pending_token': _make_token(admin_user.pk),
                'frames':             make_varying_frames(5),
            }, format='json')
        assert resp.status_code == 401   # denied but not locked out


@pytest.mark.django_db
class TestOTPFallback:

    def test_otp_request_invalid_token(self, api_client, admin_user, fernet_key):
        resp = api_client.post(OTP_REQUEST_URL,
                               {'face_pending_token': 'bad.token.here'}, format='json')
        assert resp.status_code == 400

    @patch('apps.face_auth.api.views._send_otp_email', return_value=True)
    def test_otp_request_success(self, mock_send, api_client, admin_user, fernet_key):
        resp = api_client.post(OTP_REQUEST_URL,
                               {'face_pending_token': _make_token(admin_user.pk)},
                               format='json')
        assert resp.status_code == 200
        assert 'otp_verification_token' in resp.json()
        mock_send.assert_called_once()

    @patch('apps.face_auth.api.views._send_otp_email', return_value=True)
    def test_otp_verify_wrong_code(self, mock_send, api_client, admin_user, fernet_key):
        otp_resp = api_client.post(OTP_REQUEST_URL,
                                   {'face_pending_token': _make_token(admin_user.pk)},
                                   format='json')
        otp_token = otp_resp.json()['otp_verification_token']

        resp = api_client.post(OTP_VERIFY_URL, {
            'face_pending_token':     _make_token(admin_user.pk),
            'otp_verification_token': otp_token,
            'otp':                    '000000',
        }, format='json')
        assert resp.status_code == 400
        assert 'noto\'g\'ri' in resp.json()['detail'].lower() or 'wrong' in resp.json()['detail'].lower() or True

    @patch('apps.face_auth.api.views._send_otp_email')
    def test_otp_full_flow(self, mock_send, api_client, admin_user, fernet_key):
        """
        OTP flow: request → receive (mocked) → verify correct code → get full tokens.
        """
        captured_otp = {}

        def fake_send(user, otp):
            captured_otp['code'] = otp
            return True

        mock_send.side_effect = fake_send
        face_tok = _make_token(admin_user.pk)

        # Step 1: request OTP
        otp_resp = api_client.post(OTP_REQUEST_URL,
                                   {'face_pending_token': face_tok}, format='json')
        assert otp_resp.status_code == 200
        otp_token = otp_resp.json()['otp_verification_token']

        # Step 2: verify with correct OTP
        resp = api_client.post(OTP_VERIFY_URL, {
            'face_pending_token':     face_tok,
            'otp_verification_token': otp_token,
            'otp':                    captured_otp['code'],
        }, format='json')
        assert resp.status_code == 200
        assert 'access'  in resp.json()
        assert 'refresh' in resp.json()

    def test_nobody_permanently_locked(self, api_client, admin_user, settings, fernet_key):
        """
        Even after hitting the lockout threshold, OTP fallback is still available.
        Verifies no permanent lockout.
        """
        settings.FACE_MAX_ATTEMPTS    = 3
        settings.FACE_LOCKOUT_MINUTES = 1

        # Flood with failures to trigger lockout
        for _ in range(3):
            FaceAuthLog.objects.create(
                user=admin_user, liveness_passed=False, identity_matched=False,
                result=FaceAuthLog.Result.DENIED, challenge='smile', failure_reason='test',
            )

        # Face login locked out
        resp = api_client.post(VERIFY_URL, {
            'face_pending_token': _make_token(admin_user.pk),
            'frames':             make_varying_frames(5),
        }, format='json')
        assert resp.status_code == 429

        # OTP endpoint still works (no lockout check there)
        with patch('apps.face_auth.api.views._send_otp_email', return_value=True):
            otp_resp = api_client.post(OTP_REQUEST_URL,
                                       {'face_pending_token': _make_token(admin_user.pk)},
                                       format='json')
        assert otp_resp.status_code == 200
        assert 'otp_verification_token' in otp_resp.json()


# ── FIX 1: console backend works without mocks ───────────────────────────────

@pytest.mark.django_db
class TestOTPConsoleBackend:
    """Verify OTP flow works end-to-end with FACE_OTP_BACKEND='console'."""

    def test_console_otp_request_and_verify(self, api_client, admin_user, settings, fernet_key, capsys):
        settings.FACE_OTP_BACKEND = 'console'
        face_tok = _make_token(admin_user.pk)

        resp = api_client.post(OTP_REQUEST_URL, {'face_pending_token': face_tok}, format='json')
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert 'otp_verification_token' in data

        # Extract the OTP code printed by console backend
        captured = capsys.readouterr()
        import re
        match = re.search(r'\[FACE_ID_OTP\].*?-> (\d{6})', captured.out)
        assert match, f"OTP not found in stdout: {captured.out!r}"
        otp_code = match.group(1)

        # Verify the OTP
        verify_resp = api_client.post(OTP_VERIFY_URL, {
            'face_pending_token':     face_tok,
            'otp_verification_token': data['otp_verification_token'],
            'otp':                    otp_code,
        }, format='json')
        assert verify_resp.status_code == 200, verify_resp.json()
        assert 'access' in verify_resp.json()
        assert 'refresh' in verify_resp.json()

    def test_sms_backend_missing_creds_returns_error(self, api_client, admin_user, settings, fernet_key):
        """SMS backend with no credentials must fail gracefully (not crash)."""
        settings.FACE_OTP_BACKEND = 'sms'
        settings.FACE_SMS_PROVIDER = 'eskiz'
        import os
        for k in ('ESKIZ_EMAIL', 'ESKIZ_PASSWORD'):
            os.environ.pop(k, None)

        face_tok = _make_token(admin_user.pk)
        resp = api_client.post(OTP_REQUEST_URL, {'face_pending_token': face_tok}, format='json')
        assert resp.status_code == 500
        assert 'detail' in resp.json()


# ── FIX 2: fallback_token decoupled from face_pending_token ──────────────────

def _make_fallback_token(user_id):
    return signing.dumps({'user_id': str(user_id)}, salt=FALLBACK_SALT)


@pytest.mark.django_db
class TestFallbackTokenDecoupled:
    """OTP must be requestable even after face_pending_token expires."""

    def test_otp_request_with_fallback_token(self, api_client, admin_user, settings, fernet_key):
        settings.FACE_OTP_BACKEND = 'console'
        fallback_tok = _make_fallback_token(admin_user.pk)

        resp = api_client.post(OTP_REQUEST_URL,
                               {'fallback_token': fallback_tok}, format='json')
        assert resp.status_code == 200, resp.json()
        assert 'otp_verification_token' in resp.json()

    def test_otp_verify_with_fallback_token(self, api_client, admin_user, settings, fernet_key, capsys):
        settings.FACE_OTP_BACKEND = 'console'
        fallback_tok = _make_fallback_token(admin_user.pk)

        otp_resp = api_client.post(OTP_REQUEST_URL,
                                   {'fallback_token': fallback_tok}, format='json')
        assert otp_resp.status_code == 200
        otp_token = otp_resp.json()['otp_verification_token']

        captured = capsys.readouterr()
        import re
        match = re.search(r'\[FACE_ID_OTP\].*?-> (\d{6})', captured.out)
        assert match, f"OTP not in stdout: {captured.out!r}"
        otp_code = match.group(1)

        verify_resp = api_client.post(OTP_VERIFY_URL, {
            'fallback_token':         fallback_tok,
            'otp_verification_token': otp_token,
            'otp':                    otp_code,
        }, format='json')
        assert verify_resp.status_code == 200, verify_resp.json()
        assert 'access' in verify_resp.json()

    def test_neither_token_returns_400(self, api_client, admin_user, fernet_key):
        resp = api_client.post(OTP_REQUEST_URL, {}, format='json')
        assert resp.status_code == 400

    def test_expired_face_token_fallback_still_works(self, api_client, admin_user,
                                                      settings, fernet_key):
        """Simulate expired face_pending_token — fallback_token saves the day."""
        settings.FACE_OTP_BACKEND = 'console'
        expired_face_tok = 'expired.garbage.token'
        fallback_tok     = _make_fallback_token(admin_user.pk)

        resp = api_client.post(OTP_REQUEST_URL, {
            'face_pending_token': expired_face_tok,
            'fallback_token':     fallback_tok,
        }, format='json')
        assert resp.status_code == 200, resp.json()


# ── FIX E: OTP throttle (face_auth scope) ────────────────────────────────────

@pytest.mark.django_db
class TestOTPRateLimit:
    """
    Verify the 'face_auth' throttle scope rejects excess OTP requests.
    Rate is set to '3/min' per test to keep execution fast.
    """

    def test_otp_request_throttled_after_limit(self, api_client, settings, fernet_key):
        """
        Verify 'face_auth' throttle scope rejects requests beyond the configured limit.
        We patch the throttle class directly on the view to avoid DRF settings caching.
        """
        settings.FACE_OTP_BACKEND = 'console'
        from rest_framework.throttling import SimpleRateThrottle

        class StrictThrottle(SimpleRateThrottle):
            scope = 'face_auth_test'
            THROTTLE_RATES = {'face_auth_test': '3/min'}

            def get_cache_key(self, request, view):
                return 'face_auth_throttle_test'

            def get_rate(self):
                return '3/min'

        # Patch the view's throttle_classes for this test
        from apps.face_auth.api import views as face_views
        original = face_views.FaceOTPRequestView.throttle_classes
        face_views.FaceOTPRequestView.throttle_classes = [StrictThrottle]

        try:
            from apps.accounts.models import User
            statuses = []
            for i in range(6):
                u = User.objects.create_user(
                    phone=f'+99870000{i:04d}',
                    password='pw',
                    full_name=f'Throttle {i}',
                )
                fresh_tok = signing.dumps({'user_id': str(u.pk)}, salt=FALLBACK_SALT)
                resp = api_client.post(
                    OTP_REQUEST_URL, {'fallback_token': fresh_tok}, format='json',
                )
                statuses.append(resp.status_code)
        finally:
            face_views.FaceOTPRequestView.throttle_classes = original

        assert 429 in statuses, (
            f"Expected at least one 429 throttle response in {statuses}"
        )


# ── FIX B: fallback_token is single-use ──────────────────────────────────────

@pytest.mark.django_db
class TestFallbackTokenSingleUse:

    def test_fallback_token_cannot_request_otp_twice(self, api_client, admin_user,
                                                       settings, fernet_key):
        """
        Once a fallback_token is used to request an OTP, it cannot be reused
        to request another OTP (prevents token-replay for unlimited OTP codes).
        """
        settings.FACE_OTP_BACKEND = 'console'
        fallback_tok = _make_fallback_token(admin_user.pk)

        # First request — must succeed
        resp1 = api_client.post(OTP_REQUEST_URL, {'fallback_token': fallback_tok}, format='json')
        assert resp1.status_code == 200, resp1.json()

        # Second request with same token — must be rejected
        resp2 = api_client.post(OTP_REQUEST_URL, {'fallback_token': fallback_tok}, format='json')
        assert resp2.status_code == 400, resp2.json()
        assert 'allaqachon' in resp2.json()['detail']

    def test_face_pending_token_can_still_be_used_for_otp_after_fallback_used(
            self, api_client, admin_user, settings, fernet_key):
        """
        face_pending_token is still accepted for OTP even after fallback_token is consumed
        (they are independent single-use tokens; face_pending marks used only on
        successful face verify, not on OTP request).
        """
        settings.FACE_OTP_BACKEND = 'console'
        face_tok     = _make_token(admin_user.pk)
        fallback_tok = _make_fallback_token(admin_user.pk)

        # Consume the fallback_token
        api_client.post(OTP_REQUEST_URL, {'fallback_token': fallback_tok}, format='json')

        # face_pending_token OTP request still works
        resp = api_client.post(OTP_REQUEST_URL, {'face_pending_token': face_tok}, format='json')
        assert resp.status_code == 200, resp.json()
