import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.groups.models import Group
from apps.payments.models import Payment
from apps.students.models import Student


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        phone='+998900000020', password='pass1234',
        full_name='Finance User', role=User.Role.FINANCE,
    )


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        phone='+998900000021', password='pass1234',
        full_name='Teacher User', role=User.Role.TEACHER,
    )


@pytest.fixture
def group_a(db):
    return Group.objects.create(
        name='Debt Group A', start_date='2026-01-01',
        start_time='09:00', end_time='10:00', monthly_fee=500000, payment_due_day=5,
    )


@pytest.fixture
def group_b(db):
    return Group.objects.create(
        name='Debt Group B', start_date='2026-01-01',
        start_time='09:00', end_time='10:00', monthly_fee=300000, payment_due_day=25,
    )


def make_student(phone, name, group):
    user = User.objects.create_user(phone=phone, password='pass1234', full_name=name, role=User.Role.STUDENT)
    return Student.objects.create(user=user, phone=phone, group=group)


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestDebtorsList:

    def test_only_unpaid_and_partial_appear(self, finance_user, group_a):
        s_paid    = make_student('+998900000030', 'Paid Student', group_a)
        s_partial = make_student('+998900000031', 'Partial Student', group_a)
        s_unpaid  = make_student('+998900000032', 'Unpaid Student', group_a)
        Payment.objects.create(student=s_paid, group=group_a, month=1, year=2026,
                               amount=500000, paid_amount=500000)
        Payment.objects.create(student=s_partial, group=group_a, month=1, year=2026,
                               amount=500000, paid_amount=200000)
        Payment.objects.create(student=s_unpaid, group=group_a, month=1, year=2026, amount=500000)

        client = auth_client(finance_user)
        resp = client.get('/api/v1/finance/debts/?month=1&year=2026')
        assert resp.status_code == 200
        names = {row['student_name'] for row in resp.data}
        assert names == {'Partial Student', 'Unpaid Student'}

    def test_sorted_by_debt_descending(self, finance_user, group_a):
        s_small = make_student('+998900000033', 'Small Debt', group_a)
        s_big   = make_student('+998900000034', 'Big Debt', group_a)
        Payment.objects.create(student=s_small, group=group_a, month=2, year=2026,
                               amount=500000, paid_amount=450000)
        Payment.objects.create(student=s_big, group=group_a, month=2, year=2026,
                               amount=500000, paid_amount=50000)

        client = auth_client(finance_user)
        resp = client.get('/api/v1/finance/debts/?month=2&year=2026')
        assert [row['student_name'] for row in resp.data] == ['Big Debt', 'Small Debt']

    def test_group_filter(self, finance_user, group_a, group_b):
        make_student_a = make_student('+998900000035', 'In Group A', group_a)
        make_student_b = make_student('+998900000036', 'In Group B', group_b)
        Payment.objects.create(student=make_student_a, group=group_a, month=3, year=2026, amount=500000)
        Payment.objects.create(student=make_student_b, group=group_b, month=3, year=2026, amount=300000)

        client = auth_client(finance_user)
        resp = client.get(f'/api/v1/finance/debts/?month=3&year=2026&group={group_a.id}')
        assert len(resp.data) == 1
        assert resp.data[0]['student_name'] == 'In Group A'

    def test_search_filter(self, finance_user, group_a):
        s1 = make_student('+998900000037', 'Aziz Karimov', group_a)
        s2 = make_student('+998900000038', 'Vali Rashidov', group_a)
        Payment.objects.create(student=s1, group=group_a, month=4, year=2026, amount=500000)
        Payment.objects.create(student=s2, group=group_a, month=4, year=2026, amount=500000)

        client = auth_client(finance_user)
        resp = client.get('/api/v1/finance/debts/?month=4&year=2026&search=Aziz')
        assert len(resp.data) == 1
        assert resp.data[0]['student_name'] == 'Aziz Karimov'

    def test_overdue_only_filter(self, finance_user, group_a, group_b):
        # group_a due day 5 (already passed for month=1/2026 relative to "today"),
        # group_b due day 25 in a FAR future month (not yet due).
        s_overdue    = make_student('+998900000039', 'Overdue Student', group_a)
        s_not_yet    = make_student('+998900000040', 'Not Due Yet', group_b)
        Payment.objects.create(student=s_overdue, group=group_a, month=1, year=2026, amount=500000)
        Payment.objects.create(student=s_not_yet, group=group_b, month=12, year=2099, amount=300000)

        client = auth_client(finance_user)
        # Query each month separately since the endpoint is scoped to one month/year.
        resp = client.get('/api/v1/finance/debts/?month=1&year=2026&overdue_only=true')
        assert [row['student_name'] for row in resp.data] == ['Overdue Student']

        resp2 = client.get('/api/v1/finance/debts/?month=12&year=2099&overdue_only=true')
        assert resp2.data == []

    def test_total_debt_reflects_all_months(self, finance_user, group_a):
        s = make_student('+998900000041', 'Multi Month Debtor', group_a)
        Payment.objects.create(student=s, group=group_a, month=5, year=2026, amount=500000)
        Payment.objects.create(student=s, group=group_a, month=6, year=2026, amount=500000)

        client = auth_client(finance_user)
        resp = client.get('/api/v1/finance/debts/?month=6&year=2026')
        assert resp.data[0]['debt_amount'] == '500000'      # this month only
        assert resp.data[0]['total_debt'] == 1000000.0       # both months

    def test_teacher_cannot_access_debts(self, teacher_user, group_a):
        client = auth_client(teacher_user)
        resp = client.get('/api/v1/finance/debts/')
        assert resp.status_code == 403
