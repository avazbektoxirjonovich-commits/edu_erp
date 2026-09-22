"""5-bosqich: admin ball kiritadi, o'rinlar avtomatik hisoblanadi."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.musobaqalar.models import Competition, Participant, Result
from apps.notifications.models import ActivityLog

URL = '/api/v1/musobaqalar/'


@pytest.fixture
def api(db):
    user = User.objects.create_user(phone='+998908881001', password='pass1234',
                                    full_name='Admin', role=User.Role.ADMIN)
    c = APIClient()
    c.force_authenticate(user=user)
    c.user = user
    return c


def competition(status=Competition.Status.FINISHED):
    return Competition.objects.create(name='Oktyabr', grade_from=1, grade_to=11, status=status,
                                      registration_deadline=timezone.now() - timedelta(days=3))


def participant(c, phone, grade=None, name='Ali'):
    return Participant.objects.create(competition=c, first_name=name, last_name='Valiyev',
                                      phone=phone, address='x', grade=grade)


@pytest.mark.django_db
class TestResultEntry:

    def test_enter_and_update_score(self, api):
        p = participant(competition(), '+998901230001')
        resp = api.post(f'{URL}participants/{p.id}/result/', {'score': 87}, format='json')
        assert resp.status_code == 200
        assert (resp.data['score'], resp.data['place']) == (87, None)
        resp = api.post(f'{URL}participants/{p.id}/result/', {'score': 90, 'place': 1}, format='json')
        assert (resp.data['score'], resp.data['place']) == (90, 1)
        r = Result.objects.get(participant=p)
        assert (r.score, r.place, r.entered_by) == (90, 1, api.user)
        log = ActivityLog.objects.filter(model_name='Participant').latest('created_at')
        assert log.changes['score'] == {'old': '87', 'new': '90'}

    def test_clear_score(self, api):
        p = participant(competition(), '+998901230002')
        api.post(f'{URL}participants/{p.id}/result/', {'score': 50}, format='json')
        resp = api.post(f'{URL}participants/{p.id}/result/', {'score': None}, format='json')
        assert resp.data['score'] is None
        assert not Result.objects.exists()

    @pytest.mark.parametrize('st', ['draft', 'published'])
    def test_not_before_registration_closed(self, api, st):
        p = participant(competition(status=st), '+998901230003')
        resp = api.post(f'{URL}participants/{p.id}/result/', {'score': 50}, format='json')
        assert resp.status_code == 400
        assert not Result.objects.exists()

    def test_allowed_when_registration_closed(self, api):
        p = participant(competition(status=Competition.Status.REGISTRATION_CLOSED), '+998901230004')
        assert api.post(f'{URL}participants/{p.id}/result/', {'score': 50}, format='json').status_code == 200

    @pytest.mark.parametrize('bad', [{'score': -1}, {'score': 'abc'}, {'score': 5, 'place': 0}, {}])
    def test_validation(self, api, bad):
        p = participant(competition(), '+998901230005')
        assert api.post(f'{URL}participants/{p.id}/result/', bad, format='json').status_code == 400

    def test_teacher_cannot_enter(self, db):
        user = User.objects.create_user(phone='+998908881002', password='pass1234',
                                        full_name='T', role=User.Role.TEACHER)
        c = APIClient()
        c.force_authenticate(user=user)
        p = participant(competition(), '+998901230006')
        assert c.post(f'{URL}participants/{p.id}/result/', {'score': 5}, format='json').status_code == 403


@pytest.mark.django_db
class TestAutoRank:

    def test_rank_by_score_within_grade_with_ties(self, api):
        c = competition()
        scores = {('+998901240001', 5): 90, ('+998901240002', 5): 95, ('+998901240003', 5): 90,
                  ('+998901240004', 5): 70, ('+998901240005', 6): 60, ('+998901240006', None): 88,
                  ('+998901240007', None): 99}
        for (phone, grade), score in scores.items():
            Result.objects.create(participant=participant(c, phone, grade), score=score)
        resp = api.post(f'{URL}competitions/{c.id}/rank/')
        assert resp.status_code == 200
        assert resp.data['ranked'] == 7
        got = {(r.participant.phone, r.participant.grade): r.place for r in Result.objects.select_related('participant')}
        assert got == {('+998901240002', 5): 1, ('+998901240001', 5): 2, ('+998901240003', 5): 2,
                       ('+998901240004', 5): 4, ('+998901240005', 6): 1,
                       ('+998901240007', None): 1, ('+998901240006', None): 2}

    def test_rank_is_reflected_in_public_results(self, api):
        c = competition()
        for i, score in enumerate([70, 95, 80]):
            Result.objects.create(participant=participant(c, f'+99890125000{i}', name=f'Ism{i}'), score=score)
        api.post(f'{URL}competitions/{c.id}/rank/')
        top = APIClient().get(f'/api/public/musobaqa/natijalar/{c.id}/').data['sinflar'][0]['natijalar']
        assert [(r['ism'], r['orin']) for r in top] == [('Ism1', 1), ('Ism2', 2), ('Ism0', 3)]

    def test_rank_refused_before_registration_closed(self, api):
        c = competition(status=Competition.Status.PUBLISHED)
        assert api.post(f'{URL}competitions/{c.id}/rank/').status_code == 400
