from datetime import datetime
from datetime import timezone as dt_timezone

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.finance.models import Asset, Expense, PaymentTransaction
from apps.groups.models import Group
from apps.payments.models import Payment
from apps.students.models import Student
from apps.teachers.models import Teacher, TeacherSalaryPayment


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        phone='+998900000110', password='pass1234',
        full_name='Finance User', role=User.Role.FINANCE,
    )


@pytest.fixture
def teacher_role_user(db):
    return User.objects.create_user(
        phone='+998900000111', password='pass1234',
        full_name='Teacher User', role=User.Role.TEACHER,
    )


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestFinanceDashboard:

    def test_dashboard_aggregates_everything(self, finance_user):
        group = Group.objects.create(name='Dash Group', start_date='2026-01-01',
                                     start_time='09:00', end_time='10:00', monthly_fee=500000)
        s1_user = User.objects.create_user(phone='+998900000112', password='p', full_name='Paid', role=User.Role.STUDENT)
        s2_user = User.objects.create_user(phone='+998900000113', password='p', full_name='Unpaid', role=User.Role.STUDENT)
        s1 = Student.objects.create(user=s1_user, phone=s1_user.phone, group=group)
        s2 = Student.objects.create(user=s2_user, phone=s2_user.phone, group=group)

        p1 = Payment.objects.create(student=s1, group=group, month=3, year=2026, amount=500000)
        PaymentTransaction.objects.create(
            payment=p1, amount=500000, paid_at=datetime(2026, 3, 5, 10, 0, tzinfo=dt_timezone.utc),
        )
        Payment.objects.create(student=s2, group=group, month=3, year=2026, amount=500000)

        teacher_user = User.objects.create_user(phone='+998900000114', password='p', full_name='T', role=User.Role.TEACHER)
        teacher = Teacher.objects.create(user=teacher_user, phone=teacher_user.phone, salary=1000000)
        TeacherSalaryPayment.objects.create(
            teacher=teacher, month=3, year=2026, amount=1000000,
            paid_at=datetime(2026, 3, 10, 10, 0, tzinfo=dt_timezone.utc),
        )
        Expense.objects.create(name='Rent', category='rent', amount=200000, expense_date='2026-03-15')
        Asset.objects.create(name='PC', quantity=5, purchase_price=1000000)

        client = auth_client(finance_user)
        resp = client.get('/api/v1/finance/dashboard/?month=3&year=2026')
        assert resp.status_code == 200
        d = resp.data
        assert d['expected_monthly_income'] == 1000000.0
        assert d['received_income'] == 500000.0
        assert d['outstanding_debt_this_month'] == 500000.0
        assert d['paid_students'] == 1
        assert d['unpaid_students'] == 1
        assert d['monthly_income'] == 500000.0
        assert d['teacher_salaries'] == 1000000.0
        assert d['expenses'] == 200000.0
        assert d['net_result'] == 500000.0 - 1000000.0 - 200000.0
        assert d['total_asset_value'] == 5000000.0

    def test_invalid_month_returns_400(self, finance_user):
        client = auth_client(finance_user)
        resp = client.get('/api/v1/finance/dashboard/?month=99&year=2026')
        assert resp.status_code == 400

    def test_teacher_cannot_view_dashboard(self, teacher_role_user):
        client = auth_client(teacher_role_user)
        resp = client.get('/api/v1/finance/dashboard/')
        assert resp.status_code == 403
