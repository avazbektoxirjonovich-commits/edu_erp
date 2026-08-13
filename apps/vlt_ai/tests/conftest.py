import datetime

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.groups.models import Group
from apps.students.models import Student
from apps.teachers.models import Teacher


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def developer_user(db):
    return User.objects.create_user(
        phone='+998901110001', password='pass1234',
        full_name='Developer User', role=User.Role.DEVELOPER,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        phone='+998901110002', password='pass1234',
        full_name='Admin User', role=User.Role.ADMIN,
    )


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        phone='+998901110003', password='pass1234',
        full_name='Finance User', role=User.Role.FINANCE,
    )


@pytest.fixture
def teacher_a(db):
    user = User.objects.create_user(
        phone='+998901110004', password='pass1234',
        full_name='Teacher A', role=User.Role.TEACHER,
    )
    teacher = Teacher.objects.create(user=user, phone=user.phone, subject='Math')
    group = Group.objects.create(
        name='Group A', teacher=teacher,
        start_date=datetime.date(2026, 1, 1),
        start_time=datetime.time(9, 0), end_time=datetime.time(10, 0),
    )
    return user, teacher, group


@pytest.fixture
def teacher_b(db):
    user = User.objects.create_user(
        phone='+998901110005', password='pass1234',
        full_name='Teacher B', role=User.Role.TEACHER,
    )
    teacher = Teacher.objects.create(user=user, phone=user.phone, subject='Physics')
    group = Group.objects.create(
        name='Group B', teacher=teacher,
        start_date=datetime.date(2026, 1, 1),
        start_time=datetime.time(11, 0), end_time=datetime.time(12, 0),
    )
    return user, teacher, group


def _make_student(phone, group=None, coins=0, parent_user=None):
    user = User.objects.create_user(phone=phone, password='pass1234',
                                    full_name=f'Student {phone}', role=User.Role.STUDENT)
    student = Student.objects.create(user=user, phone=phone, group=group,
                                     coins=coins, parent_user=parent_user)
    return user, student


@pytest.fixture
def student_a(db, teacher_a):
    _, _, group = teacher_a
    return _make_student('+998901110006', group=group, coins=500)


@pytest.fixture
def student_b(db, teacher_b):
    _, _, group = teacher_b
    return _make_student('+998901110007', group=group, coins=50)


@pytest.fixture
def parent_of_a(db, student_a):
    _, student = student_a
    user = User.objects.create_user(
        phone='+998901110008', password='pass1234',
        full_name='Parent of A', role=User.Role.PARENT,
    )
    student.parent_user = user
    student.save(update_fields=['parent_user'])
    return user
