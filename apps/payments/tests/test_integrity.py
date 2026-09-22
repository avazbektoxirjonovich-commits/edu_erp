"""
1-bosqich — pul yozuvlarining ishonchliligi.
Har bir test bitta "nozik nuqta" yopilganini isbotlaydi.
"""
import importlib
from datetime import date
from io import StringIO

import pytest
from django.apps import apps as django_apps
from django.core.management import call_command
from django.db.models import ProtectedError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.finance.models import PaymentTransaction
from apps.finance.services import compute_financial_summary
from apps.groups.models import Group
from apps.payments.models import Payment
from apps.students.models import Student
from apps.teachers.models import Teacher

RECORD = '/api/v1/finance/transactions/record/'


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def make_user(phone, role, name='User'):
    return User.objects.create_user(phone=phone, password='pass1234', full_name=name, role=role)


@pytest.fixture
def finance_user(db):
    return make_user('+998901110001', User.Role.FINANCE, 'Kassir')


@pytest.fixture
def admin_user(db):
    return make_user('+998901110002', User.Role.ADMIN, 'Admin')


@pytest.fixture
def group(db):
    return Group.objects.create(name='G1', start_date='2026-01-01', start_time='09:00',
                                end_time='10:00')


@pytest.fixture
def student(db, group):
    user = make_user('+998901110003', User.Role.STUDENT, 'Ali Valiyev')
    return Student.objects.create(user=user, phone=user.phone, group=group, monthly_fee=500000)


def pay(client, student, amount, month=9, year=2026, **extra):
    return client.post(RECORD, {'student': str(student.id), 'month': month, 'year': year,
                                'amount': amount, **extra})


# ── Ortiqcha to'lov ─────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestOverpayment:

    def test_amount_above_remaining_debt_rejected(self, finance_user, student):
        client = auth_client(finance_user)
        assert pay(client, student, 300000).status_code == 201
        resp = pay(client, student, 300000)
        assert resp.status_code == 400
        assert '200,000' in str(resp.data['amount'])
        assert PaymentTransaction.objects.count() == 1

    def test_exact_remaining_debt_accepted(self, finance_user, student):
        client = auth_client(finance_user)
        pay(client, student, 300000)
        assert pay(client, student, 200000).status_code == 201
        payment = Payment.objects.get(student=student, month=9, year=2026)
        assert payment.status == Payment.Status.PAID
        assert payment.debt_amount == 0

    def test_fully_paid_month_rejects_more(self, finance_user, student):
        client = auth_client(finance_user)
        pay(client, student, 500000)
        resp = pay(client, student, 1000)
        assert resp.status_code == 400
        assert "to'liq to'langan" in str(resp.data['amount'])

    def test_student_without_price_rejected(self, finance_user, db):
        user = make_user('+998901110004', User.Role.STUDENT)
        lonely = Student.objects.create(user=user, phone=user.phone, group=None)
        resp = pay(auth_client(finance_user), lonely, 1000)
        assert resp.status_code == 400
        assert 'narx belgilanmagan' in str(resp.data['amount'])

    def test_discount_lowers_what_can_be_accepted(self, finance_user, admin_user, student):
        client = auth_client(finance_user)
        pay(client, student, 100000)
        payment = Payment.objects.get(student=student)
        auth_client(admin_user).patch(f'/api/v1/payments/{payment.id}/', {'discount': 100000})
        assert pay(client, student, 400000).status_code == 400
        assert pay(client, student, 300000).status_code == 201

    def test_legacy_unknown_type_cannot_be_chosen(self, finance_user, student):
        resp = pay(auth_client(finance_user), student, 1000, payment_type='unknown')
        assert resp.status_code == 400


# ── Chek o'chirilmaydi, bekor qilinadi ──────────────────────────────────────
@pytest.mark.django_db
class TestCancelReceipt:

    def _receipt(self, finance_user, student, amount=200000):
        return pay(auth_client(finance_user), student, amount).data['transaction']['id']

    def test_delete_not_allowed(self, admin_user, finance_user, student):
        txn_id = self._receipt(finance_user, student)
        resp = auth_client(admin_user).delete(f'/api/v1/finance/transactions/{txn_id}/')
        assert resp.status_code == 405
        assert PaymentTransaction.objects.filter(pk=txn_id).exists()

    def test_finance_cannot_cancel(self, finance_user, student):
        txn_id = self._receipt(finance_user, student)
        resp = auth_client(finance_user).post(f'/api/v1/finance/transactions/{txn_id}/cancel/',
                                              {'reason': 'Xato'})
        assert resp.status_code == 403
        assert not PaymentTransaction.objects.get(pk=txn_id).is_cancelled

    def test_reason_required(self, admin_user, finance_user, student):
        txn_id = self._receipt(finance_user, student)
        resp = auth_client(admin_user).post(f'/api/v1/finance/transactions/{txn_id}/cancel/',
                                            {'reason': '  '})
        assert resp.status_code == 400

    def test_cancel_restores_debt_and_keeps_receipt(self, admin_user, finance_user, student):
        txn_id = self._receipt(finance_user, student)
        resp = auth_client(admin_user).post(f'/api/v1/finance/transactions/{txn_id}/cancel/',
                                            {'reason': 'Kassir xato kiritdi'})
        assert resp.status_code == 200
        assert resp.data['payment']['paid_amount'] == '0'
        assert resp.data['payment']['debt_amount'] == '500000'
        txn = PaymentTransaction.objects.get(pk=txn_id)
        assert txn.is_cancelled
        assert txn.cancelled_by == admin_user
        assert txn.cancel_reason == 'Kassir xato kiritdi'
        # Chek ro'yxatda qoladi
        listing = auth_client(finance_user).get(f'/api/v1/finance/transactions/?student={student.id}')
        rows = listing.data.get('results', listing.data)
        assert [r['is_cancelled'] for r in rows] == [True]

    def test_cannot_cancel_twice(self, admin_user, finance_user, student):
        txn_id = self._receipt(finance_user, student)
        client = auth_client(admin_user)
        client.post(f'/api/v1/finance/transactions/{txn_id}/cancel/', {'reason': 'Birinchi'})
        resp = client.post(f'/api/v1/finance/transactions/{txn_id}/cancel/', {'reason': 'Ikkinchi'})
        assert resp.status_code == 400
        assert PaymentTransaction.objects.get(pk=txn_id).cancel_reason == 'Birinchi'

    def test_cancelled_receipt_excluded_from_income(self, admin_user, finance_user, student):
        client = auth_client(finance_user)
        keep = pay(client, student, 100000).data['transaction']
        gone = pay(client, student, 200000).data['transaction']
        auth_client(admin_user).post(f"/api/v1/finance/transactions/{gone['id']}/cancel/",
                                     {'reason': 'Qaytarildi'})
        day = date.fromisoformat(keep['paid_at'][:10])
        assert compute_financial_summary(day, day)['total_income'] == 100000
        dash = auth_client(admin_user).get('/api/v1/finance/dashboard/')
        assert dash.data['today_income'] == 100000

    def test_cancel_frees_room_for_correct_payment(self, admin_user, finance_user, student):
        client = auth_client(finance_user)
        wrong = pay(client, student, 500000).data['transaction']['id']
        assert pay(client, student, 1000).status_code == 400
        auth_client(admin_user).post(f'/api/v1/finance/transactions/{wrong}/cancel/', {'reason': 'Xato'})
        assert pay(client, student, 450000).status_code == 201

    def test_payment_date_follows_valid_receipts(self, admin_user, finance_user, student):
        txn_id = self._receipt(finance_user, student)
        payment = Payment.objects.get(student=student)
        assert payment.payment_date is not None
        auth_client(admin_user).post(f'/api/v1/finance/transactions/{txn_id}/cancel/', {'reason': 'Xato'})
        payment.refresh_from_db()
        assert payment.payment_date is None

    def test_money_records_protected_from_cascade_delete(self, finance_user, student):
        self._receipt(finance_user, student)
        with pytest.raises(ProtectedError):
            Payment.objects.get(student=student).delete()
        with pytest.raises(ProtectedError):
            student.delete()


# ── Har oy avtomatik hisob ──────────────────────────────────────────────────
@pytest.mark.django_db
class TestMonthlyInvoices:

    def test_generate_creates_invoices_and_is_idempotent(self, finance_user, student, group):
        user = make_user('+998901110005', User.Role.STUDENT)
        personal = Student.objects.create(user=user, phone=user.phone, group=group, monthly_fee=300000)
        user2 = make_user('+998901110006', User.Role.STUDENT)
        Student.objects.create(user=user2, phone=user2.phone, group=group,
                               status=Student.Status.INACTIVE)
        client = auth_client(finance_user)

        first = client.post('/api/v1/payments/generate/', {'month': 9, 'year': 2026})
        assert first.status_code == 200
        assert first.data['created'] == 2
        assert Payment.objects.get(student=student).amount == 500000
        assert Payment.objects.get(student=personal).amount == 300000

        second = client.post('/api/v1/payments/generate/', {'month': 9, 'year': 2026})
        assert second.data['created'] == 0
        assert second.data['existing'] == 2
        assert Payment.objects.count() == 2

    def test_generate_does_not_touch_existing_payments(self, finance_user, student):
        client = auth_client(finance_user)
        pay(client, student, 200000)
        client.post('/api/v1/payments/generate/', {'month': 9, 'year': 2026})
        payment = Payment.objects.get(student=student)
        assert payment.paid_amount == 200000
        assert payment.debt_amount == 300000

    def test_unpaid_student_now_visible_as_debtor(self, finance_user, student):
        """Asosiy nozik nuqta: to'lamagan o'quvchi qarzdorlar ro'yxatida ko'rinishi kerak."""
        client = auth_client(finance_user)
        before = client.get('/api/v1/finance/debts/?month=9&year=2026')
        assert before.data == []
        client.post('/api/v1/payments/generate/', {'month': 9, 'year': 2026})
        after = client.get('/api/v1/finance/debts/?month=9&year=2026')
        assert [row['student'] for row in after.data] == [student.id]
        assert after.data[0]['debt_amount'] == '500000'

    def test_teacher_cannot_generate(self, db, student):
        teacher = make_user('+998901110007', User.Role.TEACHER)
        resp = auth_client(teacher).post('/api/v1/payments/generate/', {'month': 9, 'year': 2026})
        assert resp.status_code == 403

    def test_invalid_month_rejected(self, finance_user):
        resp = auth_client(finance_user).post('/api/v1/payments/generate/', {'month': 13, 'year': 2026})
        assert resp.status_code == 400

    def test_teacher_sees_invoice_by_its_own_group_after_student_moves(self, finance_user, student, group):
        teacher_user = make_user('+998901110008', User.Role.TEACHER)
        group.teacher = Teacher.objects.create(user=teacher_user, phone=teacher_user.phone)
        group.save(update_fields=['teacher'])
        pay(auth_client(finance_user), student, 100000)
        student.group = Group.objects.create(name='G2', start_date='2026-01-01', start_time='11:00',
                                             end_time='12:00')
        student.save(update_fields=['group'])
        resp = auth_client(teacher_user).get('/api/v1/payments/')
        assert len(resp.data['results']) == 1


# ── Eski ma'lumotni ko'chirish migratsiyasi ─────────────────────────────────
@pytest.mark.django_db
class TestLegacyMigration:

    def _migration(self):
        return importlib.import_module('apps.finance.migrations.0006_legacy_receipts_for_uncovered_payments')

    def test_uncovered_paid_amount_gets_legacy_receipt_without_changing_totals(self, finance_user, student):
        pay(auth_client(finance_user), student, 100000)
        # Eski tizim: paid_amount chekisiz 300000 ga o'zgartirilgan (signal chetlab o'tilgan)
        Payment.objects.filter(student=student).update(paid_amount=300000, debt_amount=200000,
                                                        payment_date=date(2026, 9, 3))
        self._migration().create_legacy_receipts(django_apps, None)

        payment = Payment.objects.get(student=student)
        assert (payment.paid_amount, payment.debt_amount) == (300000, 200000)
        legacy = PaymentTransaction.objects.get(payment_type='unknown')
        assert legacy.amount == 200000
        assert legacy.receipt_number.startswith('ESKI')
        assert sum(t.amount for t in payment.transactions.valid()) == payment.paid_amount

        # Qayta ishga tushirilsa — yangi chek yaratilmaydi
        self._migration().create_legacy_receipts(django_apps, None)
        assert PaymentTransaction.objects.filter(payment_type='unknown').count() == 1

        # Orqaga qaytarish faqat eski-yozuv cheklarini o'chiradi
        self._migration().delete_legacy_receipts(django_apps, None)
        assert list(PaymentTransaction.objects.values_list('amount', flat=True)) == [100000]

    def test_audit_command_runs_read_only(self, finance_user, student):
        pay(auth_client(finance_user), student, 100000)
        before = (Payment.objects.count(), PaymentTransaction.objects.count())
        out = StringIO()
        call_command('payments_audit', '--month', '9', '--year', '2026', '--details', stdout=out)
        assert "TO'LOVLAR TEKSHIRUVI" in out.getvalue()
        assert (Payment.objects.count(), PaymentTransaction.objects.count()) == before
