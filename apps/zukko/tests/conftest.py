import datetime

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.groups.models import Group
from apps.students.models import Student
from apps.teachers.models import Teacher
from apps.zukko.models import BugFindChallenge, ChallengeSession, CodingChallenge


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def teacher_a(db):
    user = User.objects.create_user(phone='+998905550001', password='x', full_name='ZUKKO Teacher', role=User.Role.TEACHER)
    teacher = Teacher.objects.create(user=user, phone=user.phone)
    group = Group.objects.create(
        name='ZUKKO Test Group', teacher=teacher,
        start_date=datetime.date(2026, 1, 1),
        start_time=datetime.time(9, 0), end_time=datetime.time(10, 0),
    )
    return user, teacher, group


@pytest.fixture
def student_a(db, teacher_a):
    _, _, group = teacher_a
    user = User.objects.create_user(phone='+998905550002', password='x', full_name='ZUKKO Student', role=User.Role.STUDENT)
    student = Student.objects.create(user=user, phone=user.phone, group=group, coins=0)
    return user, student


@pytest.fixture
def bugfind_challenge(db, teacher_a):
    teacher_user, _, _ = teacher_a
    return BugFindChallenge.objects.create(
        title='Off-by-one', description='Find the bug',
        buggy_code='for i in range(1, n):\n    total += i',
        correct_code='for i in range(1, n + 1):\n    total += i',
        bug_line_number=1,
        bug_explanation='range should include n',
        difficulty='easy', points=10,
        created_by=teacher_user,
    )


@pytest.fixture
def coding_challenge(db, teacher_a):
    teacher_user, _, _ = teacher_a
    return CodingChallenge.objects.create(
        title='Print OK', description='Print ok',
        input_format='none', output_format='ok',
        hidden_test_cases=[{'input': '', 'expected_output': 'ok'}],
        starter_code='', solution_code="print('ok')",
        difficulty='easy', points=20,
        created_by=teacher_user,
    )


@pytest.fixture
def session_a(db, teacher_a, bugfind_challenge, coding_challenge):
    _, _, group = teacher_a
    teacher_user, _, _ = teacher_a
    session = ChallengeSession.objects.create(
        title='ZUKKO Session', session_type=ChallengeSession.SessionType.MIXED,
        status=ChallengeSession.Status.ACTIVE, group=group,
        created_by=teacher_user,
    )
    session.bugfind_pool.add(bugfind_challenge)
    session.coding_pool.add(coding_challenge)
    return session
