"""4 ta to'lov turi: Naqd, Kartadan o'tkazma, Terminal orqali, Hisob raqam orqali."""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.finance.models import PaymentTransaction
from apps.groups.models import Group
from apps.students.models import Student

RECORD = '/api/v1/finance/transactions/record/'


@pytest.fixture
def finance_client(db):
    user = User.objects.create_user(phone='+998903330001', password='pass1234',
                                    full_name='Kassir', role=User.Role.FINANCE)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def student(db):
    group = Group.objects.create(name='T', start_date='2026-01-01', start_time='09:00', end_time='10:00')
    user = User.objects.create_user(phone='+998903330002', password='pass1234',
                                    full_name='Oquvchi', role=User.Role.STUDENT)
    return Student.objects.create(user=user, phone=user.phone, group=group, monthly_fee=1000000)


@pytest.mark.django_db
@pytest.mark.parametrize('code,label', [
    ('cash', 'Naqd'),
    ('card_transfer', "Kartadan o'tkazma"),
    ('terminal', 'Terminal orqali'),
    ('bank_account', 'Hisob raqam orqali'),
])
def test_each_payment_type_recorded_with_label(finance_client, student, code, label):
    resp = finance_client.post(RECORD, {'student': str(student.id), 'month': 9, 'year': 2026,
                                        'amount': 100000, 'payment_type': code})
    assert resp.status_code == 201
    assert resp.data['transaction']['payment_type'] == code
    assert resp.data['transaction']['payment_type_display'] == label


@pytest.mark.django_db
@pytest.mark.parametrize('code', ['card', 'transfer', 'unknown', 'click'])
def test_old_or_unknown_types_rejected(finance_client, student, code):
    resp = finance_client.post(RECORD, {'student': str(student.id), 'month': 9, 'year': 2026,
                                        'amount': 100000, 'payment_type': code})
    assert resp.status_code == 400
    assert not PaymentTransaction.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_migration_maps_old_types_and_back():
    # Guruh/o'quvchi jadvallari joriy holatda qoladi, faqat finance oldinga-orqaga yuriladi
    others = [('groups', '0007_remove_group_monthly_fee'), ('students', '0008_student_fee_label')]
    before = [('finance', '0006_legacy_receipts_for_uncovered_payments')] + others
    after = [('finance', '0007_payment_types')] + others
    executor = MigrationExecutor(connection)
    executor.migrate(before)
    old = executor.loader.project_state(before).apps
    User_, Group_, Student_, Payment_, Txn = (old.get_model('accounts', 'User'), old.get_model('groups', 'Group'),
                                               old.get_model('students', 'Student'),
                                               old.get_model('payments', 'Payment'),
                                               old.get_model('finance', 'PaymentTransaction'))
    g = Group_.objects.create(name='M', start_date='2026-01-01', start_time='09:00', end_time='10:00')
    u = User_.objects.create(phone='+998903330101', full_name='M', role='student')
    s = Student_.objects.create(user=u, phone=u.phone, group=g, monthly_fee=900000)
    p = Payment_.objects.create(student=s, group=g, month=9, year=2026, amount=900000)
    for i, t in enumerate(['cash', 'card', 'transfer']):
        Txn.objects.create(payment=p, amount=1000, payment_type=t, receipt_number=f'R{i}')

    executor = MigrationExecutor(connection)
    executor.migrate(after)
    new = executor.loader.project_state(after).apps.get_model('finance', 'PaymentTransaction')
    assert dict(new.objects.values_list('receipt_number', 'payment_type')) == {
        'R0': 'cash', 'R1': 'terminal', 'R2': 'card_transfer'}

    executor = MigrationExecutor(connection)
    executor.migrate(before)
    back = executor.loader.project_state(before).apps.get_model('finance', 'PaymentTransaction')
    assert dict(back.objects.values_list('receipt_number', 'payment_type')) == {
        'R0': 'cash', 'R1': 'card', 'R2': 'transfer'}

    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())
