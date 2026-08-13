"""
Manual KUMUSH adjustment — ADMIN/DEVELOPER only. Positive amount credits,
negative debits; must be atomic, validate balance, write a ledger row with
forensic fields, and log an ActivityLog entry. Student.coins is never
directly editable — only through this endpoint (or another ledger-backed path).
"""
import pytest

from apps.notifications.models import ActivityLog
from apps.store.models import KumushTransaction
from apps.store.tests.conftest import auth_client


@pytest.mark.django_db
class TestManualAdjustmentPermissions:

    def test_admin_can_adjust(self, admin_user, student_a):
        _, student = student_a
        client = auth_client(admin_user)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': str(student.pk), 'amount': 50, 'reason': 'Bonus mukofot',
        }, format='json')
        assert resp.status_code == 201

    def test_developer_can_adjust(self, developer_user, student_a):
        _, student = student_a
        client = auth_client(developer_user)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': str(student.pk), 'amount': 50, 'reason': 'Bonus mukofot',
        }, format='json')
        assert resp.status_code == 201

    def test_teacher_cannot_adjust(self, teacher_user, student_a):
        """Explicit requirement: teachers trigger attendance/homework rewards
        automatically but must NOT get arbitrary manual adjustment power."""
        _, student = student_a
        client = auth_client(teacher_user)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': str(student.pk), 'amount': 50, 'reason': 'Bonus',
        }, format='json')
        assert resp.status_code == 403
        student.refresh_from_db()
        assert student.coins == 300

    def test_finance_cannot_adjust(self, finance_user, student_a):
        _, student = student_a
        client = auth_client(finance_user)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': str(student.pk), 'amount': 50, 'reason': 'Bonus',
        }, format='json')
        assert resp.status_code == 403

    def test_student_cannot_adjust_own_kumush(self, student_a):
        student_user, student = student_a
        client = auth_client(student_user)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': str(student.pk), 'amount': 1000, 'reason': 'Self bonus',
        }, format='json')
        assert resp.status_code == 403
        student.refresh_from_db()
        assert student.coins == 300


@pytest.mark.django_db
class TestManualAdjustmentBehavior:

    def test_positive_amount_credits_with_ledger(self, admin_user, student_a):
        admin, student = admin_user, student_a[1]
        client = auth_client(admin)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': str(student.pk), 'amount': 75, 'reason': "Musobaqa g'olibi",
        }, format='json')

        assert resp.status_code == 201
        student.refresh_from_db()
        assert student.coins == 375

        txn = KumushTransaction.objects.get(student=student)
        assert txn.amount == 75
        assert txn.type == KumushTransaction.Type.EARN
        assert txn.reason == "Musobaqa g'olibi"
        assert txn.created_by == admin
        assert txn.balance_before == 300
        assert txn.balance_after == 375
        assert txn.source_type == 'manual'

        log = ActivityLog.objects.get(model_name='KumushTransaction', object_id=str(txn.pk))
        assert log.user == admin
        assert log.action == ActivityLog.Action.UPDATE

    def test_negative_amount_debits_with_ledger(self, admin_user, student_a):
        admin, student = admin_user, student_a[1]
        client = auth_client(admin)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': str(student.pk), 'amount': -100, 'reason': 'Xato tuzatish',
        }, format='json')

        assert resp.status_code == 201
        student.refresh_from_db()
        assert student.coins == 200

        txn = KumushTransaction.objects.get(student=student)
        assert txn.amount == -100
        assert txn.type == KumushTransaction.Type.SPEND
        assert txn.balance_before == 300
        assert txn.balance_after == 200

    def test_negative_amount_cannot_take_balance_below_zero(self, admin_user, student_b):
        admin, student = admin_user, student_b[1]  # coins=50
        client = auth_client(admin)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': str(student.pk), 'amount': -100, 'reason': 'Xato tuzatish',
        }, format='json')

        assert resp.status_code == 400
        student.refresh_from_db()
        assert student.coins == 50
        assert not KumushTransaction.objects.filter(student=student).exists()

    def test_zero_amount_rejected(self, admin_user, student_a):
        admin, student = admin_user, student_a[1]
        client = auth_client(admin)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': str(student.pk), 'amount': 0, 'reason': 'Nothing',
        }, format='json')
        assert resp.status_code == 400
        assert not KumushTransaction.objects.filter(student=student).exists()

    def test_missing_reason_rejected(self, admin_user, student_a):
        admin, student = admin_user, student_a[1]
        client = auth_client(admin)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': str(student.pk), 'amount': 10, 'reason': '',
        }, format='json')
        assert resp.status_code == 400
        assert not KumushTransaction.objects.filter(student=student).exists()

    def test_cannot_forge_created_by_or_balance_fields(self, admin_user, student_a):
        """The endpoint only accepts student/amount/reason — created_by,
        balance_before, balance_after must always be server-generated,
        never client-supplied."""
        admin, student = admin_user, student_a[1]
        client = auth_client(admin)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': str(student.pk), 'amount': 10, 'reason': 'test',
            'created_by': 'someone-else-id', 'balance_before': 999999, 'balance_after': 999999,
        }, format='json')

        assert resp.status_code == 201
        txn = KumushTransaction.objects.get(student=student)
        assert txn.created_by == admin
        assert txn.balance_before == 300
        assert txn.balance_after == 310
