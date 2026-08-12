import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.finance.models import PaymentTransaction
from apps.groups.models import Group
from apps.payments.models import Payment
from apps.students.models import Student
from apps.teachers.models import Teacher


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        phone='+998900000001', password='pass1234',
        full_name='Finance User', role=User.Role.FINANCE,
    )


@pytest.fixture
def teacher_user(db):
    user = User.objects.create_user(
        phone='+998900000002', password='pass1234',
        full_name='Teacher User', role=User.Role.TEACHER,
    )
    Teacher.objects.create(user=user, phone=user.phone)
    return user


@pytest.fixture
def group(db):
    return Group.objects.create(
        name='Test Group', start_date='2026-01-01',
        start_time='09:00', end_time='10:00', monthly_fee=500000,
    )


@pytest.fixture
def student(db, group):
    user = User.objects.create_user(
        phone='+998900000003', password='pass1234',
        full_name='Test Student', role=User.Role.STUDENT,
    )
    return Student.objects.create(user=user, phone=user.phone, group=group)


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestRecordPayment:

    def test_finance_can_record_payment(self, finance_user, student):
        client = auth_client(finance_user)
        resp = client.post('/api/v1/finance/transactions/record/', {
            'student': str(student.id), 'month': 3, 'year': 2026,
            'amount': 200000, 'payment_type': 'cash',
        })
        assert resp.status_code == 201
        assert resp.data['payment']['paid_amount'] == '200000'
        assert resp.data['payment']['status'] == 'partial'
        assert resp.data['transaction']['receipt_number']
        assert resp.data['transaction']['debt_after'] == '300000'
        assert resp.data['transaction']['receipt_url'] == f"/finance/receipt/{resp.data['transaction']['id']}/"

    def test_multiple_calls_accumulate_into_one_payment(self, finance_user, student):
        client = auth_client(finance_user)
        for amount in (200000, 150000, 150000):
            resp = client.post('/api/v1/finance/transactions/record/', {
                'student': str(student.id), 'month': 4, 'year': 2026,
                'amount': amount, 'payment_type': 'cash',
            })
            assert resp.status_code == 201

        payment = Payment.objects.get(student=student, month=4, year=2026)
        assert payment.paid_amount == 500000
        assert payment.status == Payment.Status.PAID
        assert PaymentTransaction.objects.filter(payment=payment).count() == 3

    def test_teacher_cannot_record_payment(self, teacher_user, student):
        client = auth_client(teacher_user)
        resp = client.post('/api/v1/finance/transactions/record/', {
            'student': str(student.id), 'month': 3, 'year': 2026, 'amount': 100000,
        })
        assert resp.status_code == 403

    def test_unauthenticated_cannot_record_payment(self, student):
        client = APIClient()
        resp = client.post('/api/v1/finance/transactions/record/', {
            'student': str(student.id), 'month': 3, 'year': 2026, 'amount': 100000,
        })
        assert resp.status_code == 401


@pytest.mark.django_db
class TestFinanceReadAccess:

    def test_finance_can_search_students(self, finance_user, student):
        client = auth_client(finance_user)
        resp = client.get('/api/v1/students/?search=Test')
        assert resp.status_code == 200

    def test_finance_can_list_payments(self, finance_user, student):
        Payment.objects.create(student=student, month=5, year=2026, amount=500000)
        client = auth_client(finance_user)
        resp = client.get('/api/v1/payments/')
        assert resp.status_code == 200

    def test_finance_can_view_student_summary(self, finance_user, student):
        client = auth_client(finance_user)
        resp = client.get(f'/api/v1/finance/students/{student.id}/summary/?month=6&year=2026')
        assert resp.status_code == 200
        assert resp.data['monthly_fee'] == 500000

    def test_teacher_cannot_view_finance_summary(self, teacher_user, student):
        client = auth_client(teacher_user)
        resp = client.get(f'/api/v1/finance/students/{student.id}/summary/')
        assert resp.status_code == 403


@pytest.mark.django_db
class TestOverdueStatus:

    def test_unpaid_past_month_is_overdue(self, student, group):
        group.payment_due_day = 5
        group.save(update_fields=['payment_due_day'])
        payment = Payment.objects.create(
            student=student, group=group, month=1, year=2026, amount=500000,
        )
        assert payment.is_overdue is True
        assert payment.effective_status == 'overdue'

    def test_paid_is_never_overdue(self, student, group):
        payment = Payment.objects.create(
            student=student, group=group, month=1, year=2026,
            amount=500000, paid_amount=500000,
        )
        assert payment.status == Payment.Status.PAID
        assert payment.is_overdue is False
        assert payment.effective_status == 'paid'
