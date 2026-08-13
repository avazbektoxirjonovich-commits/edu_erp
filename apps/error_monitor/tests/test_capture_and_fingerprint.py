"""
Error Monitor — capture, grouping (fingerprinting), and sanitization.
"""
import pytest

from apps.error_monitor.capture import capture_exception
from apps.error_monitor.fingerprint import (
    compute_severity,
    normalize_for_fingerprint,
    sanitize_message,
)
from apps.error_monitor.models import ErrorEvent, ErrorOccurrence


def _raise_and_capture(**kwargs):
    try:
        raise ValueError(kwargs.pop('message', 'boom'))
    except ValueError as exc:
        return capture_exception(exc, **kwargs)


@pytest.mark.django_db
class TestGrouping:

    def test_identical_errors_group_into_one_event(self):
        _raise_and_capture(endpoint='/api/v1/students/1/', method='GET', status_code=500)
        _raise_and_capture(endpoint='/api/v1/students/1/', method='GET', status_code=500)
        _raise_and_capture(endpoint='/api/v1/students/1/', method='GET', status_code=500)

        assert ErrorEvent.objects.count() == 1
        event = ErrorEvent.objects.first()
        assert event.occurrence_count == 3
        assert ErrorOccurrence.objects.filter(error_event=event).count() == 3

    def test_errors_differing_only_by_numeric_id_still_group(self):
        """'Student 123 not found' and 'Student 456 not found' must
        fingerprint identically — the whole point of grouping."""
        _raise_and_capture(message='Student 123 not found', endpoint='/api/v1/students/123/', status_code=404)
        # different numeric id AND different endpoint id — normalize_for_fingerprint
        # collapses digits in both the message and (via caller) endpoint stays
        # constant in this test to isolate the message-normalization behavior
        _raise_and_capture(message='Student 456 not found', endpoint='/api/v1/students/123/', status_code=404)

        assert ErrorEvent.objects.count() == 1
        assert ErrorEvent.objects.first().occurrence_count == 2

    def test_different_error_types_never_group(self):
        try:
            raise ValueError('boom')
        except ValueError as exc:
            capture_exception(exc, endpoint='/x/', status_code=500)
        try:
            raise TypeError('boom')
        except TypeError as exc:
            capture_exception(exc, endpoint='/x/', status_code=500)

        assert ErrorEvent.objects.count() == 2

    def test_different_endpoints_never_group(self):
        _raise_and_capture(endpoint='/api/v1/a/', status_code=500)
        _raise_and_capture(endpoint='/api/v1/b/', status_code=500)
        assert ErrorEvent.objects.count() == 2

    def test_no_hundreds_of_duplicate_rows_for_repeated_error(self):
        for _ in range(50):
            _raise_and_capture(endpoint='/api/v1/hot-path/', status_code=500)
        assert ErrorEvent.objects.count() == 1
        assert ErrorEvent.objects.first().occurrence_count == 50
        assert ErrorOccurrence.objects.count() == 50


@pytest.mark.django_db
class TestOccurrenceDetail:

    def test_occurrence_records_user_role_and_request_metadata(self, student_user):
        event = _raise_and_capture(
            user=student_user, endpoint='/api/v1/x/', method='POST',
            page='/student/', status_code=500,
        )
        occ = event.occurrences.first()
        assert occ.user == student_user
        assert occ.user_role == 'student'
        assert occ.method == 'POST'
        assert occ.page == '/student/'
        assert occ.request_id  # a UUID was generated
        assert occ.stack_trace  # real traceback captured

    def test_anonymous_capture_has_no_user(self):
        event = _raise_and_capture(user=None, endpoint='/api/v1/x/', status_code=500)
        occ = event.occurrences.first()
        assert occ.user is None
        assert occ.user_role == ''

    def test_capture_never_raises_even_on_internal_failure(self, monkeypatch):
        """The observability layer must never crash the request it's
        observing — verified by breaking capture internals and confirming
        no exception propagates."""
        import apps.error_monitor.capture as capture_mod

        def broken_fingerprint(*a, **kw):
            raise RuntimeError('fingerprinting itself is broken')

        monkeypatch.setattr(capture_mod, 'compute_fingerprint', broken_fingerprint)
        try:
            raise ValueError('boom')
        except ValueError as exc:
            result = capture_exception(exc, endpoint='/x/', status_code=500)
        assert result is None  # failed gracefully, did not raise


class TestSanitization:

    def test_bearer_token_redacted(self):
        text = "Auth failed: Bearer sk-ant-api03-abc123XYZ.token-part"
        out = sanitize_message(text)
        assert 'sk-ant-api03-abc123XYZ' not in out
        assert '[REDACTED]' in out

    def test_password_field_redacted(self):
        text = 'IntegrityError: password="SuperSecret123" already exists'
        out = sanitize_message(text)
        assert 'SuperSecret123' not in out

    def test_api_key_field_redacted(self):
        text = "ValueError: api_key=sk-ant-abc123 is invalid"
        out = sanitize_message(text)
        assert 'sk-ant-abc123' not in out

    def test_ordinary_message_untouched_in_meaning(self):
        text = "O'quvchi topilmadi"
        assert sanitize_message(text) == text

    def test_message_capped_in_length(self):
        out = sanitize_message('x' * 5000)
        assert len(out) <= 2000


class TestFingerprintNormalization:

    def test_uuid_collapsed(self):
        a = normalize_for_fingerprint('Student 3fa85f64-5717-4562-b3fc-2c963f66afa6 not found')
        b = normalize_for_fingerprint('Student 9c858901-8a57-4791-81fe-4c455b099bc9 not found')
        assert a == b

    def test_numbers_collapsed(self):
        a = normalize_for_fingerprint('Row 123 failed')
        b = normalize_for_fingerprint('Row 999999 failed')
        assert a == b


class TestSeverity:

    def test_5xx_or_unknown_is_critical(self):
        assert compute_severity(500) == ErrorEvent.Severity.CRITICAL
        assert compute_severity(503) == ErrorEvent.Severity.CRITICAL
        assert compute_severity(None) == ErrorEvent.Severity.CRITICAL

    def test_401_403_is_high(self):
        assert compute_severity(401) == ErrorEvent.Severity.HIGH
        assert compute_severity(403) == ErrorEvent.Severity.HIGH

    def test_other_4xx_is_medium(self):
        assert compute_severity(400) == ErrorEvent.Severity.MEDIUM
        assert compute_severity(404) == ErrorEvent.Severity.MEDIUM

    def test_below_400_is_low(self):
        assert compute_severity(200) == ErrorEvent.Severity.LOW
