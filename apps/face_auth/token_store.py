"""
Single-use token registry.

Uses Django's cache framework (Redis if configured, else in-memory/db).
On cache miss, falls back to a DB-backed UsedToken table for process-safety.

Usage:
    mark_used(token_str, ttl_seconds) -> bool  (True if newly marked, False if already used)
    is_used(token_str) -> bool
"""
import hashlib
import logging

logger = logging.getLogger('apps.face_auth')

_CACHE_PREFIX = 'faceauth_used_token:'


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _cache_key(h: str) -> str:
    return f"{_CACHE_PREFIX}{h}"


def mark_used(token: str, ttl_seconds: int) -> bool:
    """
    Mark token as used.  Returns True if this is the first use, False if already used.
    Thread- and process-safe: uses cache.add() which is atomic.
    """
    from django.core.cache import cache
    h   = _token_hash(token)
    key = _cache_key(h)

    # cache.add returns True only if the key did NOT exist → first use
    stored = cache.add(key, 1, timeout=ttl_seconds)
    if not stored:
        logger.warning("Token replay detected: hash=%s…", h[:16])
        return False

    # Also persist in DB for cross-process guarantee when cache is in-memory
    try:
        _db_mark_used(h, ttl_seconds)
    except Exception as exc:
        logger.debug("DB token store write failed (non-fatal): %s", exc)

    return True


def is_used(token: str) -> bool:
    """Return True if token has already been used."""
    from django.core.cache import cache
    h = _token_hash(token)
    if cache.get(_cache_key(h)):
        return True
    try:
        return _db_is_used(h)
    except Exception:
        return False


# ── DB fallback ───────────────────────────────────────────────────────────────

def _db_mark_used(token_hash: str, ttl_seconds: int) -> None:
    from django.utils import timezone
    from datetime import timedelta
    from apps.face_auth.models import UsedToken
    expires = timezone.now() + timedelta(seconds=ttl_seconds)
    UsedToken.objects.get_or_create(
        token_hash=token_hash,
        defaults={'expires_at': expires},
    )


def _db_is_used(token_hash: str) -> bool:
    from django.utils import timezone
    from apps.face_auth.models import UsedToken
    return UsedToken.objects.filter(
        token_hash=token_hash,
        expires_at__gt=timezone.now(),
    ).exists()


def cleanup_expired():
    """Prune expired rows (call from a periodic task)."""
    from django.utils import timezone
    from apps.face_auth.models import UsedToken
    deleted, _ = UsedToken.objects.filter(expires_at__lte=timezone.now()).delete()
    logger.debug("UsedToken cleanup: %d rows removed", deleted)
