import datetime

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.groups.models import Group
from apps.homework.models import Assignment
from apps.students.models import Student
from apps.teachers.models import Teacher


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def teacher_a(db):
    user = User.objects.create_user(phone='+998904440001', password='x', full_name='HW Teacher', role=User.Role.TEACHER)
    teacher = Teacher.objects.create(user=user, phone=user.phone)
    group = Group.objects.create(
        name='Homework Test Group', teacher=teacher,
        start_date=datetime.date(2026, 1, 1),
        start_time=datetime.time(9, 0), end_time=datetime.time(10, 0),
    )
    return user, teacher, group


@pytest.fixture
def student_a(db, teacher_a):
    _, _, group = teacher_a
    user = User.objects.create_user(phone='+998904440002', password='x', full_name='HW Student', role=User.Role.STUDENT)
    student = Student.objects.create(user=user, phone=user.phone, group=group, coins=0)
    return user, student


@pytest.fixture
def assignment_100(db, teacher_a):
    _, teacher, group = teacher_a
    return Assignment.objects.create(
        title='Test Assignment', description='desc', group=group, teacher=teacher,
        max_score=100, xp_reward=50,
    )


@pytest.fixture
def submission(db, assignment_100, student_a):
    from apps.homework.models import Submission
    _, student = student_a
    return Submission.objects.create(assignment=assignment_100, student=student, answer='my answer')
