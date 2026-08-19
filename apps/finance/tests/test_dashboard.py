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


@pytest.mark.django_db
class TestDashboardIncomeBasesDoNotDoubleCount:
    """
    FIN-003: `received_income` (accrual — Payment billing period) and
    `monthly_income` (cash — PaymentTransaction paid_at date) are two
    deliberately different figures, not one double-counted into the other.
    Uses RecordPaymentView (the real, now-live payment-recording endpoint from
    Phase 20.1) so both figures are populated exactly the way production does it.
    """

    def _setup(self, finance_user):
        group = Group.objects.create(name='FIN003 Group', start_date='2026-01-01',
                                     start_time='09:00', end_time='10:00', monthly_fee=500000)
        user = User.objects.create_user(phone='+998900000120', password='p', full_name='S', role=User.Role.STUDENT)
        student = Student.objects.create(user=user, phone=user.phone, group=group)
        return auth_client(finance_user), student

    def test_single_on_time_payment_appears_once_in_each_basis(self, finance_user):
        # RecordPaymentSerializer always stamps the PaymentTransaction with
        # timezone.now() — so for the "cash arrives the same month it's billed
        # for" case, the bill's month/year must be *today's*, not an arbitrary
        # fixed month, otherwise this would (correctly) become a late-payment
        # scenario like the test below instead of an on-time one.
        from django.utils import timezone
        today = timezone.localdate()
        client, student = self._setup(finance_user)
        resp = client.post('/api/v1/finance/transactions/record/', {
            'student': str(student.id), 'month': today.month, 'year': today.year, 'amount': 500000,
        })
        assert resp.status_code == 201

        dash = client.get(f'/api/v1/finance/dashboard/?month={today.month}&year={today.year}').data
        # Accrual basis: this month's bill is fully paid.
        assert dash['received_income'] == 500000.0
        # Cash basis: the same 500,000 shows up once here too — not summed with
        # received_income anywhere, and not doubled to 1,000,000.
        assert dash['monthly_income'] == 500000.0
        assert dash['net_result'] == 500000.0

    def test_late_payment_diverges_correctly_across_calendar_months(self, finance_user):
        """
        A payment for November's bill, actually collected in December, must:
        - count toward November's `received_income` (it settles November's bill)
        - count toward December's `monthly_income` (the cash arrived in December)
        - NOT count toward November's `monthly_income` (no cash moved that month)
        - NOT count toward December's `received_income` (December's own bill is separate)
        This is the exact scenario FIN-003 describes — both figures are correct,
        simply defined on different bases, and this proves neither is broken by
        the other's presence.
        """
        client, student = self._setup(finance_user)
        # Backdate the PaymentTransaction itself to December by recording, then
        # adjusting paid_at directly (RecordPaymentSerializer always uses "now"
        # for paid_at, so we simulate the late-collection scenario at the model
        # layer — this still exercises the real signal-driven paid_amount sync).
        resp = client.post('/api/v1/finance/transactions/record/', {
            'student': str(student.id), 'month': 11, 'year': 2026, 'amount': 500000,
        })
        assert resp.status_code == 201
        txn = PaymentTransaction.objects.get(pk=resp.data['transaction']['id'])
        txn.paid_at = datetime(2026, 12, 3, 10, 0, tzinfo=dt_timezone.utc)
        txn.save(update_fields=['paid_at'])

        nov = client.get('/api/v1/finance/dashboard/?month=11&year=2026').data
        dec = client.get('/api/v1/finance/dashboard/?month=12&year=2026').data

        assert nov['received_income'] == 500000.0   # November's bill is settled
        assert nov['monthly_income'] == 0.0          # no cash moved in November

        assert dec['received_income'] == 0.0          # December has no bill for this student
        assert dec['monthly_income'] == 500000.0     # cash arrived in December
