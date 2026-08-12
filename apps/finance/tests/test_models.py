import pytest

from apps.accounts.models import User
from apps.finance.models import Asset, PaymentTransaction
from apps.payments.models import Payment
from apps.students.models import Student


@pytest.fixture
def student(db):
    user = User.objects.create_user(
        phone='+998901112233', password='pass1234',
        full_name='Test Student', role=User.Role.STUDENT,
    )
    return Student.objects.create(user=user, phone='+998901112233')


@pytest.fixture
def payment(student):
    return Payment.objects.create(
        student=student, month=1, year=2026, amount=500000,
    )


@pytest.mark.django_db
class TestPaymentTransactionSync:

    def test_single_partial_transaction_updates_payment(self, payment):
        PaymentTransaction.objects.create(payment=payment, amount=200000)
        payment.refresh_from_db()
        assert payment.paid_amount == 200000
        assert payment.debt_amount == 300000
        assert payment.status == Payment.Status.PARTIAL

    def test_multiple_transactions_sum_to_paid(self, payment):
        PaymentTransaction.objects.create(payment=payment, amount=200000)
        PaymentTransaction.objects.create(payment=payment, amount=150000)
        PaymentTransaction.objects.create(payment=payment, amount=150000)
        payment.refresh_from_db()
        assert payment.paid_amount == 500000
        assert payment.debt_amount == 0
        assert payment.status == Payment.Status.PAID

    def test_deleting_transaction_resyncs_payment(self, payment):
        t1 = PaymentTransaction.objects.create(payment=payment, amount=200000)
        PaymentTransaction.objects.create(payment=payment, amount=150000)
        t1.delete()
        payment.refresh_from_db()
        assert payment.paid_amount == 150000
        assert payment.status == Payment.Status.PARTIAL

    def test_receipt_number_is_generated_and_unique(self, payment):
        t1 = PaymentTransaction.objects.create(payment=payment, amount=100000)
        t2 = PaymentTransaction.objects.create(payment=payment, amount=100000)
        assert t1.receipt_number
        assert t2.receipt_number
        assert t1.receipt_number != t2.receipt_number


@pytest.mark.django_db
class TestAsset:

    def test_total_value_computed(self):
        asset = Asset.objects.create(name='Kompyuter', quantity=10, purchase_price=4000000)
        assert asset.total_value == 40000000
