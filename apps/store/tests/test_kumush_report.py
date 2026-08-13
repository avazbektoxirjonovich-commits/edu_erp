"""
Admin/Developer KUMUSH financial reporting — totals issued/spent, breakdown
by earning source, top earners, best-selling products, purchase counts by
status. Distinct from the XP leaderboard: purely KUMUSH/financial figures.
"""
import pytest

from apps.store.models import KumushTransaction, PurchaseRequest, StoreItem
from apps.store.tests.conftest import auth_client


@pytest.mark.django_db
class TestKumushReportPermissions:

    def test_admin_can_view(self, admin_user):
        client = auth_client(admin_user)
        resp = client.get('/api/v1/store/kumush-report/')
        assert resp.status_code == 200

    def test_developer_can_view(self, developer_user):
        client = auth_client(developer_user)
        resp = client.get('/api/v1/store/kumush-report/')
        assert resp.status_code == 200

    def test_student_cannot_view(self, student_a):
        client = auth_client(student_a[0])
        resp = client.get('/api/v1/store/kumush-report/')
        assert resp.status_code == 403

    def test_teacher_cannot_view(self, teacher_user):
        client = auth_client(teacher_user)
        resp = client.get('/api/v1/store/kumush-report/')
        assert resp.status_code == 403

    def test_finance_cannot_view(self, finance_user):
        client = auth_client(finance_user)
        resp = client.get('/api/v1/store/kumush-report/')
        assert resp.status_code == 403


@pytest.mark.django_db
class TestKumushReportFigures:

    def test_totals_and_source_breakdown(self, admin_user, student_a, student_b):
        _, sa = student_a
        _, sb = student_b

        sa.apply_kumush_and_xp(coins_delta=10, reason='attendance', source_type='attendance', source_id='1')
        sa.apply_kumush_and_xp(coins_delta=80, reason='homework', source_type='homework', source_id='2')
        sb.apply_kumush_and_xp(coins_delta=20, reason='zukko', source_type='zukko_bugfind', source_id='3')
        sa.apply_kumush_and_xp(coins_delta=50, reason='manual bonus', source_type='manual')
        sa.apply_kumush_and_xp(coins_delta=-30, reason='spent something', source_type='')

        client = auth_client(admin_user)
        resp = client.get('/api/v1/store/kumush-report/')
        assert resp.status_code == 200
        data = resp.data

        assert data['total_issued'] == 10 + 80 + 20 + 50
        assert data['total_spent'] == 30
        assert data['by_source']['attendance'] == 10
        assert data['by_source']['homework'] == 80
        assert data['by_source']['zukko'] == 20
        assert data['by_source']['manual'] == 50

    def test_refund_counted_in_refunded_bucket(self, admin_user, student_a):
        _, student = student_a
        item = StoreItem.objects.create(name='Kitob', price=100, stock=3)
        pr = PurchaseRequest.objects.create(student=student, item=item, price_at_request=100)
        client = auth_client(admin_user)
        approve = client.post(f'/api/v1/store/requests/{pr.id}/approve/')
        assert approve.status_code == 200
        refund = client.post(f'/api/v1/store/requests/{pr.id}/refund/')
        assert refund.status_code == 200

        resp = client.get('/api/v1/store/kumush-report/')
        assert resp.data['by_source']['refunded'] == 100

    def test_top_earners_ordered_desc(self, admin_user, student_a, student_b):
        _, sa = student_a
        _, sb = student_b
        sa.apply_kumush_and_xp(coins_delta=200, reason='x', source_type='manual')
        sb.apply_kumush_and_xp(coins_delta=500, reason='y', source_type='manual')

        client = auth_client(admin_user)
        resp = client.get('/api/v1/store/kumush-report/')
        earners = resp.data['top_earners']
        assert earners[0]['student_id'] == sb.id
        assert earners[0]['total_earned'] == 500
        assert earners[1]['student_id'] == sa.id
        assert earners[1]['total_earned'] == 200

    def test_best_selling_products_only_counts_approved(self, admin_user, student_a):
        _, student = student_a
        item = StoreItem.objects.create(name='Popular', price=10, stock=10)
        for _ in range(3):
            PurchaseRequest.objects.create(
                student=student, item=item, price_at_request=10,
                status=PurchaseRequest.Status.APPROVED,
            )
        PurchaseRequest.objects.create(
            student=student, item=item, price_at_request=10,
            status=PurchaseRequest.Status.REJECTED,
        )

        client = auth_client(admin_user)
        resp = client.get('/api/v1/store/kumush-report/')
        best = resp.data['best_selling_products']
        assert best[0]['item_id'] == item.id
        assert best[0]['purchase_count'] == 3

    def test_purchase_counts_by_status(self, admin_user, student_a):
        _, student = student_a
        item = StoreItem.objects.create(name='X', price=10, stock=10)
        PurchaseRequest.objects.create(student=student, item=item, price_at_request=10,
                                        status=PurchaseRequest.Status.PENDING)
        PurchaseRequest.objects.create(student=student, item=item, price_at_request=10,
                                        status=PurchaseRequest.Status.CANCELLED)

        client = auth_client(admin_user)
        resp = client.get('/api/v1/store/kumush-report/')
        counts = resp.data['purchase_counts_by_status']
        assert counts['pending'] == 1
        assert counts['cancelled'] == 1
        assert counts['approved'] == 0
        assert counts['rejected'] == 0
        assert counts['refunded'] == 0
