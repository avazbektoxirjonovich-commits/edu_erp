"""
Unit tests for OTP backends (FIX C).

All HTTP calls are MOCKED — no real SMS or Telegram API is called.
Tests verify:
  - correct URL, payload structure, recipient field (phone / chat_id)
  - graceful handling of HTTP errors (server 500, connection refused)
  - missing-credential cases return False (no crash)
  - missing Telegram chat_id field returns False (no crash)
"""
import os
import pytest
from unittest.mock import patch, MagicMock


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_user(admin_user):
    """admin_user already has .phone; add telegram_chat_id for Telegram tests."""
    admin_user.telegram_chat_id = 987654321
    return admin_user


@pytest.fixture
def mock_user_no_tg(admin_user):
    """User without Telegram chat_id attribute."""
    # Ensure the attribute does NOT exist
    if hasattr(admin_user, 'telegram_chat_id'):
        del admin_user.telegram_chat_id
    return admin_user


def _mock_resp(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        from requests.exceptions import HTTPError
        resp.raise_for_status.side_effect = HTTPError(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


# ── Console backend ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestConsoleBackend:

    def test_console_always_returns_true(self, admin_user, capsys):
        from apps.face_auth.services.otp import _send_console
        result = _send_console(admin_user, '123456')
        assert result is True

    def test_console_prints_code(self, admin_user, capsys):
        from apps.face_auth.services.otp import _send_console
        _send_console(admin_user, '999888')
        captured = capsys.readouterr()
        assert '999888' in captured.out


# ── SMS / Eskiz backend ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestEskizBackend:

    def _set_env(self, monkeypatch):
        monkeypatch.setenv('ESKIZ_EMAIL',    'test@example.com')
        monkeypatch.setenv('ESKIZ_PASSWORD', 'secret')

    def test_eskiz_sends_to_user_phone(self, admin_user, monkeypatch, settings):
        """Eskiz must call the SMS send endpoint with the user's phone number."""
        self._set_env(monkeypatch)
        settings.FACE_OTP_BACKEND  = 'sms'
        settings.FACE_SMS_PROVIDER = 'eskiz'

        auth_resp = _mock_resp(200, {'data': {'token': 'tok123'}})
        send_resp = _mock_resp(200, {'status': 'ok'})

        with patch('apps.face_auth.services.otp.requests') as mock_req:
            mock_req.post.side_effect = [auth_resp, send_resp]
            from apps.face_auth.services.otp import _send_eskiz
            result = _send_eskiz(admin_user.phone, '112233', settings)

        assert result is True
        calls = mock_req.post.call_args_list
        # First call: auth
        assert 'auth/login' in calls[0][0][0]
        # Second call: message/sms/send — must contain the phone number
        send_call_kwargs = calls[1]
        data_sent = send_call_kwargs[1].get('data') or send_call_kwargs[0][1] if len(calls[1][0]) > 1 else {}
        # The phone is passed as data kwarg
        assert admin_user.phone.lstrip('+') in str(send_call_kwargs)

    def test_eskiz_missing_credentials_returns_false(self, admin_user, monkeypatch, settings):
        monkeypatch.delenv('ESKIZ_EMAIL',    raising=False)
        monkeypatch.delenv('ESKIZ_PASSWORD', raising=False)
        settings.FACE_OTP_BACKEND  = 'sms'
        settings.FACE_SMS_PROVIDER = 'eskiz'
        from apps.face_auth.services.otp import _send_eskiz
        result = _send_eskiz(admin_user.phone, '000000', settings)
        assert result is False

    def test_eskiz_http_error_returns_false(self, admin_user, monkeypatch, settings):
        """If Eskiz API returns 500, must return False without crashing."""
        self._set_env(monkeypatch)
        auth_resp = _mock_resp(200, {'data': {'token': 'tok123'}})
        send_resp = _mock_resp(500)

        with patch('apps.face_auth.services.otp.requests') as mock_req:
            mock_req.post.side_effect = [auth_resp, send_resp]
            from apps.face_auth.services.otp import _send_eskiz
            result = _send_eskiz(admin_user.phone, '112233', settings)

        assert result is False

    def test_eskiz_auth_failure_returns_false(self, admin_user, monkeypatch, settings):
        self._set_env(monkeypatch)
        auth_resp = _mock_resp(401)
        with patch('apps.face_auth.services.otp.requests') as mock_req:
            mock_req.post.return_value = auth_resp
            from apps.face_auth.services.otp import _send_eskiz
            result = _send_eskiz(admin_user.phone, '112233', settings)
        assert result is False


# ── SMS / Playmobile backend ──────────────────────────────────────────────────

@pytest.mark.django_db
class TestPlaymobileBackend:

    def _set_env(self, monkeypatch):
        monkeypatch.setenv('PLAYMOBILE_LOGIN',      'pmuser')
        monkeypatch.setenv('PLAYMOBILE_PASSWORD',   'pmpass')
        monkeypatch.setenv('PLAYMOBILE_ORIGINATOR', 'VLT.erp')

    def test_playmobile_sends_to_user_phone(self, admin_user, monkeypatch, settings):
        """Playmobile must POST to its broker API with the user's phone."""
        self._set_env(monkeypatch)
        settings.FACE_OTP_BACKEND  = 'sms'
        settings.FACE_SMS_PROVIDER = 'playmobile'

        ok_resp = _mock_resp(200, {'status': 'ok'})
        with patch('apps.face_auth.services.otp.requests') as mock_req:
            mock_req.post.return_value = ok_resp
            from apps.face_auth.services.otp import _send_playmobile
            result = _send_playmobile(admin_user.phone, '445566', settings)

        assert result is True
        call_kwargs = mock_req.post.call_args
        # URL must be Playmobile broker
        assert 'broker-api/send' in call_kwargs[0][0]
        # Payload must contain the phone number
        json_sent = call_kwargs[1].get('json', {})
        messages  = json_sent.get('messages', [{}])
        assert messages[0]['recipient'] == admin_user.phone.lstrip('+')

    def test_playmobile_missing_credentials_returns_false(self, admin_user, monkeypatch, settings):
        monkeypatch.delenv('PLAYMOBILE_LOGIN',    raising=False)
        monkeypatch.delenv('PLAYMOBILE_PASSWORD', raising=False)
        settings.FACE_SMS_PROVIDER = 'playmobile'
        from apps.face_auth.services.otp import _send_playmobile
        result = _send_playmobile(admin_user.phone, '000000', settings)
        assert result is False

    def test_playmobile_http_500_returns_false(self, admin_user, monkeypatch, settings):
        self._set_env(monkeypatch)
        bad_resp = _mock_resp(500)
        with patch('apps.face_auth.services.otp.requests') as mock_req:
            mock_req.post.return_value = bad_resp
            from apps.face_auth.services.otp import _send_playmobile
            result = _send_playmobile(admin_user.phone, '445566', settings)
        assert result is False


# ── Telegram backend ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTelegramBackend:

    def _set_env(self, monkeypatch):
        monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'bot123:ABC')

    def test_telegram_sends_to_correct_chat_id(self, mock_user, monkeypatch, settings):
        """Telegram backend must POST to the bot API with the user's chat_id."""
        self._set_env(monkeypatch)
        ok_resp = _mock_resp(200, {'ok': True})

        with patch('apps.face_auth.services.otp.requests') as mock_req:
            mock_req.post.return_value = ok_resp
            from apps.face_auth.services.otp import _send_telegram
            result = _send_telegram(mock_user, '778899')

        assert result is True
        call_args = mock_req.post.call_args
        url = call_args[0][0]
        assert 'api.telegram.org' in url
        assert 'bot123:ABC' in url
        assert 'sendMessage' in url
        json_data = call_args[1].get('json', {})
        assert json_data['chat_id'] == mock_user.telegram_chat_id

    def test_telegram_missing_chat_id_returns_false(self, mock_user_no_tg, monkeypatch):
        """If User has no telegram_chat_id attribute, return False without crashing."""
        self._set_env(monkeypatch)
        from apps.face_auth.services.otp import _send_telegram
        result = _send_telegram(mock_user_no_tg, '778899')
        assert result is False

    def test_telegram_missing_bot_token_returns_false(self, mock_user, monkeypatch, settings):
        monkeypatch.delenv('TELEGRAM_BOT_TOKEN', raising=False)
        settings.TELEGRAM_BOT_TOKEN = ''   # also clear from Django settings
        from apps.face_auth.services.otp import _send_telegram
        result = _send_telegram(mock_user, '778899')
        assert result is False

    def test_telegram_http_error_returns_false(self, mock_user, monkeypatch):
        """If Telegram API call fails (network/server), return False without crashing."""
        self._set_env(monkeypatch)
        bad_resp = _mock_resp(400, {'ok': False, 'description': 'Bad Request'})
        with patch('apps.face_auth.services.otp.requests') as mock_req:
            mock_req.post.return_value = bad_resp
            from apps.face_auth.services.otp import _send_telegram
            result = _send_telegram(mock_user, '778899')
        assert result is False

    def test_telegram_connection_error_returns_false(self, mock_user, monkeypatch):
        """Network error (ConnectionError) must return False, never raise."""
        self._set_env(monkeypatch)
        with patch('apps.face_auth.services.otp.requests') as mock_req:
            mock_req.post.side_effect = ConnectionError("connection refused")
            from apps.face_auth.services.otp import _send_telegram
            result = _send_telegram(mock_user, '778899')
        assert result is False
