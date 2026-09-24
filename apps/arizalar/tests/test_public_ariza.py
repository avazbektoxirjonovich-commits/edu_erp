"""Saytdan ariza qoldirish (autentifikatsiyasiz public API)."""
import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.arizalar.models import Application

URL = '/api/public/ariza/'


def payload(**extra):
    data = {
        'ism_familya': "Aliyev Vali Anvar o'g'li",
        'telefon': '+998901112233',
        'yashash_manzili': "Qorako'l tumani, Navoiy ko'chasi 12",
        'ota_ona_ismi': 'Aliyev Anvar',
        'yosh': 12,
        'yonalish': 'Matematika',
    }
    data.update(extra)
    return data


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def anon():
    return APIClient()


@pytest.mark.django_db
class TestArizaCreate:

    def test_application_saved(self, anon):
        resp = anon.post(URL, payload(), format='json')
        assert resp.status_code == 201
        assert 'xabar' in resp.data
        a = Application.objects.get()
        assert (a.full_name, a.phone, a.age, a.direction) == (
            "Aliyev Vali Anvar o'g'li", '+998901112233', 12, 'Matematika')
        assert a.parent_name == 'Aliyev Anvar'
        assert a.status == Application.Status.NEW

    @pytest.mark.parametrize('given', ['901112233', '998901112233', '+998 (90) 111-22-33'])
    def test_phone_normalized(self, anon, given):
        assert anon.post(URL, payload(telefon=given), format='json').status_code == 201
        assert Application.objects.get().phone == '+998901112233'

    @pytest.mark.parametrize('bad', ['12345', '+9989011122', 'telefon yoq'])
    def test_bad_phone_rejected(self, anon, bad):
        resp = anon.post(URL, payload(telefon=bad), format='json')
        assert resp.status_code == 400
        assert 'telefon' in resp.data
        assert not Application.objects.exists()

    @pytest.mark.parametrize('field', ['ism_familya', 'telefon', 'yashash_manzili',
                                       'ota_ona_ismi', 'yosh', 'yonalish'])
    def test_every_field_required(self, anon, field):
        data = payload()
        data.pop(field)
        resp = anon.post(URL, data, format='json')
        assert resp.status_code == 400
        assert field in resp.data
        assert not Application.objects.exists()

    @pytest.mark.parametrize('age', [2, 100, -5, 'yigirma'])
    def test_bad_age_rejected(self, anon, age):
        assert anon.post(URL, payload(yosh=age), format='json').status_code == 400
        assert not Application.objects.exists()

    def test_name_with_digits_rejected(self, anon):
        resp = anon.post(URL, payload(ism_familya='Ali 123'), format='json')
        assert resp.status_code == 400
        assert 'ism_familya' in resp.data

    def test_short_address_rejected(self, anon):
        assert anon.post(URL, payload(yashash_manzili='a'), format='json').status_code == 400

    def test_honeypot_silently_ignored(self, anon):
        """Bot ko'rinmas maydonni to'ldiradi — javob muvaffaqiyatli, lekin yozuv yo'q."""
        resp = anon.post(URL, payload(website='http://spam.example'), format='json')
        assert resp.status_code == 201
        assert not Application.objects.exists()

    def test_duplicate_open_application_rejected(self, anon):
        assert anon.post(URL, payload(), format='json').status_code == 201
        resp = anon.post(URL, payload(yonalish='Ingliz tili'), format='json')
        assert resp.status_code == 400
        assert 'telefon' in resp.data
        assert Application.objects.count() == 1

    @pytest.mark.parametrize('closed', [Application.Status.ENROLLED, Application.Status.REJECTED])
    def test_new_application_allowed_after_closed_one(self, anon, closed):
        anon.post(URL, payload(), format='json')
        Application.objects.update(status=closed)
        assert anon.post(URL, payload(), format='json').status_code == 201
        assert Application.objects.count() == 2

    def test_ip_hourly_limit(self, anon, settings):
        """Bir IP'dan soatiga cheklangan son — baza bo'yicha hisoblanadi."""
        from apps.arizalar import public
        limit = public.MAX_APPLICATIONS_PER_IP_HOUR
        for i in range(limit):
            Application.objects.create(
                full_name='X Y', phone=f'+99890111{i:04d}', address='manzil',
                parent_name='Ota Ona', age=10, direction='Matematika', ip_address='10.1.2.3')
        resp = anon.post(URL, payload(), format='json', HTTP_X_FORWARDED_FOR='10.1.2.3')
        assert resp.status_code == 429
        assert Application.objects.count() == limit

    def test_no_auth_required(self, anon):
        """Public endpoint — token so'ralmaydi."""
        assert anon.post(URL, payload(), format='json').status_code == 201


@pytest.mark.parametrize('module', ['config.settings.development', 'config.settings.windows',
                                    'config.settings.test'])
def test_throttle_scope_in_every_settings_module(module):
    """Scope yo'q bo'lsa endpoint 500 beradi — har bir sozlamalar faylida bo'lishi shart."""
    import importlib
    rates = importlib.import_module(module).REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
    assert 'ariza_register' in rates
