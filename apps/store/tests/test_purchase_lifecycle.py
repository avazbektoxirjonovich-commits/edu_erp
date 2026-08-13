"""
Store purchase request lifecycle: duplicate-pending guard, student
self-cancellation, and admin/developer refund. Explicitly does NOT touch
the existing approve()/reject() flow or its protections.
"""
import pytest

from apps.notifications.models import ActivityLog
from apps.store.models import KumushTransaction, PurchaseRequest, StoreItem
from apps.store.tests.conftest import auth_client


@pytest.mark.django_db
class TestDuplicatePendingGuard:

    def test_second_pending_request_for_same_item_blocked(self, student_a):
        item = StoreItem.objects.create(name='Kitob', price=10, stock=5)
        _, student = student_a
        client = auth_client(student.user)

        first = client.post('/api/v1/store/requests/', {'item': str(item.id)})
        second = client.post('/api/v1/store/requests/', {'item': str(item.id)})

        assert first.status_code == 201
        assert second.status_code == 409
        assert PurchaseRequest.objects.filter(student=student, item=item).count() == 1

    def test_new_request_allowed_after_rejection(self, student_a, admin_user):
        item = StoreItem.objects.create(name='Kitob', price=10, stock=5)
        _, student = student_a
        client = auth_client(student.user)
        admin_client = auth_client(admin_user)

        first = client.post('/api/v1/store/requests/', {'item': str(item.id)})
        pr_id = first.data['id']
        reject_resp = admin_client.post(f'/api/v1/store/requests/{pr_id}/reject/', {'reason': 'no'})
        assert reject_resp.status_code == 200

        second = client.post('/api/v1/store/requests/', {'item': str(item.id)})
        assert second.status_code == 201

    def test_new_request_allowed_after_approval(self, student_a, admin_user):
        item = StoreItem.objects.create(name='Kitob', price=10, stock=5)
        _, student = student_a
        client = auth_client(student.user)
        admin_client = auth_client(admin_user)

        first = client.post('/api/v1/store/requests/', {'item': str(item.id)})
        pr_id = first.data['id']
        approve_resp = admin_client.post(f'/api/v1/store/requests/{pr_id}/approve/')
        assert approve_resp.status_code == 200

        second = client.post('/api/v1/store/requests/', {'item': str(item.id)})
        assert second.status_code == 201


@pytest.mark.django_db
class TestCancellation:

    def test_student_can_cancel_own_pending_request(self, student_a):
        item = StoreItem.objects.create(name='Kitob', price=10, stock=5)
        _, student = student_a
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=10)
        client = auth_client(student.user)

        resp = client.post(f'/api/v1/store/requests/{pr.id}/cancel/')
        assert resp.status_code == 200
        pr.refresh_from_db()
        assert pr.status == PurchaseRequest.Status.CANCELLED
        assert pr.cancelled_at is not None

        student.refresh_from_db()
        item.refresh_from_db()
        assert student.coins == 300  # unaffected
        assert item.stock == 5       # unaffected
        assert not KumushTransaction.objects.filter(student=student).exists()

    def test_cannot_cancel_other_students_request(self, student_a, student_b):
        item = StoreItem.objects.create(name='Kitob', price=10, stock=5)
        _, owner = student_a
        _, other = student_b
        pr = PurchaseRequest.objects.create(student=owner, item=item, price_at_request=10)
        client = auth_client(other.user)

        resp = client.post(f'/api/v1/store/requests/{pr.id}/cancel/')
        assert resp.status_code == 403
        pr.refresh_from_db()
        assert pr.status == PurchaseRequest.Status.PENDING

    def test_admin_cannot_use_student_cancel_action(self, student_a, admin_user):
        """Cancellation is a self-service student action only — admins use
        approve/reject/refund, not cancel."""
        item = StoreItem.objects.create(name='Kitob', price=10, stock=5)
        _, student = student_a
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=10)
        client = auth_client(admin_user)

        resp = client.post(f'/api/v1/store/requests/{pr.id}/cancel/')
        assert resp.status_code == 403
        pr.refresh_from_db()
        assert pr.status == PurchaseRequest.Status.PENDING

    def test_cannot_cancel_approved_request(self, student_a):
        item = StoreItem.objects.create(name='Kitob', price=10, stock=5)
        _, student = student_a
        pr = PurchaseRequest.objects.create(
            student=student, item=item, price_at_request=10,
            status=PurchaseRequest.Status.APPROVED,
        )
        client = auth_client(student.user)

        resp = client.post(f'/api/v1/store/requests/{pr.id}/cancel/')
        assert resp.status_code == 400
        pr.refresh_from_db()
        assert pr.status == PurchaseRequest.Status.APPROVED

    def test_cannot_cancel_rejected_request(self, student_a):
        item = StoreItem.objects.create(name='Kitob', price=10, stock=5)
        _, student = student_a
        pr = PurchaseRequest.objects.create(
            student=student, item=item, price_at_request=10,
            status=PurchaseRequest.Status.REJECTED,
        )
        client = auth_client(student.user)

        resp = client.post(f'/api/v1/store/requests/{pr.id}/cancel/')
        assert resp.status_code == 400

    def test_cancellation_frees_slot_for_new_request(self, student_a):
        item = StoreItem.objects.create(name='Kitob', price=10, stock=5)
        _, student = student_a
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=10)
        client = auth_client(student.user)

        client.post(f'/api/v1/store/requests/{pr.id}/cancel/')
        second = client.post('/api/v1/store/requests/', {'item': str(item.id)})
        assert second.status_code == 201


@pytest.mark.django_db
class TestRefund:

    def _approved_purchase(self, student, item, admin_user):
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=item.price)
        admin_client = auth_client(admin_user)
        resp = admin_client.post(f'/api/v1/store/requests/{pr.id}/approve/')
        assert resp.status_code == 200
        return PurchaseRequest.objects.get(pk=pr.pk)

    def test_admin_can_refund_approved_purchase(self, admin_user, student_a):
        item = StoreItem.objects.create(name='Kitob', price=100, stock=3)
        _, student = student_a  # coins=300
        pr = self._approved_purchase(student, item, admin_user)
        student.refresh_from_db(); item.refresh_from_db()
        assert student.coins == 200
        assert item.stock == 2

        client = auth_client(admin_user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/refund/', {'reason': 'defective'})
        assert resp.status_code == 200

        student.refresh_from_db()
        item.refresh_from_db()
        pr.refresh_from_db()
        assert student.coins == 300
        assert item.stock == 3
        assert pr.status == PurchaseRequest.Status.REFUNDED
        assert pr.refunded_by == admin_user
        assert pr.refund_reason == 'defective'
        assert pr.refunded_at is not None

        earn_txn = KumushTransaction.objects.get(student=student, type=KumushTransaction.Type.EARN)
        assert earn_txn.amount == 100
        assert earn_txn.created_by == admin_user
        assert earn_txn.balance_before == 200
        assert earn_txn.balance_after == 300
        assert earn_txn.source_type == 'store_refund'
        assert earn_txn.source_id == str(pr.pk)
        assert earn_txn.purchase_id == pr.pk

        log = ActivityLog.objects.filter(model_name='PurchaseRequest', object_id=str(pr.pk),
                                          changes__kumush_restored=100).first()
        assert log is not None

    def test_developer_can_refund(self, developer_user, admin_user, student_a):
        item = StoreItem.objects.create(name='Kitob', price=100, stock=3)
        _, student = student_a
        pr = self._approved_purchase(student, item, admin_user)
        client = auth_client(developer_user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/refund/')
        assert resp.status_code == 200

    def test_student_cannot_refund(self, student_a, admin_user):
        item = StoreItem.objects.create(name='Kitob', price=100, stock=3)
        _, student = student_a
        pr = self._approved_purchase(student, item, admin_user)
        client = auth_client(student.user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/refund/')
        assert resp.status_code == 403

    def test_teacher_cannot_refund(self, teacher_user, admin_user, student_a):
        item = StoreItem.objects.create(name='Kitob', price=100, stock=3)
        _, student = student_a
        pr = self._approved_purchase(student, item, admin_user)
        client = auth_client(teacher_user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/refund/')
        assert resp.status_code == 403

    def test_finance_cannot_refund(self, finance_user, admin_user, student_a):
        item = StoreItem.objects.create(name='Kitob', price=100, stock=3)
        _, student = student_a
        pr = self._approved_purchase(student, item, admin_user)
        client = auth_client(finance_user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/refund/')
        assert resp.status_code == 403

    def test_cannot_refund_pending_request(self, admin_user, student_a):
        item = StoreItem.objects.create(name='Kitob', price=100, stock=3)
        _, student = student_a
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=100)
        client = auth_client(admin_user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/refund/')
        assert resp.status_code == 400

    def test_cannot_refund_rejected_request(self, admin_user, student_a):
        item = StoreItem.objects.create(name='Kitob', price=100, stock=3)
        _, student = student_a
        pr = PurchaseRequest.objects.create(
            student=student, item=item, price_at_request=100,
            status=PurchaseRequest.Status.REJECTED,
        )
        client = auth_client(admin_user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/refund/')
        assert resp.status_code == 400

    def test_cannot_refund_twice(self, admin_user, student_a):
        item = StoreItem.objects.create(name='Kitob', price=100, stock=3)
        _, student = student_a
        pr = self._approved_purchase(student, item, admin_user)
        client = auth_client(admin_user)

        first = client.post(f'/api/v1/store/requests/{pr.id}/refund/')
        second = client.post(f'/api/v1/store/requests/{pr.id}/refund/')

        assert first.status_code == 200
        assert second.status_code == 400
        student.refresh_from_db()
        item.refresh_from_db()
        assert student.coins == 300  # only restored once
        assert item.stock == 3       # only restored once
        assert KumushTransaction.objects.filter(
            student=student, type=KumushTransaction.Type.EARN, source_type='store_refund',
        ).count() == 1
