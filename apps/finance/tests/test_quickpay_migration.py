"""
Phase 20.1 — regression tests for FIN-001 / FIN-002.

The live payment UI (templates/erp/payments.html: doPay/doBulkPay/printReceipt)
was migrated from the raw-overwrite `/api/v1/payments/` endpoint to the
authoritative, receipted `/api/v1/finance/transactions/record/` endpoint.
These tests pin down the exact business contract required by that migration:
Payment.paid_amount must be derived from the sum of PaymentTransaction rows,
never overwritten by client input, and every payment must be receipted.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.finance.models import PaymentTransaction
from apps.groups.models import Group
from apps.notifications.models import ActivityLog
from apps.payments.models import Payment
from apps.students.models import Student
from apps.teachers.models import Teacher


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        phone='+998900000200', password='pass1234',
        full_name='Finance User', role=User.Role.FINANCE,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        phone='+998900000201', password='pass1234',
        full_name='Admin User', role=User.Role.ADMIN,
    )


@pytest.fixture
def teacher_role_user(db):
    user = User.objects.create_user(
        phone='+998900000202', password='pass1234',
        full_name='Teacher User', role=User.Role.TEACHER,
    )
    Teacher.objects.create(user=user, phone=user.phone)
    return user


@pytest.fixture
def student_role_user(db):
    return User.objects.create_user(
        phone='+998900000203', password='pass1234',
        full_name='Student Role User', role=User.Role.STUDENT,
    )


@pytest.fixture
def parent_role_user(db):
    return User.objects.create_user(
        phone='+998900000204', password='pass1234',
        full_name='Parent Role User', role=User.Role.PARENT,
    )


@pytest.fixture
def group(db):
    return Group.objects.create(
        name='QuickPay Group', start_date='2026-01-01',
        start_time='09:00', end_time='10:00', monthly_fee=500000,
    )


@pytest.fixture
def student(db, group):
    user = User.objects.create_user(
        phone='+998900000205', password='pass1234',
        full_name='QuickPay Student', role=User.Role.STUDENT,
    )
    return Student.objects.create(user=user, phone=user.phone, group=group)


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def record(client, student, month, year, amount, note=''):
    return client.post('/api/v1/finance/transactions/record/', {
        'student': str(student.id), 'month': month, 'year': year,
        'amount': amount, 'payment_type': 'cash', 'note': note,
    })


@pytest.mark.django_db
class TestQuickPayAccumulatesNeverOverwrites:
    """TEST 1 / TEST 2 / TEST 5 — the core FIN-001 fix."""

    def test_installment_completing_the_bill_reaches_full_paid(self, finance_user, student):
        client = auth_client(finance_user)
        record(client, student, 6, 2026, 200000)
        resp = record(client, student, 6, 2026, 300000)

        assert resp.status_code == 201
        payment = Payment.objects.get(student=student, month=6, year=2026)
        assert payment.paid_amount == 500000
        assert payment.debt_amount == 0
        assert payment.status == Payment.Status.PAID
        assert PaymentTransaction.objects.filter(payment=payment).count() == 2

    def test_partial_installment_leaves_correct_remaining_debt(self, finance_user, student):
        client = auth_client(finance_user)
        record(client, student, 7, 2026, 200000)
        resp = record(client, student, 7, 2026, 100000)

        assert resp.status_code == 201
        payment = Payment.objects.get(student=student, month=7, year=2026)
        assert payment.paid_amount == 300000
        assert payment.debt_amount == 200000
        assert payment.status == Payment.Status.PARTIAL
        assert PaymentTransaction.objects.filter(payment=payment).count() == 2

    def test_quick_pay_of_suggested_debt_amount_does_not_overwrite_history(self, finance_user, student):
        """
        Regression for FIN-001: openQuickPay() pre-fills the amount field with the
        *outstanding debt* (a natural "pay off what's owed" default). Confirms that
        submitting exactly that suggested value now correctly adds to, rather than
        replaces, the already-recorded 200,000 — the original defect would have left
        paid_amount at 300,000 (the debt figure) instead of the correct 500,000.
        """
        client = auth_client(finance_user)
        first = record(client, student, 8, 2026, 200000)
        suggested_debt = first.data['payment']['debt_amount']
        assert suggested_debt == '300000'

        resp = record(client, student, 8, 2026, int(suggested_debt))

        payment = Payment.objects.get(student=student, month=8, year=2026)
        assert payment.paid_amount == 500000, "previous 200,000 installment must not be erased"
        assert payment.debt_amount == 0
        assert payment.status == Payment.Status.PAID
        assert resp.status_code == 201


@pytest.mark.django_db
class TestFirstPaymentOnUnpaidBill:
    """TEST 3."""

    def test_first_payment_creates_payment_and_transaction(self, finance_user, student):
        client = auth_client(finance_user)
        assert not Payment.objects.filter(student=student, month=9, year=2026).exists()

        resp = record(client, student, 9, 2026, 150000)

        assert resp.status_code == 201
        assert Payment.objects.filter(student=student, month=9, year=2026).count() == 1
        payment = Payment.objects.get(student=student, month=9, year=2026)
        assert payment.paid_amount == 150000
        assert payment.debt_amount == 500000 - 150000
        assert PaymentTransaction.objects.filter(payment=payment).count() == 1
        txn = PaymentTransaction.objects.get(payment=payment)
        assert txn.receipt_number


@pytest.mark.django_db
class TestRepeatedInstallmentsAccumulate:
    """TEST 4."""

    def test_three_installments_sum_correctly(self, finance_user, student):
        client = auth_client(finance_user)
        for amount in (200000, 150000, 150000):
            resp = record(client, student, 10, 2026, amount)
            assert resp.status_code == 201

        payment = Payment.objects.get(student=student, month=10, year=2026)
        assert payment.paid_amount == 500000
        assert payment.status == Payment.Status.PAID
        assert PaymentTransaction.objects.filter(payment=payment).count() == 3


@pytest.mark.django_db
class TestPaymentRecordingPermissions:
    """TEST 6."""

    def test_finance_allowed(self, finance_user, student):
        resp = record(auth_client(finance_user), student, 11, 2026, 100000)
        assert resp.status_code == 201

    def test_admin_allowed(self, admin_user, student):
        resp = record(auth_client(admin_user), student, 11, 2026, 100000)
        assert resp.status_code == 201

    def test_teacher_denied(self, teacher_role_user, student):
        resp = record(auth_client(teacher_role_user), student, 11, 2026, 100000)
        assert resp.status_code == 403

    def test_student_denied(self, student_role_user, student):
        resp = record(auth_client(student_role_user), student, 11, 2026, 100000)
        assert resp.status_code == 403

    def test_parent_denied(self, parent_role_user, student):
        resp = record(auth_client(parent_role_user), student, 11, 2026, 100000)
        assert resp.status_code == 403


@pytest.mark.django_db
class TestActivityLogAndReceiptRetrieval:
    """TEST 7 / TEST 8 / TEST 9 — the full record -> receipt -> PDF loop the UI now drives."""

    def test_successful_payment_creates_activity_log(self, finance_user, student):
        client = auth_client(finance_user)
        resp = record(client, student, 12, 2026, 100000)
        txn_id = resp.data['transaction']['id']

        log = ActivityLog.objects.filter(
            action=ActivityLog.Action.CREATE, model_name='PaymentTransaction',
        ).order_by('-created_at').first()
        assert log is not None
        assert log.user == finance_user
        assert str(log.object_id) == txn_id

    def test_receipt_endpoint_retrieves_newly_created_transaction(self, finance_user, student):
        client = auth_client(finance_user)
        resp = record(client, student, 1, 2027, 220000)
        txn_id = resp.data['transaction']['id']

        detail = client.get(f'/api/v1/finance/transactions/{txn_id}/')
        assert detail.status_code == 200
        assert detail.data['id'] == txn_id
        assert detail.data['amount'] == '220000'
        assert detail.data['receipt_number']

    def test_receipt_pdf_endpoint_works_for_created_transaction(self, finance_user, student):
        client = auth_client(finance_user)
        resp = record(client, student, 2, 2027, 180000)
        txn_id = resp.data['transaction']['id']

        pdf = client.get(f'/api/v1/finance/transactions/{txn_id}/receipt-pdf/')
        assert pdf.status_code == 200
        assert pdf['Content-Type'] == 'application/pdf'


@pytest.mark.django_db
class TestBulkPaymentCreatesPerStudentTransactions:
    """TEST 10 — mirrors doBulkPay()'s per-student loop against the new endpoint."""

    def test_each_student_gets_own_transaction_and_correct_totals(self, finance_user, group):
        students = []
        for i in range(3):
            user = User.objects.create_user(
                phone=f'+99890000021{i}', password='pass1234',
                full_name=f'Bulk Student {i}', role=User.Role.STUDENT,
            )
            students.append(Student.objects.create(user=user, phone=user.phone, group=group))

        client = auth_client(finance_user)
        for s in students:
            resp = record(client, s, 3, 2027, 500000, note='Ommaviy to\'lov')
            assert resp.status_code == 201

        for s in students:
            payment = Payment.objects.get(student=s, month=3, year=2027)
            assert payment.paid_amount == 500000
            assert payment.status == Payment.Status.PAID
            assert PaymentTransaction.objects.filter(payment=payment).count() == 1

        assert PaymentTransaction.objects.filter(
            payment__student__in=students, payment__month=3, payment__year=2027,
        ).count() == 3
