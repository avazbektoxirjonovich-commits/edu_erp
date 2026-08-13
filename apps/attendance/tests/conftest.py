import datetime

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.groups.models import Group
from apps.students.models import Student
from apps.teachers.models import Teacher


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(phone='+998903330001', password='x', full_name='Admin', role=User.Role.ADMIN)


@pytest.fixture
def teacher_a(db):
    user = User.objects.create_user(phone='+998903330002', password='x', full_name='Teacher A', role=User.Role.TEACHER)
    teacher = Teacher.objects.create(user=user, phone=user.phone)
    group = Group.objects.create(
        name='Attendance Test Group', teacher=teacher,
        start_date=datetime.date(2026, 1, 1),
        start_time=datetime.time(9, 0), end_time=datetime.time(10, 0),
    )
    return user, teacher, group


@pytest.fixture
def teacher_b(db):
    user = User.objects.create_user(phone='+998903330003', password='x', full_name='Teacher B', role=User.Role.TEACHER)
    teacher = Teacher.objects.create(user=user, phone=user.phone)
    group = Group.objects.create(
        name='Attendance Test Group B', teacher=teacher,
        start_date=datetime.date(2026, 1, 1),
        start_time=datetime.time(11, 0), end_time=datetime.time(12, 0),
    )
    return user, teacher, group


@pytest.fixture
def student_a(db, teacher_a):
    _, _, group = teacher_a
    user = User.objects.create_user(phone='+998903330004', password='x', full_name='Student A', role=User.Role.STUDENT)
    student = Student.objects.create(user=user, phone=user.phone, group=group, coins=0)
    return user, student


@pytest.fixture
def student_b(db, teacher_a):
    _, _, group = teacher_a
    user = User.objects.create_user(phone='+998903330005', password='x', full_name='Student B', role=User.Role.STUDENT)
    student = Student.objects.create(user=user, phone=user.phone, group=group, coins=0)
    return user, student
