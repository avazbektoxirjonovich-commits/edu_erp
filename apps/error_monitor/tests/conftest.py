import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def developer_user(db):
    return User.objects.create_user(
        phone='+998902220101', password='pass1234',
        full_name='Developer', role=User.Role.DEVELOPER,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        phone='+998902220102', password='pass1234',
        full_name='Admin', role=User.Role.ADMIN,
    )


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        phone='+998902220103', password='pass1234',
        full_name='Teacher', role=User.Role.TEACHER,
    )


@pytest.fixture
def student_user(db):
    return User.objects.create_user(
        phone='+998902220104', password='pass1234',
        full_name='Student', role=User.Role.STUDENT,
    )


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        phone='+998902220105', password='pass1234',
        full_name='Finance', role=User.Role.FINANCE,
    )
