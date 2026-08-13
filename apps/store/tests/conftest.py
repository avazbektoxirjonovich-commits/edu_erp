import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.students.models import Student


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        phone='+998900001090', password='pass1234',
        full_name='Admin User', role=User.Role.ADMIN,
    )


@pytest.fixture
def developer_user(db):
    return User.objects.create_user(
        phone='+998900001091', password='pass1234',
        full_name='Developer User', role=User.Role.DEVELOPER,
    )


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        phone='+998900001092', password='pass1234',
        full_name='Teacher User', role=User.Role.TEACHER,
    )


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        phone='+998900001093', password='pass1234',
        full_name='Finance User', role=User.Role.FINANCE,
    )


def _make_student(phone, coins=0):
    user = User.objects.create_user(phone=phone, password='pass1234',
                                    full_name=f'Student {phone}', role=User.Role.STUDENT)
    student = Student.objects.create(user=user, phone=phone, coins=coins)
    return user, student


@pytest.fixture
def student_a(db):
    return _make_student('+998900001094', coins=300)


@pytest.fixture
def student_b(db):
    return _make_student('+998900001095', coins=50)
