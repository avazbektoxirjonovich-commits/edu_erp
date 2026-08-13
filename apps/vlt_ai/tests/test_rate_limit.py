"""
VLT AI — per-role rate limiting.

Backend-enforced only: check_ai_rate_limit() is unit-tested directly against
real Message rows (never a client-supplied counter), and ChatView is tested
end-to-end to confirm a rate-limited request never reaches the LLM client —
the cost-control requirement ("do not call Claude when the user has
exceeded their limit").
"""
from unittest.mock import patch

import pytest

from apps.vlt_ai.models import Conversation, Message
from apps.vlt_ai.rate_limit import RATE_LIMIT_MESSAGE, RATE_LIMITS, check_ai_rate_limit
from apps.vlt_ai.tests.conftest import auth_client


def _make_conversation_with_n_questions(user, n):
    conv = Conversation.objects.create(user=user, title='t')
    for _ in range(n):
        Message.objects.create(conversation=conv, role=Message.Role.USER, content='hi')
    return conv


@pytest.mark.django_db
class TestRateLimitLogic:

    def test_developer_is_unlimited(self, developer_user):
        _make_conversation_with_n_questions(developer_user, 500)
        status = check_ai_rate_limit(developer_user)
        assert status.allowed is True
        assert status.limit is None

    def test_student_limit_is_two_per_hour(self, student_a):
        user, _ = student_a
        assert RATE_LIMITS['student'] == 2
        _make_conversation_with_n_questions(user, 1)
        assert check_ai_rate_limit(user).allowed is True
        _make_conversation_with_n_questions(user, 1)  # total 2 — at the cap
        assert check_ai_rate_limit(user).allowed is False

    def test_admin_limit_is_ten(self, admin_user):
        assert RATE_LIMITS['admin'] == 10
        _make_conversation_with_n_questions(admin_user, 9)
        assert check_ai_rate_limit(admin_user).allowed is True
        _make_conversation_with_n_questions(admin_user, 1)
        assert check_ai_rate_limit(admin_user).allowed is False

    def test_teacher_and_finance_limit_is_five(self, teacher_a, finance_user):
        user, _, _ = teacher_a
        assert RATE_LIMITS['teacher'] == 5
        assert RATE_LIMITS['finance'] == 5
        _make_conversation_with_n_questions(user, 5)
        assert check_ai_rate_limit(user).allowed is False
        assert check_ai_rate_limit(finance_user).allowed is True  # separate user, own count

    def test_parent_limit_is_two(self, parent_of_a):
        assert RATE_LIMITS['parent'] == 2
        _make_conversation_with_n_questions(parent_of_a, 2)
        assert check_ai_rate_limit(parent_of_a).allowed is False

    def test_only_own_questions_count_toward_limit(self, student_a, student_b):
        """Someone else's questions must never count against this user's cap."""
        user_a, _ = student_a
        user_b, _ = student_b
        _make_conversation_with_n_questions(user_b, 5)
        assert check_ai_rate_limit(user_a).allowed is True

    def test_window_is_rolling_one_hour(self, student_a):
        from datetime import timedelta

        from django.utils import timezone
        user, _ = student_a
        conv = Conversation.objects.create(user=user, title='t')
        old_msg = Message.objects.create(conversation=conv, role=Message.Role.USER, content='old')
        Message.objects.filter(pk=old_msg.pk).update(created_at=timezone.now() - timedelta(hours=2))
        Message.objects.create(conversation=conv, role=Message.Role.USER, content='recent')
        # Only 1 message is inside the rolling window — well under the cap of 2
        assert check_ai_rate_limit(user).allowed is True


@pytest.mark.django_db
class TestRateLimitEnforcedInChatView:

    def test_rate_limited_request_never_calls_llm(self, student_a):
        user, _ = student_a
        _make_conversation_with_n_questions(user, 2)  # at the cap

        with patch('apps.vlt_ai.services.llm_client.llm_client.chat_with_tools') as mock_llm:
            client = auth_client(user)
            resp = client.post('/api/v1/vlt-ai/chat/', {'message': 'salom'}, format='json')

        assert resp.status_code == 429
        assert resp.data['error'] == RATE_LIMIT_MESSAGE
        mock_llm.assert_not_called()

    def test_rate_limited_request_creates_no_new_conversation(self, student_a):
        user, _ = student_a
        _make_conversation_with_n_questions(user, 2)
        before = Conversation.objects.filter(user=user).count()

        client = auth_client(user)
        client.post('/api/v1/vlt-ai/chat/', {'message': 'salom'}, format='json')

        assert Conversation.objects.filter(user=user).count() == before

    def test_rate_limit_rejection_is_logged(self, student_a):
        from apps.notifications.models import ActivityLog
        user, _ = student_a
        _make_conversation_with_n_questions(user, 2)

        client = auth_client(user)
        client.post('/api/v1/vlt-ai/chat/', {'message': 'salom'}, format='json')

        assert ActivityLog.objects.filter(
            user=user, action=ActivityLog.Action.RATE_LIMITED, model_name='VltAiChat',
        ).exists()

    def test_under_limit_request_does_reach_llm(self, student_a):
        """Sanity check the negative test above is meaningful — a request
        under the cap does proceed to the LLM client. ChatView streams its
        response lazily (a generator), so the body must be consumed to
        actually execute process_chat()."""
        user, _ = student_a  # 0 questions asked yet, limit is 2

        with patch('apps.vlt_ai.services.llm_client.llm_client.chat_with_tools') as mock_llm:
            mock_llm.side_effect = RuntimeError('boom — process_chat catches this gracefully')
            client = auth_client(user)
            resp = client.post('/api/v1/vlt-ai/chat/', {'message': 'salom'}, format='json')
            list(resp.streaming_content)  # force the generator to run

        mock_llm.assert_called_once()
