"""
Cross-cutting KUMUSH security matrix: IDOR, field forgery, role boundaries,
and the negative-balance invariant. Individual endpoints already have their
own permission tests (test_manual_adjustment.py, test_purchase_lifecycle.py,
test_store.py, test_kumush_report.py) — this file covers what those don't:
cross-endpoint role sweeps and direct-model-bypass attempts.
"""
import pytest
from django.db import IntegrityError

from apps.store.models import KumushTransaction, PurchaseRequest, StoreItem
from apps.store.tests.conftest import auth_client


@pytest.mark.django_db
class TestNegativeBalanceImpossible:

    def test_db_level_check_constraint_blocks_negative_coins(self, student_a):
        """Defense-in-depth beneath apply_kumush_and_xp()'s own application-
        level refusal: Student.coins is a PositiveIntegerField, which Django
        backs with a DB-level CHECK (coins >= 0) constraint — even a direct
        .update() bypassing all application logic cannot make it negative."""
        _, student = student_a
        from apps.students.models import Student
        with pytest.raises(IntegrityError):
            Student.objects.filter(pk=student.pk).update(coins=-1)

    def test_application_layer_also_refuses(self, student_b):
        _, student = student_b  # coins=50
        txn = student.apply_kumush_and_xp(coins_delta=-51, reason='overspend attempt')
        assert txn is None
        student.refresh_from_db()
        assert student.coins == 50


@pytest.mark.django_db
class TestKumushTransactionIDOR:

    def test_student_cannot_view_other_students_transactions(self, student_a, student_b):
        _, sa = student_a
        _, sb = student_b
        sa.apply_kumush_and_xp(coins_delta=10, reason='a earns', source_type='manual')
        sb.apply_kumush_and_xp(coins_delta=20, reason='b earns', source_type='manual')

        client = auth_client(sa.user)
        resp = client.get('/api/v1/store/transactions/')
        results = resp.data.get('results', resp.data)
        assert all(r['student'] == sa.id for r in results)

    def test_student_cannot_use_query_param_to_view_others_transactions(self, student_a, student_b):
        """Even explicitly asking for another student's data via ?student=
        must not leak it — get_queryset scopes to the caller's own student
        profile before any filterset_fields are applied."""
        _, sa = student_a
        _, sb = student_b
        sb.apply_kumush_and_xp(coins_delta=20, reason='b earns', source_type='manual')

        client = auth_client(sa.user)
        resp = client.get(f'/api/v1/store/transactions/?student={sb.id}')
        results = resp.data.get('results', resp.data)
        assert results == []


@pytest.mark.django_db
class TestFieldForgery:

    def test_manual_adjustment_cannot_forge_type(self, admin_user, student_a):
        """type is derived server-side from the sign of amount — a client-
        supplied 'type' in the body must be silently ignored, never trusted."""
        _, student = student_a
        client = auth_client(admin_user)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': str(student.pk), 'amount': 10, 'reason': 'test',
            'type': 'spend',  # attempt to forge — amount is +10, should be EARN regardless
        }, format='json')
        assert resp.status_code == 201
        txn = KumushTransaction.objects.get(student=student)
        assert txn.type == KumushTransaction.Type.EARN

    def test_manual_adjustment_cannot_forge_source_type(self, admin_user, student_a):
        """source_type is hardcoded to 'manual' for this endpoint — a client
        cannot impersonate an automated source like 'attendance' or 'zukko'
        to make a manual credit look like a system-triggered reward."""
        _, student = student_a
        client = auth_client(admin_user)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': str(student.pk), 'amount': 10, 'reason': 'test',
            'source_type': 'attendance', 'source_id': '999',
        }, format='json')
        assert resp.status_code == 201
        txn = KumushTransaction.objects.get(student=student)
        assert txn.source_type == 'manual'


@pytest.mark.django_db
class TestFinanceCannotManipulateKumushAnywhere:
    """Finance has no KUMUSH powers at all per the permission matrix — swept
    across every admin-only KUMUSH endpoint in one place."""

    def test_finance_cannot_view_store_items(self, finance_user):
        client = auth_client(finance_user)
        assert client.get('/api/v1/store/items/').status_code == 403

    def test_finance_cannot_view_requests(self, finance_user):
        client = auth_client(finance_user)
        assert client.get('/api/v1/store/requests/').status_code == 403

    def test_finance_cannot_approve(self, finance_user, admin_user, student_a):
        item = StoreItem.objects.create(name='X', price=10, stock=5)
        _, student = student_a
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=10)
        client = auth_client(finance_user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/approve/')
        assert resp.status_code == 403

    def test_finance_cannot_reject(self, finance_user, student_a):
        item = StoreItem.objects.create(name='X', price=10, stock=5)
        _, student = student_a
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=10)
        client = auth_client(finance_user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/reject/')
        assert resp.status_code == 403

    def test_finance_cannot_refund(self, finance_user, student_a):
        item = StoreItem.objects.create(name='X', price=10, stock=5)
        _, student = student_a
        pr = PurchaseRequest.objects.create(
            student=student, item=item, price_at_request=10,
            status=PurchaseRequest.Status.APPROVED,
        )
        client = auth_client(finance_user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/refund/')
        assert resp.status_code == 403

    def test_finance_cannot_manually_adjust(self, finance_user, student_a):
        _, student = student_a
        client = auth_client(finance_user)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': str(student.pk), 'amount': 10, 'reason': 'x',
        }, format='json')
        assert resp.status_code == 403

    def test_finance_cannot_view_kumush_report(self, finance_user):
        client = auth_client(finance_user)
        assert client.get('/api/v1/store/kumush-report/').status_code == 403

    def test_finance_cannot_view_summary(self, finance_user):
        client = auth_client(finance_user)
        assert client.get('/api/v1/store/summary/').status_code == 403


@pytest.mark.django_db
class TestStudentSelfProfileCannotEditCoins:

    def test_student_cannot_patch_own_profile_at_all(self, student_a):
        """StudentViewSet restricts update/partial_update to IsAdmin —
        students have no write path to their own Student record, coins
        included. Verified at the permission layer (defense-in-depth: even
        if this changed, StudentUpdateSerializer's field list separately
        excludes coins/xp_points — see apps/students/serializers.py)."""
        _, student = student_a
        client = auth_client(student.user)
        resp = client.patch(f'/api/v1/students/{student.id}/', {'coins': 999999}, format='json')
        assert resp.status_code in (403, 404)
        student.refresh_from_db()
        assert student.coins == 300


@pytest.mark.django_db
class TestMalformedAndInvalidInputs:

    def test_purchase_request_rejects_invalid_item_id(self, student_a):
        client = auth_client(student_a[0])
        resp = client.post('/api/v1/store/requests/', {'item': '00000000-0000-0000-0000-000000000000'})
        assert resp.status_code == 400

    def test_purchase_request_rejects_malformed_item_id(self, student_a):
        client = auth_client(student_a[0])
        resp = client.post('/api/v1/store/requests/', {'item': 'not-a-uuid'})
        assert resp.status_code == 400

    def test_manual_adjustment_rejects_invalid_student_id(self, admin_user):
        client = auth_client(admin_user)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': '00000000-0000-0000-0000-000000000000', 'amount': 10, 'reason': 'x',
        }, format='json')
        assert resp.status_code == 400

    def test_manual_adjustment_rejects_malformed_student_id(self, admin_user):
        client = auth_client(admin_user)
        resp = client.post('/api/v1/store/kumush-adjustment/', {
            'student': 'not-a-uuid', 'amount': 10, 'reason': 'x',
        }, format='json')
        assert resp.status_code == 400

    def test_purchase_request_create_ignores_forged_status(self, student_a):
        """status is read_only on PurchaseRequestSerializer — a client
        cannot self-approve by sending status in the create body."""
        item = StoreItem.objects.create(name='Kitob', price=10, stock=5)
        client = auth_client(student_a[0])
        resp = client.post('/api/v1/store/requests/', {'item': str(item.id), 'status': 'approved'})
        assert resp.status_code == 201
        assert resp.data['status'] == 'pending'
