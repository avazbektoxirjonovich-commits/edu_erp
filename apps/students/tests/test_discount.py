"""O'quvchining doimiy oylik chegirmasi: ochilganda beriladi, hisobga avtomat qo'llanadi."""
import pytest
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.groups.models import Group
from apps.notifications.models import ActivityLog
from apps.payments.models import Payment
from apps.payments.services import (
    generate_monthly_invoices,
    get_or_create_invoice,
    record_payment,
    remaining_debt,
)
from apps.students.models import Student

URL = '/api/v1/students/'


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(phone='+998903330001', password='pass1234',
                                    full_name='Admin', role=User.Role.ADMIN)


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(phone='+998903330002', password='pass1234',
                                    full_name='Kassir', role=User.Role.FINANCE)


@pytest.fixture
def group(db):
    return Group.objects.create(name='Chegirma guruh', start_date='2026-01-01',
                                start_time='09:00', end_time='10:00')


def payload(group, **extra):
    return {'full_name': "Chegirmali O'quvchi", 'phone': '+998903330010',
            'password': 'pass1234', 'group': str(group.id), 'monthly_fee': 500000, **extra}


def make_student(group, *, fee=500000, discount=0, phone='+998903330099'):
    user = User.objects.create_user(phone=phone, password='pass1234',
                                    full_name="Test O'quvchi", role=User.Role.STUDENT)
    return Student.objects.create(user=user, phone=phone, group=group,
                                  monthly_fee=fee, discount=discount)


@pytest.mark.django_db
class TestDiscountOnCreate:

    def test_discount_saved_when_student_created(self, admin_user, group):
        resp = auth_client(admin_user).post(URL, payload(group, discount=100000), format='json')
        assert resp.status_code == 201
        student = Student.objects.get()
        assert (student.monthly_fee, student.discount) == (500000, 100000)
        assert student.net_monthly_fee == 400000

    def test_discount_optional_defaults_to_zero(self, admin_user, group):
        resp = auth_client(admin_user).post(URL, payload(group), format='json')
        assert resp.status_code == 201
        assert Student.objects.get().discount == 0

    def test_discount_cannot_exceed_fee(self, admin_user, group):
        resp = auth_client(admin_user).post(URL, payload(group, discount=500001), format='json')
        assert resp.status_code == 400
        assert 'discount' in resp.data
        assert not Student.objects.exists()

    def test_negative_discount_rejected(self, admin_user, group):
        resp = auth_client(admin_user).post(URL, payload(group, discount=-1), format='json')
        assert resp.status_code == 400
        assert not Student.objects.exists()

    def test_full_discount_allowed(self, admin_user, group):
        resp = auth_client(admin_user).post(URL, payload(group, discount=500000), format='json')
        assert resp.status_code == 201
        assert Student.objects.get().net_monthly_fee == 0


@pytest.mark.django_db
class TestDiscountEditing:

    def test_admin_can_change_discount_and_it_is_logged(self, admin_user, group):
        student = make_student(group, discount=50000)
        resp = auth_client(admin_user).patch(f'{URL}{student.id}/', {'discount': 120000}, format='json')
        assert resp.status_code == 200
        student.refresh_from_db()
        assert student.discount == 120000
        log = ActivityLog.objects.filter(model_name='Student', action='update').latest('created_at')
        assert log.changes['discount'] == {'old': '50000', 'new': '120000'}

    def test_discount_above_new_fee_rejected(self, admin_user, group):
        student = make_student(group, fee=500000, discount=400000)
        resp = auth_client(admin_user).patch(f'{URL}{student.id}/', {'monthly_fee': 300000}, format='json')
        assert resp.status_code == 400
        student.refresh_from_db()
        assert (student.monthly_fee, student.discount) == (500000, 400000)

    def test_fee_and_discount_can_be_lowered_together(self, admin_user, group):
        student = make_student(group, fee=500000, discount=400000)
        resp = auth_client(admin_user).patch(
            f'{URL}{student.id}/', {'monthly_fee': 300000, 'discount': 100000}, format='json')
        assert resp.status_code == 200
        student.refresh_from_db()
        assert (student.monthly_fee, student.discount) == (300000, 100000)

    def test_finance_cannot_touch_discount(self, finance_user, group):
        student = make_student(group, discount=0)
        resp = auth_client(finance_user).patch(f'{URL}{student.id}/', {'discount': 100000}, format='json')
        assert resp.status_code == 403
        student.refresh_from_db()
        assert student.discount == 0

    def test_db_constraint_blocks_discount_above_fee(self, group):
        student = make_student(group, fee=500000, discount=0)
        student.discount = 600000
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                student.save(update_fields=['discount'])


@pytest.mark.django_db
class TestDiscountOnInvoices:

    def test_new_invoice_carries_student_discount(self, group):
        student = make_student(group, fee=500000, discount=150000)
        invoice, created = get_or_create_invoice(student, 10, 2026)
        assert created
        assert (invoice.amount, invoice.discount) == (500000, 150000)
        assert remaining_debt(invoice) == 350000

    def test_monthly_generation_applies_discount(self, group):
        make_student(group, fee=500000, discount=200000, phone='+998903330111')
        generate_monthly_invoices(11, 2026)
        invoice = Payment.objects.get()
        assert (invoice.amount, invoice.discount) == (500000, 200000)

    def test_existing_invoices_unchanged_when_discount_changes(self, group):
        student = make_student(group, fee=500000, discount=100000)
        invoice, _ = get_or_create_invoice(student, 10, 2026)
        student.discount = 400000
        student.save(update_fields=['discount'])
        invoice.refresh_from_db()
        assert invoice.discount == 100000          # eski hisob muhrlangan
        new_invoice, _ = get_or_create_invoice(student, 11, 2026)
        assert new_invoice.discount == 400000      # yangi hisobga yangi chegirma

    def test_payment_above_discounted_debt_rejected(self, admin_user, group):
        student = make_student(group, fee=500000, discount=150000)
        with pytest.raises(ValidationError):
            record_payment(student=student, month=10, year=2026, amount=400000,
                           payment_type='cash', note='', user=admin_user)

    def test_discounted_debt_can_be_closed(self, admin_user, group):
        student = make_student(group, fee=500000, discount=150000)
        record_payment(student=student, month=10, year=2026, amount=350000,
                       payment_type='cash', note='', user=admin_user)
        invoice = Payment.objects.get()
        assert (invoice.paid_amount, invoice.debt_amount) == (350000, 0)
        assert invoice.status == Payment.Status.PAID

    def test_full_discount_invoice_needs_no_payment(self, group):
        student = make_student(group, fee=500000, discount=500000)
        invoice, _ = get_or_create_invoice(student, 10, 2026)
        assert remaining_debt(invoice) == 0
        assert invoice.debt_amount == 0


@pytest.mark.django_db
class TestDiscountHelpers:
    """Xavfsizlik to'ri: baza cheklovi chetlab o'tilsa ham chegirma narxdan oshmaydi."""

    def test_effective_discount_never_exceeds_fee(self):
        student = Student(monthly_fee=100000, discount=500000)
        assert student.effective_discount == 100000
        assert student.net_monthly_fee == 0

    def test_no_fee_means_no_discount(self):
        student = Student(monthly_fee=None, discount=50000)
        assert (student.effective_discount, student.net_monthly_fee) == (0, 0)
