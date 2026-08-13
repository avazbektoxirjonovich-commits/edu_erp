import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.store.models import KumushTransaction, PurchaseRequest, StoreItem
from apps.students.models import Student


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        phone='+998900000090', password='pass1234',
        full_name='Admin User', role=User.Role.ADMIN,
    )


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        phone='+998900000091', password='pass1234',
        full_name='Teacher User', role=User.Role.TEACHER,
    )


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        phone='+998900000092', password='pass1234',
        full_name='Finance User', role=User.Role.FINANCE,
    )


def _make_student(phone, coins=0):
    user = User.objects.create_user(phone=phone, password='pass1234',
                                    full_name=f'Student {phone}', role=User.Role.STUDENT)
    student = Student.objects.create(user=user, phone=phone, coins=coins)
    return user, student


@pytest.fixture
def student_a(db):
    return _make_student('+998900000093', coins=300)


@pytest.fixture
def student_b(db):
    return _make_student('+998900000094', coins=50)


@pytest.mark.django_db
class TestStoreItemPermissions:

    def test_admin_can_create_item(self, admin_user):
        client = auth_client(admin_user)
        resp = client.post('/api/v1/store/items/', {
            'name': 'Quloqchin', 'price': 250, 'stock': 3, 'description': 'Simsiz quloqchin',
        }, format='json')
        assert resp.status_code == 201
        assert resp.data['is_available'] is True
        assert resp.data['sold_count'] == 0

    def test_student_cannot_create_item(self, student_a):
        _, student = student_a
        client = auth_client(student.user)
        resp = client.post('/api/v1/store/items/', {'name': 'Hack', 'price': 1, 'stock': 1})
        assert resp.status_code == 403

    def test_teacher_cannot_create_item(self, teacher_user):
        client = auth_client(teacher_user)
        resp = client.post('/api/v1/store/items/', {'name': 'Hack', 'price': 1, 'stock': 1})
        assert resp.status_code == 403

    def test_teacher_can_view_items(self, teacher_user):
        StoreItem.objects.create(name='Kitob', price=100, stock=5)
        client = auth_client(teacher_user)
        resp = client.get('/api/v1/store/items/')
        assert resp.status_code == 200

    def test_finance_cannot_view_store(self, finance_user):
        client = auth_client(finance_user)
        resp = client.get('/api/v1/store/items/')
        assert resp.status_code == 403

    def test_inactive_item_hidden_from_student(self, student_a, admin_user):
        StoreItem.objects.create(name='Faol', price=100, stock=5, is_active=True)
        StoreItem.objects.create(name='Nofaol', price=100, stock=5, is_active=False)
        _, student = student_a
        client = auth_client(student.user)
        resp = client.get('/api/v1/store/items/')
        names = [i['name'] for i in resp.data.get('results', resp.data)]
        assert 'Faol' in names
        assert 'Nofaol' not in names

    def test_inactive_item_visible_to_admin(self, admin_user):
        StoreItem.objects.create(name='Nofaol', price=100, stock=5, is_active=False)
        client = auth_client(admin_user)
        resp = client.get('/api/v1/store/items/')
        names = [i['name'] for i in resp.data.get('results', resp.data)]
        assert 'Nofaol' in names

    def test_negative_price_rejected(self, admin_user):
        client = auth_client(admin_user)
        resp = client.post('/api/v1/store/items/', {'name': 'X', 'price': -5, 'stock': 1})
        assert resp.status_code == 400

    def test_zero_price_rejected(self, admin_user):
        """StoreItem.price has MinValueValidator(1) — 0 must be rejected
        just like a negative price, not treated as a free item."""
        client = auth_client(admin_user)
        resp = client.post('/api/v1/store/items/', {'name': 'X', 'price': 0, 'stock': 1})
        assert resp.status_code == 400

    def test_item_delete_not_allowed(self, admin_user):
        item = StoreItem.objects.create(name='Y', price=100, stock=1)
        client = auth_client(admin_user)
        resp = client.delete(f'/api/v1/store/items/{item.id}/')
        assert resp.status_code == 405
        assert StoreItem.objects.filter(id=item.id).exists()

    def test_deactivate_item(self, admin_user):
        item = StoreItem.objects.create(name='Z', price=100, stock=1, is_active=True)
        client = auth_client(admin_user)
        resp = client.patch(f'/api/v1/store/items/{item.id}/', {'is_active': False})
        assert resp.status_code == 200
        item.refresh_from_db()
        assert item.is_active is False


@pytest.mark.django_db
class TestPurchaseRequestFlow:

    def test_student_can_request_with_enough_coins(self, student_a, admin_user):
        item = StoreItem.objects.create(name='Quloqchin', price=250, stock=3)
        _, student = student_a
        client = auth_client(student.user)
        resp = client.post('/api/v1/store/requests/', {'item': str(item.id)})
        assert resp.status_code == 201
        assert resp.data['status'] == 'pending'
        assert resp.data['price_at_request'] == 250
        # Nothing deducted yet
        student.refresh_from_db()
        assert student.coins == 300
        item.refresh_from_db()
        assert item.stock == 3

    def test_insufficient_coins_rejected(self, student_b):
        item = StoreItem.objects.create(name='Quloqchin', price=250, stock=3)
        _, student = student_b  # only 50 coins
        client = auth_client(student.user)
        resp = client.post('/api/v1/store/requests/', {'item': str(item.id)})
        assert resp.status_code == 400

    def test_out_of_stock_rejected(self, student_a):
        item = StoreItem.objects.create(name='Tugagan', price=10, stock=0)
        _, student = student_a
        client = auth_client(student.user)
        resp = client.post('/api/v1/store/requests/', {'item': str(item.id)})
        assert resp.status_code == 400

    def test_student_sees_only_own_requests(self, student_a, student_b):
        item = StoreItem.objects.create(name='Kitob', price=10, stock=5)
        _, sa = student_a
        _, sb = student_b
        PurchaseRequest.objects.create(student=sa, item=item, price_at_request=10)
        PurchaseRequest.objects.create(student=sb, item=item, price_at_request=10)
        client = auth_client(sa.user)
        resp = client.get('/api/v1/store/requests/')
        results = resp.data.get('results', resp.data)
        assert len(results) == 1
        assert results[0]['student'] == sa.id

    def test_teacher_cannot_access_requests(self, teacher_user):
        client = auth_client(teacher_user)
        resp = client.get('/api/v1/store/requests/')
        assert resp.status_code == 403

    def test_student_cannot_approve_own_request(self, student_a):
        item = StoreItem.objects.create(name='Kitob', price=10, stock=5)
        _, student = student_a
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=10)
        client = auth_client(student.user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/approve/')
        assert resp.status_code == 403

    def test_student_cannot_patch_status_directly(self, student_a):
        item = StoreItem.objects.create(name='Kitob', price=10, stock=5)
        _, student = student_a
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=10)
        client = auth_client(student.user)
        resp = client.patch(f'/api/v1/store/requests/{pr.id}/', {'status': 'approved'})
        assert resp.status_code == 405


@pytest.mark.django_db
class TestApproval:

    def test_approve_deducts_coins_and_stock_and_logs_transaction(self, student_a, admin_user):
        item = StoreItem.objects.create(name='Quloqchin', price=250, stock=3)
        _, student = student_a
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=250)

        client = auth_client(admin_user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/approve/')
        assert resp.status_code == 200
        assert resp.data['status'] == 'approved'

        student.refresh_from_db()
        item.refresh_from_db()
        pr.refresh_from_db()
        assert student.coins == 50           # 300 - 250
        assert item.stock == 2                # 3 - 1
        assert pr.status == 'approved'
        assert pr.decided_by == admin_user

        txn = KumushTransaction.objects.get(purchase=pr)
        assert txn.amount == -250
        assert txn.student == student

    def test_approve_ledger_has_full_forensic_metadata(self, student_a, admin_user):
        """Store approval's SPEND transaction must carry the same forensic
        metadata every other KUMUSH mutation in the system does — routed
        through apply_kumush_and_xp() rather than spend_coins() + a
        hand-built KumushTransaction()."""
        item = StoreItem.objects.create(name='Quloqchin', price=250, stock=3)
        _, student = student_a
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=250)

        client = auth_client(admin_user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/approve/')
        assert resp.status_code == 200

        # Exactly one SPEND transaction — never duplicated.
        assert KumushTransaction.objects.filter(purchase=pr).count() == 1
        txn = KumushTransaction.objects.get(purchase=pr)
        assert txn.type == KumushTransaction.Type.SPEND
        assert txn.amount == -250
        assert txn.created_by == admin_user
        assert txn.balance_before == 300
        assert txn.balance_after == 50
        assert txn.source_type == 'store_purchase'
        assert txn.source_id == str(pr.pk)

        student.refresh_from_db()
        assert student.coins == txn.balance_after  # stored balance matches ledger's balance_after

    def test_double_approve_blocked(self, student_a, admin_user):
        item = StoreItem.objects.create(name='Quloqchin', price=250, stock=3)
        _, student = student_a
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=250)
        client = auth_client(admin_user)

        r1 = client.post(f'/api/v1/store/requests/{pr.id}/approve/')
        r2 = client.post(f'/api/v1/store/requests/{pr.id}/approve/')
        assert r1.status_code == 200
        assert r2.status_code == 400

        student.refresh_from_db()
        item.refresh_from_db()
        assert student.coins == 50   # only deducted once
        assert item.stock == 2       # only decremented once

    def test_approve_fails_if_balance_dropped_since_request(self, student_b, admin_user):
        # Student had enough at request time but balance was spent elsewhere before approval.
        item = StoreItem.objects.create(name='Quloqchin', price=50, stock=3)
        _, student = student_b  # exactly 50
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=50)
        student.coins = 0
        student.save(update_fields=['coins'])

        client = auth_client(admin_user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/approve/')
        assert resp.status_code == 400
        pr.refresh_from_db()
        assert pr.status == 'pending'

    def test_reject_does_not_touch_coins_or_stock(self, student_a, admin_user):
        item = StoreItem.objects.create(name='Quloqchin', price=250, stock=3)
        _, student = student_a
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=250)

        client = auth_client(admin_user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/reject/', {'reason': "Yetarli emas"})
        assert resp.status_code == 200
        assert resp.data['status'] == 'rejected'
        assert resp.data['rejection_reason'] == "Yetarli emas"

        student.refresh_from_db()
        item.refresh_from_db()
        assert student.coins == 300
        assert item.stock == 3
        assert KumushTransaction.objects.filter(purchase=pr).count() == 0

    def test_price_change_after_request_does_not_affect_snapshot(self, student_a, admin_user):
        item = StoreItem.objects.create(name='Quloqchin', price=100, stock=3)
        _, student = student_a
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=100)
        item.price = 999
        item.save(update_fields=['price'])

        client = auth_client(admin_user)
        resp = client.post(f'/api/v1/store/requests/{pr.id}/approve/')
        assert resp.status_code == 200
        student.refresh_from_db()
        assert student.coins == 200   # 300 - 100 (snapshot price), not 999


@pytest.mark.django_db
class TestConcurrency:
    """
    Real thread-level concurrency can't be exercised reliably here: SQLite
    (the pytest DB) has no row-level locking, so two genuinely concurrent
    writers just collide on its single database-wide write lock regardless
    of application logic — that's a test-harness limitation, not something
    this suite can observe. Production runs on PostgreSQL, where
    select_for_update() in approve() actually blocks a second transaction
    until the first commits.

    What we *can* verify deterministically, without threads, is the
    single-use-atomic-gate pattern this codebase relies on for safety
    against double-spend: an atomic conditional UPDATE that only one
    caller can ever win, however many callers race to call it. approve()
    itself now goes through apply_kumush_and_xp() (select_for_update() +
    a balance check inside the lock, rather than spend_coins()'s
    conditional UPDATE) — its own concurrency guard is covered by
    TestApproval.test_double_approve_blocked. spend_coins() remains a
    tested, available primitive with the same safety guarantee, exercised
    directly here.
    """

    def test_spend_coins_is_a_single_use_atomic_gate(self, db):
        user = User.objects.create_user(
            phone='+998900000096', password='pass1234',
            full_name='Student Concurrency', role=User.Role.STUDENT,
        )
        student = Student.objects.create(user=user, phone=user.phone, coins=250)

        first  = student.spend_coins(250, reason='Quloqchin sotib olindi')
        second = student.spend_coins(250, reason='Quloqchin sotib olindi (double-spend urinishi)')

        assert first is True
        assert second is False          # balance already exhausted by the first call
        student.refresh_from_db()
        assert student.coins == 0        # deducted exactly once, never negative
