"""
payments.html va salary.html sahifalari moliyachi uchun ham ishlashi kerak
(ular API darajasida finance rolига ochilgan), lekin bu sahifalar yuklanishda
/dashboard/, /groups/, /teachers/ kabi qo'shimcha endpointlarni ham chaqiradi.
Bu test o'sha bog'liqliklarni ham finance rolига ochiq ekanini tekshiradi —
Playwright orqali brauzerda 403 xatolari topilgach qo'shilgan.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        phone='+998900000120', password='pass1234',
        full_name='Finance User', role=User.Role.FINANCE,
    )


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestFinanceCanUseSharedPages:

    def test_finance_can_list_teachers(self, finance_user):
        client = auth_client(finance_user)
        resp = client.get('/api/v1/teachers/')
        assert resp.status_code == 200

    def test_finance_can_list_groups(self, finance_user):
        client = auth_client(finance_user)
        resp = client.get('/api/v1/groups/')
        assert resp.status_code == 200

    def test_finance_can_view_admin_dashboard(self, finance_user):
        client = auth_client(finance_user)
        resp = client.get('/api/v1/dashboard/')
        assert resp.status_code == 200
