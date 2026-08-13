"""
Error Monitor — Fingerprinting & sanitization
================================================
A stable fingerprint groups repeated identical errors into one ErrorEvent
instead of creating a new row per occurrence. Two errors that differ only by
an ID/number in the message (e.g. "Student 123 not found" vs "Student 456
not found") normalize to the same fingerprint.
"""
from __future__ import annotations

import hashlib
import re

_UUID_RE = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
_NUM_RE = re.compile(r'\d+')

# Defense-in-depth: strip anything that looks like a credential before it is
# ever persisted, even though secrets should not normally appear in an
# exception message or traceback.
_SECRET_PATTERNS = [
    re.compile(r'(?i)(bearer\s+)[A-Za-z0-9\-_.]+'),
    re.compile(r'(?i)((?:api[_-]?key|password|secret|token)["\']?\s*[:=]\s*["\']?)[^"\'\s,}]+'),
]


def sanitize_message(text: str) -> str:
    """Redact anything credential-shaped and cap length before storage."""
    if not text:
        return ''
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r'\1[REDACTED]', text)
    return text[:2000]


def normalize_for_fingerprint(text: str) -> str:
    """Collapse IDs/numbers so equivalent errors share one fingerprint."""
    text = _UUID_RE.sub('<id>', text)
    text = _NUM_RE.sub('<n>', text)
    return text[:300]


def compute_fingerprint(error_type: str, endpoint: str, normalized_message: str) -> str:
    raw = f"{error_type}:{endpoint}:{normalized_message}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


def compute_severity(status_code: int | None) -> str:
    """Deterministic severity from HTTP status only — no heuristic guessing."""
    from apps.error_monitor.models import ErrorEvent

    if status_code is None or status_code >= 500:
        return ErrorEvent.Severity.CRITICAL
    if status_code in (401, 403):
        return ErrorEvent.Severity.HIGH
    if 400 <= status_code < 500:
        return ErrorEvent.Severity.MEDIUM
    return ErrorEvent.Severity.LOW
