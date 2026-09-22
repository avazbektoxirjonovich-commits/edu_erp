"""2-bosqich: public API (autentifikatsiyasiz) — throttle, honeypot, CORS, natijalar."""
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.musobaqalar import public
from apps.musobaqalar.models import Competition, Participant, Result

BASE = '/api/public/musobaqa/'


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def anon():
    return APIClient()


def make_competition(**extra):
    data = dict(name='Oktyabr matematika', grade_from=1, grade_to=11,
                registration_deadline=timezone.now() + timedelta(days=7),
                status=Competition.Status.PUBLISHED, location="Qorako'l, markaz binosi")
    data.update(extra)
    return Competition.objects.create(**data)


def form(competition, **extra):
    data = {'musobaqa_id': str(competition.id), 'ism': 'Ali', 'familya': 'Valiyev',
            'telefon': '+998901234567', 'yashash_manzili': "Qorako'l, Navoiy ko'chasi 5", 'sinf': 5}
    data.update(extra)
    return data


def register(client, competition, ip='10.0.0.1', **extra):
    return client.post(f'{BASE}royxat/', form(competition, **extra), format='json', REMOTE_ADDR=ip)


# ── Joriy musobaqa ───────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestCurrent:

    def test_empty_state(self, anon):
        make_competition(status=Competition.Status.DRAFT)
        resp = anon.get(f'{BASE}joriy/')
        assert resp.status_code == 200
        assert resp.data == {'musobaqa': None}

    def test_published_competition(self, anon):
        c = make_competition()
        data = anon.get(f'{BASE}joriy/').data['musobaqa']
        assert data['id'] == str(c.id)
        assert (data['nomi'], data['boshlanish_sinf'], data['tugash_sinf']) == ('Oktyabr matematika', 1, 11)
        assert data['manzil'] == "Qorako'l, markaz binosi"
        assert data['royxat_ochiq'] is True
        # ISO 8601 zona bilan (Safari 'YYYY-MM-DD HH:MM:SS' ni o'qiy olmaydi)
        assert data['royxatdan_otish_muddati'].endswith('+05:00') and 'T' in data['royxatdan_otish_muddati']

    def test_deadline_passed_shows_closed(self, anon):
        make_competition(registration_deadline=timezone.now() - timedelta(minutes=1))
        assert anon.get(f'{BASE}joriy/').data['musobaqa']['royxat_ochiq'] is False

    def test_no_auth_needed_even_with_bad_token(self, anon):
        make_competition()
        anon.credentials(HTTP_AUTHORIZATION='Bearer buzilgan-token')
        assert anon.get(f'{BASE}joriy/').status_code == 200


# ── Ro'yxatdan o'tish ────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestRegister:

    def test_success(self, anon):
        c = make_competition()
        resp = register(anon, c, ip='10.1.1.1')
        assert resp.status_code == 201
        assert 'operatorimiz' in resp.data['xabar']
        p = Participant.objects.get()
        assert (p.first_name, p.last_name, p.phone, p.grade, p.status) == (
            'Ali', 'Valiyev', '+998901234567', 5, 'new')
        assert p.ip_address == '10.1.1.1'

    @pytest.mark.parametrize('raw', ['90 123 45 67', '998901234567', '+998 (90) 123-45-67', '901234567'])
    def test_phone_normalized(self, anon, raw):
        c = make_competition()
        assert register(anon, c, telefon=raw).status_code == 201
        assert Participant.objects.get().phone == '+998901234567'

    @pytest.mark.parametrize('bad', ['12345', '+7901234567', '+99890123456a', ''])
    def test_bad_phone(self, anon, bad):
        resp = register(anon, make_competition(), telefon=bad)
        assert resp.status_code == 400
        assert 'telefon' in resp.data

    def test_duplicate_phone(self, anon):
        c = make_competition()
        register(anon, c)
        resp = register(anon, c, ism='Boshqa', telefon='90 123 45 67')
        assert resp.status_code == 400
        assert 'allaqachon' in str(resp.data['telefon'][0])
        assert Participant.objects.count() == 1

    def test_deadline_passed(self, anon):
        c = make_competition(registration_deadline=timezone.now() - timedelta(seconds=1))
        resp = register(anon, c)
        assert resp.status_code == 400
        assert 'muddati tugagan' in str(resp.data['musobaqa_id'][0])

    @pytest.mark.parametrize('st', ['draft', 'registration_closed', 'finished'])
    def test_not_published(self, anon, st):
        resp = register(anon, make_competition(status=st))
        assert resp.status_code == 400
        assert not Participant.objects.exists()

    def test_unknown_competition(self, anon):
        c = make_competition()
        resp = anon.post(f'{BASE}royxat/', form(c, musobaqa_id='00000000-0000-0000-0000-000000000000'),
                         format='json')
        assert resp.status_code == 400

    def test_grade_outside_range(self, anon):
        resp = register(anon, make_competition(grade_from=5, grade_to=9), sinf=3)
        assert resp.status_code == 400
        assert '5-9' in str(resp.data['sinf'][0])

    @pytest.mark.parametrize('field,value', [
        ('ism', ''), ('familya', ' '), ('ism', 'http://spam.uz'), ('familya', 'A1'),
        ('yashash_manzili', ''), ('sinf', 12), ('sinf', 0),
    ])
    def test_field_validation(self, anon, field, value):
        resp = register(anon, make_competition(), **{field: value})
        assert resp.status_code == 400
        assert field in resp.data

    def test_uzbek_letters_allowed(self, anon):
        resp = register(anon, make_competition(), ism="G‘ayrat", familya="O'ktamov-Sobirov")
        assert resp.status_code == 201

    def test_honeypot_silently_rejected(self, anon):
        resp = register(anon, make_competition(), website='http://bot.example')
        assert resp.status_code == 201  # bot farqni sezmasin
        assert not Participant.objects.exists()

    def test_throttle_per_ip(self, anon):
        c = make_competition()
        codes = [register(anon, c, ip='10.9.9.9', telefon=f'+99890000000{i}').status_code for i in range(6)]
        assert codes == [201] * 5 + [429]
        # Boshqa IP cheklanmaydi
        assert register(anon, c, ip='10.9.9.8', telefon='+998900000009').status_code == 201

    def test_spoofed_forwarded_for_does_not_bypass_throttle(self, anon):
        c = make_competition()
        codes = []
        for i in range(6):
            codes.append(anon.post(f'{BASE}royxat/', form(c, telefon=f'+99891000000{i}'), format='json',
                                   HTTP_X_FORWARDED_FOR=f'1.2.3.{i}, 10.7.7.7').status_code)
        assert codes[-1] == 429
        assert set(Participant.objects.values_list('ip_address', flat=True)) == {'10.7.7.7'}

    def test_garbage_forwarded_for_does_not_crash(self, anon):
        resp = anon.post(f'{BASE}royxat/', form(make_competition()), format='json',
                         HTTP_X_FORWARDED_FOR='not-an-ip', REMOTE_ADDR='10.3.3.3')
        assert resp.status_code == 201
        assert Participant.objects.get().ip_address == '10.3.3.3'

    def test_hourly_limit_per_ip_survives_cache_reset(self, anon, monkeypatch):
        monkeypatch.setattr(public, 'MAX_REGISTRATIONS_PER_IP_HOUR', 2)
        c = make_competition()
        for i in range(2):
            assert register(anon, c, ip='10.4.4.4', telefon=f'+99893000000{i}').status_code == 201
        cache.clear()  # jarayon qayta ishga tushgandek — DRF throttle hisobi yo'qoladi
        resp = register(anon, c, ip='10.4.4.4', telefon='+998930000009')
        assert resp.status_code == 429


# ── CORS ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestCors:

    @pytest.fixture(autouse=True)
    def cors_settings(self, settings):
        settings.CORS_ALLOW_ALL_ORIGINS = False
        settings.CORS_ALLOWED_ORIGINS = []
        settings.PUBLIC_SITE_ORIGIN = 'https://musobaqa.example.uz'
        return settings

    def test_public_site_allowed_on_public_api(self, anon):
        resp = anon.get(f'{BASE}joriy/', HTTP_ORIGIN='https://musobaqa.example.uz')
        assert resp['Access-Control-Allow-Origin'] == 'https://musobaqa.example.uz'

    def test_preflight_for_registration(self, anon):
        resp = anon.options(f'{BASE}royxat/', HTTP_ORIGIN='https://musobaqa.example.uz',
                            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
                            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='content-type')
        assert resp['Access-Control-Allow-Origin'] == 'https://musobaqa.example.uz'

    def test_other_origin_refused(self, anon):
        resp = anon.get(f'{BASE}joriy/', HTTP_ORIGIN='https://yomon.example')
        assert 'Access-Control-Allow-Origin' not in resp

    def test_public_site_not_allowed_on_erp_api(self, anon):
        resp = anon.get('/api/v1/musobaqalar/competitions/', HTTP_ORIGIN='https://musobaqa.example.uz')
        assert 'Access-Control-Allow-Origin' not in resp

    def test_nothing_allowed_when_origin_not_configured(self, anon, cors_settings):
        cors_settings.PUBLIC_SITE_ORIGIN = ''
        resp = anon.get(f'{BASE}joriy/', HTTP_ORIGIN='https://musobaqa.example.uz')
        assert 'Access-Control-Allow-Origin' not in resp


# ── Natijalar ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestResults:

    def _finished(self, show_full_names=False):
        c = make_competition(status=Competition.Status.FINISHED, show_full_names=show_full_names,
                             competition_date=timezone.now())
        for grade in (5, 6):
            for i in range(12):
                p = Participant.objects.create(competition=c, first_name=f'Ism{i}', last_name=f'Familya{i}',
                                               phone=f'+9989{grade}00000{i:02d}', address='x', grade=grade)
                Result.objects.create(participant=p, score=100 - i, place=i + 1 if i < 3 else None)
        return c

    def test_top10_per_grade_masked(self, anon):
        c = self._finished()
        resp = anon.get(f'{BASE}natijalar/{c.id}/')
        assert resp.status_code == 200
        grades = resp.data['sinflar']
        assert [g['sinf'] for g in grades] == [5, 6]
        top = grades[0]['natijalar']
        assert len(top) == 10
        assert [r['orin'] for r in top[:4]] == [1, 2, 3, None]
        assert top[0] == {'ism': 'Ism0', 'familya': 'F.', 'ball': 100, 'orin': 1}
        # Telefon, manzil hech qachon chiqmaydi
        assert 'telefon' not in str(resp.data) and '+998' not in str(resp.data)

    def test_full_names_when_enabled(self, anon):
        c = self._finished(show_full_names=True)
        top = anon.get(f'{BASE}natijalar/{c.id}/').data['sinflar'][0]['natijalar']
        assert top[0]['familya'] == 'Familya0'

    @pytest.mark.parametrize('st', ['draft', 'published', 'registration_closed'])
    def test_only_finished(self, anon, st):
        c = make_competition(status=st)
        resp = anon.get(f'{BASE}natijalar/{c.id}/')
        assert resp.status_code == 404
        assert "e'lon qilinmagan" in resp.data['detail']

    def test_latest(self, anon):
        assert anon.get(f'{BASE}natijalar/oxirgi/').data == {'musobaqa': None, 'sinflar': []}
        c = self._finished()
        assert anon.get(f'{BASE}natijalar/oxirgi/').data['musobaqa']['id'] == str(c.id)


# ── Sozlamalar ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize('module', ['config.settings.development', 'config.settings.windows',
                                    'config.settings.test'])
def test_throttle_scopes_configured_in_every_settings_module(module):
    """Har bir sozlamalar fayli REST_FRAMEWORK'ni o'zi yozadi — scope yo'q bo'lsa endpoint 500 beradi."""
    import importlib
    rates = importlib.import_module(module).REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
    assert {'musobaqa_public', 'musobaqa_register'} <= set(rates)
