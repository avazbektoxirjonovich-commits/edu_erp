"""
Tests: VLT AI chat API endpoint
"""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from apps.vlt_ai.models import Conversation

User = get_user_model()


# ── Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        phone="+998902220001",
        password="testpass123",
        full_name="Chat Admin",
        role="admin",
    )


@pytest.fixture
def student_user(db):
    return User.objects.create_user(
        phone="+998902220002",
        password="testpass123",
        full_name="Chat Student",
        role="student",
    )


@pytest.fixture
def auth_client_admin(admin_user):
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    client = APIClient()
    tokens = RefreshToken.for_user(admin_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.access_token}")
    return client


@pytest.fixture
def auth_client_student(student_user):
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    client = APIClient()
    tokens = RefreshToken.for_user(student_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.access_token}")
    return client


# ── Chat endpoint ─────────────────────────────────────────────

@pytest.mark.django_db
def test_chat_creates_conversation(admin_user, auth_client_admin):
    """POST /chat/ must create a Conversation and Message."""
    mock_gen = iter([
        'data: {"type": "text", "text": "Salom"}\n\n',
        "data: [DONE]\n\n",
    ])

    with patch("apps.vlt_ai.api.views.process_chat", return_value=mock_gen):
        response = auth_client_admin.post(
            "/api/v1/vlt-ai/chat/",
            {"message": "Salom VLT AI"},
            format="json",
        )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")
    assert Conversation.objects.filter(user=admin_user).exists()


@pytest.mark.django_db
def test_chat_requires_authentication(db):
    from rest_framework.test import APIClient

    client = APIClient()
    response = client.post(
        "/api/v1/vlt-ai/chat/",
        {"message": "Salom"},
        format="json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_chat_invalid_payload(auth_client_admin):
    response = auth_client_admin.post(
        "/api/v1/vlt-ai/chat/",
        {},
        format="json",
    )
    assert response.status_code == 400


# ── Conversation list ──────────────────────────────────────────

@pytest.mark.django_db
def test_conversation_list_scoped_to_user(admin_user, student_user, auth_client_admin):
    """GET /conversations/ must return only the authenticated user's conversations."""
    Conversation.objects.create(user=admin_user, title="Admin suhbati")
    Conversation.objects.create(user=student_user, title="Student suhbati")

    response = auth_client_admin.get("/api/v1/vlt-ai/conversations/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Admin suhbati"


@pytest.mark.django_db
def test_conversation_detail_not_found_for_other_user(
    admin_user, student_user, auth_client_student
):
    """Students must not see admin's conversation."""
    conv = Conversation.objects.create(user=admin_user, title="Admin")
    response = auth_client_student.get(f"/api/v1/vlt-ai/conversations/{conv.id}/")
    assert response.status_code == 404


# ── Out-of-scope request integration ──────────────────────────

@pytest.mark.django_db
def test_out_of_scope_tool_call_returns_uzbek_denied(student_user):
    """Student calling a restricted tool must receive the Uzbek denial message."""
    from apps.vlt_ai.tools.registry import execute_tool

    result = execute_tool(student_user, "get_payment_summary", {})
    assert result["error"] == "Sizda bunga ruxsat yo'q"
