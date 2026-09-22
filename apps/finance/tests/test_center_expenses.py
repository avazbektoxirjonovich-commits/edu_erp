"""Markaz xarajatlari: ijara, kommunal, kanselyariya, davomli/davomsiz, olib kelingan narsalar."""
from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.finance.models import Asset, Expense

URL = '/api/v1/finance/expenses/'


@pytest.fixture
def client(db):
    user = User.objects.create_user(phone='+998906660001', password='pass1234',
                                    full_name='Moliyachi', role=User.Role.FINANCE)
    c = APIClient()
    c.force_authenticate(user=user)
    c.user = user
    return c


def add(client, **data):
    payload = {'name': 'X', 'category': 'other', 'amount': 100000, 'expense_date': '2026-09-05', **data}
    return client.post(URL, payload, format='json')


@pytest.mark.django_db
@pytest.mark.parametrize('category,label', [
    ('rent', "Ijara to'lovi"), ('utilities', "Kommunal to'lov"),
    ('stationery', 'Kanselyariya'), ('purchase', 'Olib kelingan narsalar'),
])
def test_new_categories(client, category, label):
    extra = {'quantity': 2} if category == 'purchase' else {}
    resp = add(client, category=category, **extra)
    assert resp.status_code == 201, resp.data
    assert resp.data['category_display'] == label


@pytest.mark.django_db
def test_salary_category_rejected_to_avoid_double_count(client):
    resp = add(client, category='salary')
    assert resp.status_code == 400
    assert not Expense.objects.exists()


@pytest.mark.django_db
def test_purchase_requires_quantity(client):
    assert add(client, category='purchase').status_code == 400


@pytest.mark.django_db
def test_purchase_added_to_assets(client):
    resp = add(client, name='Stul', category='purchase', amount=600000, quantity=4, add_to_assets=True)
    assert resp.status_code == 201
    asset = Asset.objects.get()
    assert (asset.name, asset.quantity, asset.purchase_price, asset.purchase_date) == (
        'Stul', 4, 150000, date(2026, 9, 5))
    assert Expense.objects.get().asset == asset


@pytest.mark.django_db
def test_purchase_without_asset_flag_creates_no_asset(client):
    add(client, name='Qog\'oz', category='purchase', quantity=10)
    assert not Asset.objects.exists()


@pytest.mark.django_db
def test_only_purchase_can_go_to_assets(client):
    assert add(client, category='rent', add_to_assets=True).status_code == 400


@pytest.mark.django_db
def test_recurring_carried_to_next_month_once(client):
    add(client, name='Ijara', category='rent', amount=5000000, expense_date='2026-09-01', is_recurring=True)
    add(client, name='Kommunal', category='utilities', amount=700000, expense_date='2026-09-30',
        is_recurring=True)
    add(client, name='Kanselyariya', category='stationery', amount=90000, expense_date='2026-09-10')  # davomsiz

    first = client.post(f'{URL}carry-recurring/', {'month': 10, 'year': 2026}, format='json')
    assert first.status_code == 200
    assert first.data['created'] == 2
    october = Expense.objects.filter(expense_date__month=10).order_by('name')
    assert [(e.name, e.amount, e.expense_date.day, e.is_recurring) for e in october] == [
        ('Ijara', 5000000, 1, True), ('Kommunal', 700000, 30, True)]

    again = client.post(f'{URL}carry-recurring/', {'month': 10, 'year': 2026}, format='json')
    assert again.data['created'] == 0

    # Keyingi oyga ham zanjir bo'lib o'tadi (asl yozuvga bog'langan holda)
    nov = client.post(f'{URL}carry-recurring/', {'month': 11, 'year': 2026}, format='json')
    assert nov.data['created'] == 2
    ijara = Expense.objects.filter(name='Ijara').order_by('expense_date')
    assert len({e.recurring_source_id or e.pk for e in ijara}) == 1


@pytest.mark.django_db
def test_stopping_recurring_stops_carry(client):
    resp = add(client, name='Ijara', category='rent', expense_date='2026-09-01', is_recurring=True)
    client.patch(f"{URL}{resp.data['id']}/", {'is_recurring': False}, format='json')
    assert client.post(f'{URL}carry-recurring/', {'month': 10, 'year': 2026},
                       format='json').data['created'] == 0


@pytest.mark.django_db
def test_carry_across_year_boundary(client):
    add(client, name='Ijara', category='rent', expense_date='2026-12-31', is_recurring=True)
    resp = client.post(f'{URL}carry-recurring/', {'month': 1, 'year': 2027}, format='json')
    assert resp.data['created'] == 1
    assert Expense.objects.filter(expense_date=date(2027, 1, 31)).exists()


@pytest.mark.django_db
def test_filter_recurring(client):
    add(client, name='A', is_recurring=True)
    add(client, name='B')
    resp = client.get(f'{URL}?is_recurring=true')
    rows = resp.data.get('results', resp.data)
    assert [r['name'] for r in rows] == ['A']
