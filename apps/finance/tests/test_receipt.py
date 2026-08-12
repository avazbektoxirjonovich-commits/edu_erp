import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.finance.models import PaymentTransaction
from apps.groups.models import Group
from apps.payments.models import Payment
from apps.students.models import Student


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        phone='+998900000010', password='pass1234',
        full_name='Finance User', role=User.Role.FINANCE,
    )


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        phone='+998900000011', password='pass1234',
        full_name='Teacher User', role=User.Role.TEACHER,
    )


@pytest.fixture
def group(db):
    return Group.objects.create(
        name='Receipt Group', start_date='2026-01-01',
        start_time='09:00', end_time='10:00', monthly_fee=500000,
    )


@pytest.fixture
def student(db, group):
    user = User.objects.create_user(
        phone='+998900000012', password='pass1234',
        full_name='Receipt Student', role=User.Role.STUDENT,
    )
    return Student.objects.create(user=user, phone=user.phone, group=group)


@pytest.fixture
def payment(student, group):
    return Payment.objects.create(student=student, group=group, month=2, year=2026, amount=500000)


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestDebtAfterSnapshot:

    def test_debt_after_reflects_state_at_creation_time(self, payment):
        t1 = PaymentTransaction.objects.create(payment=payment, amount=200000)
        assert t1.debt_after == 300000

        t2 = PaymentTransaction.objects.create(payment=payment, amount=300000)
        assert t2.debt_after == 0

        # Old receipt's frozen snapshot must NOT change after a later payment.
        t1.refresh_from_db()
        assert t1.debt_after == 300000

    def test_receipt_number_present_on_first_save(self, payment):
        t = PaymentTransaction.objects.create(payment=payment, amount=100000)
        assert t.debt_after is not None


@pytest.mark.django_db
class TestReceiptEndpoints:

    def test_finance_can_view_transaction_detail(self, finance_user, payment):
        t = PaymentTransaction.objects.create(payment=payment, amount=200000)
        client = auth_client(finance_user)
        resp = client.get(f'/api/v1/finance/transactions/{t.id}/')
        assert resp.status_code == 200
        assert resp.data['receipt_number'] == t.receipt_number
        assert resp.data['debt_after'] == '300000'
        assert resp.data['receipt_url'] == f'/finance/receipt/{t.id}/'

    def test_teacher_cannot_view_transaction_detail(self, teacher_user, payment):
        t = PaymentTransaction.objects.create(payment=payment, amount=200000)
        client = auth_client(teacher_user)
        resp = client.get(f'/api/v1/finance/transactions/{t.id}/')
        assert resp.status_code == 403

    def test_finance_can_download_receipt_pdf(self, finance_user, payment):
        t = PaymentTransaction.objects.create(payment=payment, amount=500000)
        client = auth_client(finance_user)
        resp = client.get(f'/api/v1/finance/transactions/{t.id}/receipt-pdf/')
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'application/pdf'
        assert resp.content.startswith(b'%PDF')

    def test_teacher_cannot_download_receipt_pdf(self, teacher_user, payment):
        t = PaymentTransaction.objects.create(payment=payment, amount=200000)
        client = auth_client(teacher_user)
        resp = client.get(f'/api/v1/finance/transactions/{t.id}/receipt-pdf/')
        assert resp.status_code == 403

    def test_receipt_pdf_404_for_unknown_transaction(self, finance_user):
        client = auth_client(finance_user)
        resp = client.get('/api/v1/finance/transactions/00000000-0000-0000-0000-000000000000/receipt-pdf/')
        assert resp.status_code == 404
