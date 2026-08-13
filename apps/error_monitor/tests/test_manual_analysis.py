"""
Error Monitor — manual AI analysis.

The core requirement under test: Claude is called for error analysis ONLY
when a developer explicitly POSTs to the analyze endpoint — never
automatically from capture, listing, stats, or status changes.
"""
import json
from unittest.mock import patch

import pytest

from apps.error_monitor.capture import capture_exception
from apps.error_monitor.tests.conftest import auth_client


def _seed_error(**kwargs):
    try:
        raise ValueError('seeded error for analysis')
    except ValueError as exc:
        return capture_exception(exc, endpoint='/api/v1/x/', status_code=500, **kwargs)


FAKE_ANALYSIS_JSON = json.dumps({
    'probable_cause': 'Null qiymat tekshirilmagan',
    'affected_module': 'apps.students',
    'severity': 'critical',
    'reproduction_steps': '1. ...',
    'recommended_fix': 'None check qo\'shish',
    'possible_side_effects': "Yo'q",
    'testing_recommendations': 'Unit test qo\'shish',
})


@pytest.mark.django_db
class TestManualAnalysisIsExplicitOnly:

    def test_capturing_an_error_never_calls_claude(self):
        with patch('apps.vlt_ai.services.llm_client.llm_client.simple_complete') as mock_llm:
            _seed_error()
        mock_llm.assert_not_called()

    def test_capturing_many_errors_never_calls_claude(self):
        with patch('apps.vlt_ai.services.llm_client.llm_client.simple_complete') as mock_llm:
            for _ in range(10):
                _seed_error()
        mock_llm.assert_not_called()

    def test_listing_errors_never_calls_claude(self, developer_user):
        _seed_error()
        with patch('apps.vlt_ai.services.llm_client.llm_client.simple_complete') as mock_llm:
            client = auth_client(developer_user)
            client.get('/api/v1/error-monitor/errors/')
        mock_llm.assert_not_called()

    def test_viewing_stats_never_calls_claude(self, developer_user):
        _seed_error()
        with patch('apps.vlt_ai.services.llm_client.llm_client.simple_complete') as mock_llm:
            client = auth_client(developer_user)
            client.get('/api/v1/error-monitor/stats/')
        mock_llm.assert_not_called()

    def test_changing_status_never_calls_claude(self, developer_user):
        event = _seed_error()
        with patch('apps.vlt_ai.services.llm_client.llm_client.simple_complete') as mock_llm:
            client = auth_client(developer_user)
            client.patch(f'/api/v1/error-monitor/errors/{event.id}/status/',
                          {'status': 'investigating'}, format='json')
        mock_llm.assert_not_called()

    def test_developer_click_does_call_claude_exactly_once(self, developer_user):
        event = _seed_error()
        with patch('apps.vlt_ai.services.llm_client.llm_client.simple_complete',
                    return_value=FAKE_ANALYSIS_JSON) as mock_llm:
            client = auth_client(developer_user)
            resp = client.post(f'/api/v1/error-monitor/errors/{event.id}/analyze/')

        assert resp.status_code == 200
        mock_llm.assert_called_once()

    def test_non_developer_cannot_trigger_analysis(self, admin_user):
        event = _seed_error()
        with patch('apps.vlt_ai.services.llm_client.llm_client.simple_complete') as mock_llm:
            client = auth_client(admin_user)
            resp = client.post(f'/api/v1/error-monitor/errors/{event.id}/analyze/')
        assert resp.status_code == 403
        mock_llm.assert_not_called()


@pytest.mark.django_db
class TestManualAnalysisContentAndCaching:

    def test_analysis_result_is_cached_on_the_event(self, developer_user):
        event = _seed_error()
        with patch('apps.vlt_ai.services.llm_client.llm_client.simple_complete',
                    return_value=FAKE_ANALYSIS_JSON):
            client = auth_client(developer_user)
            client.post(f'/api/v1/error-monitor/errors/{event.id}/analyze/')

        event.refresh_from_db()
        assert event.ai_analysis['probable_cause'] == 'Null qiymat tekshirilmagan'
        assert event.ai_analyzed_at is not None
        assert event.ai_analyzed_by == developer_user

    def test_analysis_sends_only_this_error_not_other_users_data(self, developer_user, student_user):
        """The prompt sent to Claude must contain only this error's own
        fields — never a dump of other users or unrelated occurrences."""
        event = _seed_error(user=student_user)
        captured_prompt = {}

        def fake_complete(prompt, **kwargs):
            captured_prompt['text'] = prompt
            return FAKE_ANALYSIS_JSON

        with patch('apps.vlt_ai.services.llm_client.llm_client.simple_complete', side_effect=fake_complete):
            client = auth_client(developer_user)
            client.post(f'/api/v1/error-monitor/errors/{event.id}/analyze/')

        prompt = captured_prompt['text']
        assert event.error_type in prompt
        # The student's phone/full name must never be sent — only the
        # sanitized error message/stack trace, no user-identifying dump.
        assert student_user.full_name not in prompt
        assert student_user.phone not in prompt

    def test_analysis_activity_is_logged(self, developer_user):
        from apps.notifications.models import ActivityLog
        event = _seed_error()
        with patch('apps.vlt_ai.services.llm_client.llm_client.simple_complete',
                    return_value=FAKE_ANALYSIS_JSON):
            client = auth_client(developer_user)
            client.post(f'/api/v1/error-monitor/errors/{event.id}/analyze/')

        assert ActivityLog.objects.filter(
            model_name='ErrorAiAnalysis', object_id=str(event.id), user=developer_user,
        ).exists()

    def test_llm_failure_returns_safe_response_not_500(self, developer_user):
        event = _seed_error()
        with patch('apps.vlt_ai.services.llm_client.llm_client.simple_complete',
                    side_effect=RuntimeError('anthropic unreachable')):
            client = auth_client(developer_user)
            resp = client.post(f'/api/v1/error-monitor/errors/{event.id}/analyze/')

        assert resp.status_code == 502
        assert 'error' in resp.data

    def test_non_json_llm_response_falls_back_to_raw_field(self, developer_user):
        event = _seed_error()
        with patch('apps.vlt_ai.services.llm_client.llm_client.simple_complete',
                    return_value='not valid json at all'):
            client = auth_client(developer_user)
            resp = client.post(f'/api/v1/error-monitor/errors/{event.id}/analyze/')

        assert resp.status_code == 200
        assert resp.data['ai_analysis']['raw'] == 'not valid json at all'
