"""
Pluggable OTP sender for Face ID fallback.

Backend chosen by FACE_OTP_BACKEND setting (or env var):
  "console"  — logs the code to stdout/logger (dev default, no creds needed)
  "sms"      — Eskiz/Playmobile SMS API (Uzbekistan), sends to user.phone
  "telegram" — Telegram Bot API, sends to user's Telegram chat

Required env vars by backend:
  console:  (none)
  sms:      ESKIZ_EMAIL, ESKIZ_PASSWORD  (Eskiz)
              or
            PLAYMOBILE_LOGIN, PLAYMOBILE_PASSWORD, PLAYMOBILE_ORIGINATOR  (Playmobile)
            FACE_SMS_PROVIDER = "eskiz" | "playmobile"  (default: eskiz)
  telegram: TELEGRAM_BOT_TOKEN, FACE_TG_CHAT_ID_FIELD
            (FACE_TG_CHAT_ID_FIELD = User model attribute that holds the chat id)
"""
import logging

logger = logging.getLogger('apps.face_auth')

try:
    import requests as _requests  # type: ignore
except ImportError:
    _requests = None  # type: ignore

# Re-export at module level so tests can patch 'apps.face_auth.services.otp.requests'
requests = _requests


def send_otp(user, code: str) -> bool:
    """
    Dispatch OTP `code` to `user` via the configured backend.
    Returns True on success, False on failure.
    """
    from django.conf import settings
    backend = getattr(settings, 'FACE_OTP_BACKEND', 'console').lower()

    if backend == 'console':
        return _send_console(user, code)
    if backend == 'sms':
        return _send_sms(user, code)
    if backend == 'telegram':
        return _send_telegram(user, code)

    logger.error("Noma'lum FACE_OTP_BACKEND: %s. 'console', 'sms', 'telegram' dan biri", backend)
    return False


# ── console ───────────────────────────────────────────────────────────────────

def _send_console(user, code: str) -> bool:
    """Dev backend: just log the code. Always succeeds."""
    logger.info(
        "=== FACE ID OTP (console backend) ===\n"
        "  Foydalanuvchi : %s (%s)\n"
        "  Telefon       : %s\n"
        "  Kod           : %s\n"
        "=====================================",
        user.full_name, user.pk, getattr(user, 'phone', '—'), code,
    )
    print(
        f"\n[FACE_ID_OTP] {user.full_name} ({getattr(user,'phone','')}) -> {code}\n"
    )
    return True


# ── SMS (Eskiz / Playmobile) ──────────────────────────────────────────────────

def _send_sms(user, code: str) -> bool:
    from django.conf import settings
    phone = getattr(user, 'phone', '') or ''
    if not phone:
        logger.warning("OTP SMS: telefon raqam topilmadi, user=%s", user.pk)
        return False

    provider = getattr(settings, 'FACE_SMS_PROVIDER', 'eskiz').lower()
    if provider == 'eskiz':
        return _send_eskiz(phone, code, settings)
    if provider == 'playmobile':
        return _send_playmobile(phone, code, settings)

    logger.error("Noma'lum FACE_SMS_PROVIDER: %s", provider)
    return False


def _send_eskiz(phone: str, code: str, settings) -> bool:
    """
    Eskiz.uz SMS API.
    Docs: https://eskiz.uz/api
    """
    import os
    if requests is None:
        logger.error("'requests' kutubxonasi o'rnatilmagan (pip install requests)")
        return False

    email    = os.environ.get('ESKIZ_EMAIL',    '')
    password = os.environ.get('ESKIZ_PASSWORD', '')
    if not email or not password:
        logger.error("ESKIZ_EMAIL / ESKIZ_PASSWORD muhit o'zgaruvchilari topilmadi")
        return False

    # Step 1: get token
    try:
        auth = requests.post(
            'https://notify.eskiz.uz/api/auth/login',
            data={'email': email, 'password': password},
            timeout=10,
        )
        auth.raise_for_status()
        token = auth.json()['data']['token']
    except Exception as exc:
        logger.error("Eskiz autentifikatsiya xatosi: %s", exc)
        return False

    # Step 2: send
    msg = f"VLT.erp Face ID kodingiz: {code}\nKod 10 daqiqa amal qiladi."
    try:
        resp = requests.post(
            'https://notify.eskiz.uz/api/message/sms/send',
            headers={'Authorization': f'Bearer {token}'},
            data={
                'mobile_phone': phone.lstrip('+'),
                'message':      msg,
                'from':         '4546',
            },
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Eskiz SMS yuborildi: user=%s phone=%s", 'n/a', phone)
        return True
    except Exception as exc:
        logger.error("Eskiz SMS xatosi: %s", exc)
        return False


def _send_playmobile(phone: str, code: str, settings) -> bool:
    """
    Playmobile SMS API.
    Docs: https://playmobile.uz/api
    """
    import os, json
    if requests is None:
        logger.error("'requests' kutubxonasi o'rnatilmagan")
        return False

    login      = os.environ.get('PLAYMOBILE_LOGIN',      '')
    password   = os.environ.get('PLAYMOBILE_PASSWORD',   '')
    originator = os.environ.get('PLAYMOBILE_ORIGINATOR', 'VLT.erp')
    if not login or not password:
        logger.error("PLAYMOBILE_LOGIN / PLAYMOBILE_PASSWORD topilmadi")
        return False

    msg = f"VLT.erp Face ID: {code} (10 daqiqa)"
    try:
        resp = requests.post(
            'https://send.smsxabar.uz/broker-api/send',
            auth=(login, password),
            json={
                'messages': [{
                    'recipient': phone.lstrip('+'),
                    'message-id': f'faceid_{phone}',
                    'sms': {'originator': originator, 'content': {'text': msg}},
                }]
            },
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Playmobile SMS yuborildi: phone=%s", phone)
        return True
    except Exception as exc:
        logger.error("Playmobile SMS xatosi: %s", exc)
        return False


# ── Telegram ──────────────────────────────────────────────────────────────────

def _send_telegram(user, code: str) -> bool:
    """
    Telegram Bot API.
    Requires:
      TELEGRAM_BOT_TOKEN     — already in project settings
      FACE_TG_CHAT_ID_FIELD  — name of User model field holding the Telegram chat_id
    """
    import os
    from django.conf import settings as djsettings

    bot_token  = os.environ.get('TELEGRAM_BOT_TOKEN', '') or getattr(djsettings, 'TELEGRAM_BOT_TOKEN', '')
    chat_field = os.environ.get('FACE_TG_CHAT_ID_FIELD', 'telegram_chat_id')
    chat_id    = getattr(user, chat_field, None)

    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN topilmadi")
        return False
    if not chat_id:
        logger.warning(
            "Foydalanuvchida Telegram chat_id yo'q (maydon: '%s' User modelida topilmadi), user=%s",
            chat_field, user.pk,
        )
        return False

    if requests is None:
        logger.error("'requests' kutubxonasi o'rnatilmagan")
        return False

    msg = (
        f"🔐 *VLT.erp Face ID zaxira kodi*\n\n"
        f"Kodingiz: `{code}`\n\n"
        f"Bu kod 10 daqiqa amal qiladi."
    )
    try:
        resp = requests.post(
            f'https://api.telegram.org/bot{bot_token}/sendMessage',
            json={'chat_id': chat_id, 'text': msg, 'parse_mode': 'Markdown'},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Telegram OTP yuborildi: user=%s", user.pk)
        return True
    except Exception as exc:
        logger.error("Telegram xatosi: %s", exc)
        return False
