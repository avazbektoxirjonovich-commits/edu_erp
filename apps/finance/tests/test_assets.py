import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.finance.models import Asset


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        phone='+998900000080', password='pass1234',
        full_name='Finance User', role=User.Role.FINANCE,
    )


@pytest.fixture
def teacher_role_user(db):
    return User.objects.create_user(
        phone='+998900000081', password='pass1234',
        full_name='Teacher User', role=User.Role.TEACHER,
    )


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestAssetCRUD:

    def test_finance_can_create_asset_with_computed_total(self, finance_user):
        client = auth_client(finance_user)
        resp = client.post('/api/v1/finance/assets/', {
            'name': 'Kompyuter', 'quantity': 10, 'purchase_price': 4000000,
            'category': 'texnika', 'condition': 'new',
        })
        assert resp.status_code == 201
        assert resp.data['total_value'] == 40000000
        assert resp.data['condition_display'] == 'Yangi'

    def test_teacher_cannot_access_assets(self, teacher_role_user):
        client = auth_client(teacher_role_user)
        resp = client.get('/api/v1/finance/assets/')
        assert resp.status_code == 403

    def test_filter_by_condition(self, finance_user):
        Asset.objects.create(name='Yangi stol', quantity=5, purchase_price=200000, condition='new')
        Asset.objects.create(name='Eski stul', quantity=3, purchase_price=50000, condition='damaged')
        client = auth_client(finance_user)
        resp = client.get('/api/v1/finance/assets/?condition=damaged')
        results = resp.data.get('results', resp.data)
        assert len(results) == 1
        assert results[0]['name'] == 'Eski stul'

    def test_search_by_name(self, finance_user):
        Asset.objects.create(name='Proyektor', quantity=2, purchase_price=1500000)
        Asset.objects.create(name='Doska', quantity=4, purchase_price=300000)
        client = auth_client(finance_user)
        resp = client.get('/api/v1/finance/assets/?search=Proyektor')
        results = resp.data.get('results', resp.data)
        assert len(results) == 1

    def test_update_quantity_recomputes_total(self, finance_user):
        asset = Asset.objects.create(name='Kreslo', quantity=5, purchase_price=100000)
        client = auth_client(finance_user)
        resp = client.patch(f'/api/v1/finance/assets/{asset.id}/', {'quantity': 8})
        assert resp.status_code == 200
        assert resp.data['total_value'] == 800000

    def test_delete_asset(self, finance_user):
        asset = Asset.objects.create(name='Old chair', quantity=1, purchase_price=50000)
        client = auth_client(finance_user)
        resp = client.delete(f'/api/v1/finance/assets/{asset.id}/')
        assert resp.status_code == 204
        assert not Asset.objects.filter(id=asset.id).exists()


@pytest.mark.django_db
class TestAssetSummary:

    def test_total_value_and_by_condition(self, finance_user):
        Asset.objects.create(name='A', quantity=10, purchase_price=4000000, condition='new')
        Asset.objects.create(name='B', quantity=2, purchase_price=500000, condition='damaged')
        client = auth_client(finance_user)
        resp = client.get('/api/v1/finance/assets/summary/')
        assert resp.status_code == 200
        assert resp.data['total_assets'] == 2
        assert resp.data['total_value'] == 41000000.0
        assert resp.data['value_by_condition']['new'] == 40000000.0
        assert resp.data['value_by_condition']['damaged'] == 1000000.0

    def test_teacher_cannot_view_asset_summary(self, teacher_role_user):
        client = auth_client(teacher_role_user)
        resp = client.get('/api/v1/finance/assets/summary/')
        assert resp.status_code == 403
