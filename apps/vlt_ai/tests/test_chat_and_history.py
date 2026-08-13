"""
VLT AI — end-to-end chat flow and conversation-history isolation.
"""
import json
from unittest.mock import patch

import pytest

from apps.vlt_ai.models import Conversation, Message
from apps.vlt_ai.tests.conftest import auth_client


class FakeUsage:
    def __init__(self, input_tokens=42, output_tokens=8):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class FakeTextBlock:
    type = 'text'

    def __init__(self, text):
        self.text = text


class FakeAnthropicResponse:
    """Minimal stand-in for the Anthropic SDK's Message object — just the
    attributes chat_service.py actually reads."""

    def __init__(self, text='Salom! Yordam bera olaman.'):
        self.stop_reason = 'end_turn'
        self.content = [FakeTextBlock(text)]
        self.usage = FakeUsage()


def _consume(resp):
    return b''.join(resp.streaming_content).decode('utf-8')


@pytest.mark.django_db
class TestChatFlowPersistence:

    def test_successful_reply_persists_model_tokens_and_cost(self, student_a):
        user, _ = student_a
        with patch('apps.vlt_ai.services.llm_client.llm_client.chat_with_tools',
                    return_value=FakeAnthropicResponse('Yaxshi javob')):
            client = auth_client(user)
            resp = client.post('/api/v1/vlt-ai/chat/', {'message': 'salom'}, format='json')
            body = _consume(resp)

        assert resp.status_code == 200
        assert 'Yaxshi javob' in body
        assert '[DONE]' in body

        reply = Message.objects.get(role=Message.Role.ASSISTANT, conversation__user=user)
        assert reply.request_status == Message.RequestStatus.OK
        assert reply.input_tokens == 42
        assert reply.output_tokens == 8
        assert reply.model  # populated from llm_client.model
        assert reply.estimated_cost is not None

    def test_llm_error_persists_error_status_and_is_captured(self, student_a):
        user, _ = student_a
        with patch('apps.vlt_ai.services.llm_client.llm_client.chat_with_tools',
                    side_effect=RuntimeError('anthropic down')):
            client = auth_client(user)
            resp = client.post('/api/v1/vlt-ai/chat/', {'message': 'salom'}, format='json')
            body = _consume(resp)

        assert '"type": "error"' in body
        reply = Message.objects.get(role=Message.Role.ASSISTANT, conversation__user=user)
        assert reply.request_status == Message.RequestStatus.ERROR

        from apps.error_monitor.models import ErrorEvent
        assert ErrorEvent.objects.filter(error_type='RuntimeError').exists()

    def test_question_and_response_are_audit_logged(self, student_a):
        from apps.notifications.models import ActivityLog
        user, _ = student_a
        with patch('apps.vlt_ai.services.llm_client.llm_client.chat_with_tools',
                    return_value=FakeAnthropicResponse()):
            client = auth_client(user)
            resp = client.post('/api/v1/vlt-ai/chat/', {'message': 'salom'}, format='json')
            _consume(resp)

        assert ActivityLog.objects.filter(user=user, model_name='VltAiQuestion').exists()
        assert ActivityLog.objects.filter(user=user, model_name='VltAiResponse').exists()


@pytest.mark.django_db
class TestConversationHistoryIsolation:

    def test_user_sees_only_own_conversations_in_list(self, student_a, student_b):
        user_a, _ = student_a
        user_b, _ = student_b
        Conversation.objects.create(user=user_a, title='A convo')
        Conversation.objects.create(user=user_b, title='B convo')

        client = auth_client(user_a)
        resp = client.get('/api/v1/vlt-ai/conversations/')
        titles = [c['title'] for c in resp.data]
        assert 'A convo' in titles
        assert 'B convo' not in titles

    def test_user_cannot_fetch_another_users_conversation_by_id(self, student_a, student_b):
        user_a, _ = student_a
        user_b, _ = student_b
        convo_b = Conversation.objects.create(user=user_b, title='B convo')

        client = auth_client(user_a)
        resp = client.get(f'/api/v1/vlt-ai/conversations/{convo_b.id}/')
        assert resp.status_code == 404

    def test_developer_can_view_any_conversation_via_admin_endpoint(self, developer_user, student_a):
        user_a, _ = student_a
        convo = Conversation.objects.create(user=user_a, title='A convo')

        client = auth_client(developer_user)
        resp = client.get(f'/api/v1/vlt-ai/admin/conversations/{convo.id}/')
        assert resp.status_code == 200
        assert resp.data['title'] == 'A convo'

    def test_developer_can_list_all_conversations(self, developer_user, student_a, student_b):
        user_a, _ = student_a
        user_b, _ = student_b
        Conversation.objects.create(user=user_a, title='A convo')
        Conversation.objects.create(user=user_b, title='B convo')

        client = auth_client(developer_user)
        resp = client.get('/api/v1/vlt-ai/admin/conversations/')
        titles = [c['title'] for c in resp.data]
        assert 'A convo' in titles and 'B convo' in titles

    def test_admin_cannot_use_developer_only_global_history_endpoint(self, admin_user, student_a):
        """Global AI history is a Developer Panel feature, not admin."""
        user_a, _ = student_a
        convo = Conversation.objects.create(user=user_a, title='A convo')

        client = auth_client(admin_user)
        resp = client.get(f'/api/v1/vlt-ai/admin/conversations/{convo.id}/')
        assert resp.status_code == 403

    def test_student_cannot_use_admin_history_endpoint_at_all(self, student_a):
        client = auth_client(student_a[0])
        resp = client.get('/api/v1/vlt-ai/admin/conversations/')
        assert resp.status_code == 403

    def test_reading_history_never_calls_the_llm(self, student_a):
        """Listing/viewing history is explicitly a no-Claude-call path."""
        user, _ = student_a
        Conversation.objects.create(user=user, title='A convo')
        with patch('apps.vlt_ai.services.llm_client.llm_client.chat_with_tools') as mock_llm:
            client = auth_client(user)
            client.get('/api/v1/vlt-ai/conversations/')
        mock_llm.assert_not_called()
