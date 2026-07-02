"""Shared fixtures for face_auth tests."""
import base64
import json
import pytest
import numpy as np
from cryptography.fernet import Fernet
from rest_framework.test import APIClient


@pytest.fixture
def fernet_key(settings):
    key = Fernet.generate_key().decode()
    settings.FACE_ENCRYPTION_KEY = key
    settings.FACE_AUTH_ENABLED   = True
    settings.FACE_REQUIRED_ROLES = ['admin', 'developer']
    settings.FACE_COSINE_THRESHOLD = 0.68
    settings.FACE_MAX_ATTEMPTS   = 5
    settings.FACE_LOCKOUT_MINUTES = 5
    return key


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    from apps.accounts.models import User
    return User.objects.create_user(
        phone='+998901234567',
        password='testpass123',
        full_name='Test Admin',
        role='admin',
    )


@pytest.fixture
def teacher_user(db):
    from apps.accounts.models import User
    return User.objects.create_user(
        phone='+998901234568',
        password='testpass123',
        full_name='Test Teacher',
        role='teacher',
    )


@pytest.fixture
def student_user(db):
    from apps.accounts.models import User
    return User.objects.create_user(
        phone='+998901234569',
        password='testpass123',
        full_name='Test Student',
        role='student',
    )


def make_black_frame_b64(width: int = 100, height: int = 100) -> str:
    """Create a tiny black JPEG frame as base64."""
    import cv2
    img = np.zeros((height, width, 3), dtype=np.uint8)
    _, buf = cv2.imencode('.jpg', img)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf).decode()


def make_synthetic_embedding(dim: int = 512) -> list:
    """Return a deterministic unit-norm embedding."""
    rng = np.random.RandomState(42)
    v   = rng.randn(dim).astype(np.float64)
    return (v / np.linalg.norm(v)).tolist()


def make_varying_frames(n: int = 10) -> list:
    """
    Create n slightly different frames (non-zero inter-frame difference)
    to pass the anti-spoofing motion check.
    """
    import cv2
    frames_b64 = []
    for i in range(n):
        img = np.full((100, 100, 3), i * 10 % 200 + 10, dtype=np.uint8)
        _, buf = cv2.imencode('.jpg', img)
        frames_b64.append('data:image/jpeg;base64,' + base64.b64encode(buf).decode())
    return frames_b64
