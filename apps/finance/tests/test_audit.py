import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.finance.models import Expense
from apps.groups.models import Group
from apps.notifications.models import ActivityLog
from apps.payments.models import Payment
from apps.students.models import Student
from apps.teachers.models import Teacher


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        phone='+998900000100', password='pass1234',
        full_name='Finance User', role=User.Role.FINANCE,
    )


@pytest.fixture
def group(db):
    return Group.objects.create(name='Audit Group', start_date='2026-01-01',
                                start_time='09:00', end_time='10:00', monthly_fee=500000)


@pytest.fixture
def student(db, group):
    user = User.objects.create_user(
        phone='+998900000101', password='pass1234', full_name='Audit Student', role=User.Role.STUDENT,
    )
    return Student.objects.create(user=user, phone=user.phone, group=group)


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def last_log(action, model_name):
    return ActivityLog.objects.filter(action=action, model_name=model_name).order_by('-created_at').first()


@pytest.mark.django_db
class TestFinanceAuditTrail:

    def test_recording_payment_logs_create(self, finance_user, student):
        client = auth_client(finance_user)
        resp = client.post('/api/v1/finance/transactions/record/', {
            'student': str(student.id), 'month': 3, 'year': 2026, 'amount': 200000,
        })
        assert resp.status_code == 201
        log = last_log(ActivityLog.Action.CREATE, 'PaymentTransaction')
        assert log is not None
        assert log.user == finance_user

    def test_cancelling_transaction_logs_delete(self, finance_user, student):
        client = auth_client(finance_user)
        resp = client.post('/api/v1/finance/transactions/record/', {
            'student': str(student.id), 'month': 4, 'year': 2026, 'amount': 200000,
        })
        txn_id = resp.data['transaction']['id']
        del_resp = client.delete(f'/api/v1/finance/transactions/{txn_id}/')
        assert del_resp.status_code == 204
        log = last_log(ActivityLog.Action.DELETE, 'PaymentTransaction')
        assert log is not None
        assert str(log.object_id) == txn_id

    def test_editing_payment_logs_update(self, finance_user, student, group):
        payment = Payment.objects.create(student=student, group=group, month=5, year=2026, amount=500000)
        client = auth_client(finance_user)
        resp = client.patch(f'/api/v1/payments/{payment.id}/', {'note': 'edited', 'paid_amount': 200000})
        assert resp.status_code == 200
        log = last_log(ActivityLog.Action.UPDATE, 'Payment')
        assert log is not None
        assert log.user == finance_user
        assert log.changes['paid_amount'] == {'old': '0', 'new': '200000'}
        assert log.changes['note']['new'] == 'edited'
        # debt_amount is derived from paid_amount by Payment.save() — the diff
        # must reflect the model-computed value, not just the submitted field.
        assert log.changes['debt_amount'] == {'old': '500000', 'new': '300000'}

    def test_salary_created_and_updated_logged(self, finance_user):
        teacher_user = User.objects.create_user(
            phone='+998900000102', password='pass1234', full_name='Audit Teacher', role=User.Role.TEACHER,
        )
        teacher = Teacher.objects.create(user=teacher_user, phone=teacher_user.phone, salary=1000000)
        client = auth_client(finance_user)
        resp = client.post('/api/v1/teachers/salaries/', {
            'teacher': str(teacher.id), 'month': 6, 'year': 2026, 'amount': 1000000,
        })
        assert resp.status_code == 201
        assert last_log(ActivityLog.Action.CREATE, 'TeacherSalaryPayment') is not None

        salary_id = resp.data['id']
        resp2 = client.patch(f'/api/v1/teachers/salaries/{salary_id}/', {'bonus': 50000})
        assert resp2.status_code == 200
        log = last_log(ActivityLog.Action.UPDATE, 'TeacherSalaryPayment')
        assert log is not None
        assert log.user == finance_user
        assert log.changes['bonus'] == {'old': '0', 'new': '50000'}
        assert 'amount' not in log.changes  # unrelated field must not appear when unchanged

    def test_expense_created_updated_deleted_logged(self, finance_user):
        client = auth_client(finance_user)
        resp = client.post('/api/v1/finance/expenses/', {
            'name': 'Audit Expense', 'category': 'other', 'amount': 100000, 'expense_date': '2026-03-01',
        })
        assert resp.status_code == 201
        assert last_log(ActivityLog.Action.CREATE, 'Expense') is not None

        expense_id = resp.data['id']
        client.patch(f'/api/v1/finance/expenses/{expense_id}/', {'name': 'Renamed'})
        log = last_log(ActivityLog.Action.UPDATE, 'Expense')
        assert log is not None
        assert log.changes == {'name': {'old': 'Audit Expense', 'new': 'Renamed'}}

        client.delete(f'/api/v1/finance/expenses/{expense_id}/')
        assert last_log(ActivityLog.Action.DELETE, 'Expense') is not None
        assert not Expense.objects.filter(id=expense_id).exists()

    def test_asset_added_and_quantity_changed_logged(self, finance_user):
        client = auth_client(finance_user)
        resp = client.post('/api/v1/finance/assets/', {
            'name': 'Audit Asset', 'quantity': 5, 'purchase_price': 100000,
        })
        assert resp.status_code == 201
        assert last_log(ActivityLog.Action.CREATE, 'Asset') is not None

        asset_id = resp.data['id']
        client.patch(f'/api/v1/finance/assets/{asset_id}/', {'quantity': 8})
        log = last_log(ActivityLog.Action.UPDATE, 'Asset')
        assert log is not None
        assert 'x8' in log.object_repr
        assert log.changes == {'quantity': {'old': '5', 'new': '8'}}

    def test_finance_can_view_activity_log(self, finance_user):
        ActivityLog.objects.create(user=finance_user, action='create', model_name='Expense', object_repr='x')
        client = auth_client(finance_user)
        resp = client.get('/api/v1/notifications/activity/')
        assert resp.status_code == 200


@pytest.mark.django_db
class TestPaymentUpsertAuditLabel:
    """
    FIN-004: /api/v1/payments/ (apps.payments' legacy upsert endpoint, kept live
    for backward compatibility) previously logged every call as CREATE, even when
    it silently overwrote an existing Payment. It must now log UPDATE — with the
    old/new paid_amount — for the overwrite branch, and only log CREATE for an
    actual first-time Payment.
    """

    def test_first_call_logs_create(self, finance_user, student, group):
        client = auth_client(finance_user)
        resp = client.post('/api/v1/payments/', {
            'student': str(student.id), 'group': str(group.id),
            'month': 9, 'year': 2026, 'paid_amount': 100000,
        })
        assert resp.status_code == 201
        assert last_log(ActivityLog.Action.CREATE, 'Payment') is not None
        assert last_log(ActivityLog.Action.UPDATE, 'Payment') is None

    def test_second_call_for_same_bill_logs_update_not_create(self, finance_user, student, group):
        client = auth_client(finance_user)
        # `group` is deliberately omitted here, matching the real payload shape the
        # (now-retired) payments.html quick-pay flow used to send: PaymentCreateSerializer
        # backfills group=student.group inside its custom validate() hook, which runs
        # *after* DRF's auto unique-together validator — so explicitly passing `group`
        # would hit that validator first and 400 instead of reaching the upsert branch.
        client.post('/api/v1/payments/', {
            'student': str(student.id), 'month': 10, 'year': 2026, 'paid_amount': 100000,
        })
        create_count_before = ActivityLog.objects.filter(
            action=ActivityLog.Action.CREATE, model_name='Payment').count()

        resp = client.post('/api/v1/payments/', {
            'student': str(student.id), 'month': 10, 'year': 2026, 'paid_amount': 250000,
        })
        assert resp.status_code == 201  # HTTP contract unchanged — only the audit label is fixed

        create_count_after = ActivityLog.objects.filter(
            action=ActivityLog.Action.CREATE, model_name='Payment').count()
        assert create_count_after == create_count_before, "second upsert call must not log another CREATE"

        log = last_log(ActivityLog.Action.UPDATE, 'Payment')
        assert log is not None
        assert log.user == finance_user
        assert log.changes['paid_amount'] == {'old': '100000', 'new': '250000'}


@pytest.mark.django_db
class TestAuditChangesNoSensitiveData:
    """Confirms the new `changes` payloads only ever contain the whitelisted
    business fields — never FK/user/credential-shaped data."""

    FORBIDDEN_KEYS = {'password', 'token', 'access', 'refresh', 'secret',
                       'received_by', 'paid_by', 'created_by', 'user'}

    def test_payment_update_changes_has_no_forbidden_keys(self, finance_user, student, group):
        payment = Payment.objects.create(student=student, group=group, month=11, year=2026, amount=500000)
        client = auth_client(finance_user)
        client.patch(f'/api/v1/payments/{payment.id}/', {'paid_amount': 500000, 'note': 'paid in full'})
        log = last_log(ActivityLog.Action.UPDATE, 'Payment')
        assert log.changes
        assert not (set(log.changes.keys()) & self.FORBIDDEN_KEYS)

    def test_salary_update_changes_has_no_forbidden_keys(self, finance_user):
        teacher_user = User.objects.create_user(
            phone='+998900000103', password='pass1234', full_name='Audit Teacher 2', role=User.Role.TEACHER,
        )
        teacher = Teacher.objects.create(user=teacher_user, phone=teacher_user.phone, salary=1000000)
        client = auth_client(finance_user)
        resp = client.post('/api/v1/teachers/salaries/', {
            'teacher': str(teacher.id), 'month': 12, 'year': 2026, 'amount': 1000000,
        })
        client.patch(f"/api/v1/teachers/salaries/{resp.data['id']}/", {'deductions': 20000})
        log = last_log(ActivityLog.Action.UPDATE, 'TeacherSalaryPayment')
        assert log.changes
        assert not (set(log.changes.keys()) & self.FORBIDDEN_KEYS)
