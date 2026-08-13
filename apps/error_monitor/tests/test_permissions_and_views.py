"""
Error Monitor — developer-only visibility, safe user-facing messages.
"""
import pytest

from apps.error_monitor.capture import capture_exception
from apps.error_monitor.exception_handler import SAFE_ERROR_MESSAGE
from apps.error_monitor.models import ErrorEvent
from apps.error_monitor.tests.conftest import auth_client


def _seed_error(status_code=500):
    try:
        raise ValueError('seeded error')
    except ValueError as exc:
        return capture_exception(exc, endpoint='/api/v1/x/', status_code=status_code)


@pytest.mark.django_db
class TestDeveloperOnlyVisibility:
    """Only developer (or superuser) can reach any error_monitor endpoint —
    not admin, not finance, not teacher, not student."""

    @pytest.mark.parametrize('fixture_name', ['admin_user', 'teacher_user', 'student_user', 'finance_user'])
    def test_non_developer_roles_denied_error_list(self, request, fixture_name):
        user = request.getfixturevalue(fixture_name)
        client = auth_client(user)
        resp = client.get('/api/v1/error-monitor/errors/')
        assert resp.status_code == 403

    @pytest.mark.parametrize('fixture_name', ['admin_user', 'teacher_user', 'student_user', 'finance_user'])
    def test_non_developer_roles_denied_stats(self, request, fixture_name):
        user = request.getfixturevalue(fixture_name)
        client = auth_client(user)
        resp = client.get('/api/v1/error-monitor/stats/')
        assert resp.status_code == 403

    def test_developer_can_list_errors(self, developer_user):
        _seed_error()
        client = auth_client(developer_user)
        resp = client.get('/api/v1/error-monitor/errors/')
        assert resp.status_code == 200
        assert resp.data['count'] == 1

    def test_developer_can_view_stack_trace_in_detail(self, developer_user):
        event = _seed_error()
        client = auth_client(developer_user)
        resp = client.get(f'/api/v1/error-monitor/errors/{event.id}/')
        assert resp.status_code == 200
        assert resp.data['recent_occurrences'][0]['stack_trace']

    def test_admin_cannot_view_error_detail(self, admin_user):
        event = _seed_error()
        client = auth_client(admin_user)
        resp = client.get(f'/api/v1/error-monitor/errors/{event.id}/')
        assert resp.status_code == 403

    def test_developer_can_update_status(self, developer_user):
        event = _seed_error()
        client = auth_client(developer_user)
        resp = client.patch(f'/api/v1/error-monitor/errors/{event.id}/status/',
                             {'status': 'resolved'}, format='json')
        assert resp.status_code == 200
        event.refresh_from_db()
        assert event.status == ErrorEvent.Status.RESOLVED

    def test_admin_cannot_update_status(self, admin_user):
        event = _seed_error()
        client = auth_client(admin_user)
        resp = client.patch(f'/api/v1/error-monitor/errors/{event.id}/status/',
                             {'status': 'resolved'}, format='json')
        assert resp.status_code == 403

    def test_status_change_is_audit_logged(self, developer_user):
        from apps.notifications.models import ActivityLog
        event = _seed_error()
        client = auth_client(developer_user)
        client.patch(f'/api/v1/error-monitor/errors/{event.id}/status/',
                      {'status': 'ignored'}, format='json')
        assert ActivityLog.objects.filter(
            model_name='ErrorEvent', object_id=str(event.id),
            action=ActivityLog.Action.UPDATE,
        ).exists()


@pytest.mark.django_db
class TestSafeUserFacingMessages:
    """Confirms the custom DRF exception handler never leaks technical
    detail to the response body, regardless of DEBUG."""

    def test_unhandled_exception_returns_safe_generic_message(self):
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from apps.error_monitor.exception_handler import custom_exception_handler

        factory = APIRequestFactory()
        django_request = factory.get('/api/v1/some-endpoint/')
        request = Request(django_request)

        exc = ValueError('DB password is hunter2, connection string leaked here')
        response = custom_exception_handler(exc, {'request': request, 'view': None})

        assert response.status_code == 500
        assert response.data == {'error': SAFE_ERROR_MESSAGE}
        # The exact things a normal user must never see:
        body = str(response.data)
        assert 'hunter2' not in body
        assert 'Traceback' not in body
        assert '.py' not in body  # no file paths

    def test_unhandled_exception_is_captured_and_grouped(self):
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from apps.error_monitor.exception_handler import custom_exception_handler

        request = Request(APIRequestFactory().get('/api/v1/boom/'))
        custom_exception_handler(RuntimeError('x'), {'request': request, 'view': None})

        assert ErrorEvent.objects.filter(error_type='RuntimeError').exists()

    def test_expected_4xx_passes_through_unchanged_and_is_not_captured(self):
        from rest_framework.exceptions import ValidationError
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from apps.error_monitor.exception_handler import custom_exception_handler

        request = Request(APIRequestFactory().get('/api/v1/x/'))
        exc = ValidationError({'field': ['required']})
        response = custom_exception_handler(exc, {'request': request, 'view': None})

        assert response.status_code == 400
        assert response.data == {'field': ['required']}  # DRF's own body, untouched
        assert ErrorEvent.objects.count() == 0  # 4xx is an expected outcome, not a bug
