"""Xona muammosi: guruh ochishda bir xonaga bir vaqtda ikki guruh qo'yilmasin."""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.groups.models import Group, LessonSchedule, Room

GROUPS = '/api/v1/groups/'
ROOMS = '/api/v1/groups/rooms/'


@pytest.fixture
def admin(db):
    user = User.objects.create_user(phone='+998907770001', password='pass1234',
                                    full_name='Admin', role=User.Role.ADMIN)
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def rooms(db):
    return {n: Room.objects.create(name=n, capacity=15) for n in ('101', '102')}


def new_group(admin, name, start, end, days, room='', **extra):
    return admin.post(GROUPS, {'name': name, 'start_time': start, 'end_time': end,
                               'days': days, 'room': room, **extra}, format='json')


@pytest.mark.django_db
class TestRoomConflicts:

    def test_same_room_same_time_rejected(self, admin, rooms):
        assert new_group(admin, 'Python A1', '14:00', '15:30', [1, 3], '101').status_code == 201
        resp = new_group(admin, 'English B1', '15:00', '16:00', [3, 5], '101')
        assert resp.status_code == 400
        msg = str(resp.data)
        assert 'Python A1' in msg and 'Chorshanba' in msg and '101' in msg
        assert not Group.objects.filter(name='English B1').exists()

    def test_back_to_back_lessons_allowed(self, admin, rooms):
        new_group(admin, 'A', '14:00', '15:30', [1], '101')
        assert new_group(admin, 'B', '15:30', '17:00', [1], '101').status_code == 201

    def test_other_room_or_other_day_allowed(self, admin, rooms):
        new_group(admin, 'A', '14:00', '15:30', [1], '101')
        assert new_group(admin, 'B', '14:00', '15:30', [1], '102').status_code == 201
        assert new_group(admin, 'C', '14:00', '15:30', [2], '101').status_code == 201

    def test_room_name_case_and_spaces_ignored(self, admin, rooms):
        Room.objects.create(name='Katta zal')
        new_group(admin, 'A', '10:00', '12:00', [6], 'Katta zal')
        assert new_group(admin, 'B', '11:00', '13:00', [6], ' katta ZAL ').status_code == 400

    def test_unknown_room_rejected(self, admin, rooms):
        resp = new_group(admin, 'A', '10:00', '12:00', [1], '999')
        assert resp.status_code == 400
        assert "ro'yxatda yo'q" in str(resp.data['room'][0])

    def test_inactive_or_finished_group_does_not_block(self, admin, rooms):
        new_group(admin, 'Eski', '14:00', '15:30', [1], '101', status='completed')
        new_group(admin, 'Tugagan', '14:00', '15:30', [2], '101', end_date='2026-01-31',
                  start_date='2025-09-01')
        assert new_group(admin, 'Yangi', '14:00', '15:30', [1], '101').status_code == 201
        assert new_group(admin, 'Yangi2', '14:00', '15:30', [2], '101',
                         start_date='2026-09-01').status_code == 201

    def test_set_schedule_rejects_busy_room(self, admin, rooms):
        new_group(admin, 'A', '14:00', '15:30', [1], '101')
        b = new_group(admin, 'B', '14:30', '16:00', [2], '102').data
        resp = admin.post(f"{GROUPS}{b['id']}/set-schedule/",
                          {'schedules': [{'day_of_week': 1, 'room': '101'}]}, format='json')
        assert resp.status_code == 400
        # Rad etilganda eski jadval o'zgarmaydi
        assert list(LessonSchedule.objects.filter(group_id=b['id']).values_list('day_of_week', 'room')) == [
            (2, '102')]

    def test_changing_time_into_conflict_rejected(self, admin, rooms):
        new_group(admin, 'A', '14:00', '15:30', [1], '101')
        b = new_group(admin, 'B', '16:00', '17:00', [1], '101').data
        resp = admin.patch(f"{GROUPS}{b['id']}/", {'start_time': '15:00'}, format='json')
        assert resp.status_code == 400
        assert str(Group.objects.get(pk=b['id']).start_time) == '16:00:00'

    def test_reactivating_group_into_conflict_rejected(self, admin, rooms):
        a = new_group(admin, 'A', '14:00', '15:30', [1], '101', status='inactive').data
        new_group(admin, 'B', '14:00', '15:30', [1], '101')
        resp = admin.patch(f"{GROUPS}{a['id']}/", {'status': 'active'}, format='json')
        assert resp.status_code == 400

    def test_editing_days_keeps_rooms(self, admin, rooms):
        """Oldin: guruh kunlari qayta yozilsa xonalar yo'qolardi."""
        g = new_group(admin, 'A', '14:00', '15:30', [1, 3], '101').data
        admin.patch(f"{GROUPS}{g['id']}/", {'days': [1, 3, 5]}, format='json')
        rooms_by_day = dict(LessonSchedule.objects.filter(group_id=g['id']).values_list('day_of_week', 'room'))
        assert rooms_by_day == {1: '101', 3: '101', 5: ''}

    def test_end_before_start_rejected(self, admin, rooms):
        assert new_group(admin, 'A', '15:00', '14:00', [1], '101').status_code == 400


@pytest.mark.django_db
class TestRoomApi:

    def test_list_shows_usage(self, admin, rooms):
        new_group(admin, 'Python A1', '14:00', '15:30', [1, 3], '101')
        resp = admin.get(ROOMS)
        rows = resp.data.get('results', resp.data)
        usage = {r['name']: [(u['day_of_week'], u['group_name']) for u in r['usages']] for r in rows}
        assert usage == {'101': [(1, 'Python A1'), (3, 'Python A1')], '102': []}

    def test_duplicate_name_rejected(self, admin, rooms):
        assert admin.post(ROOMS, {'name': ' 101 '}, format='json').status_code == 400

    def test_rename_updates_schedules(self, admin, rooms):
        g = new_group(admin, 'A', '14:00', '15:30', [1], '101').data
        admin.patch(f"{ROOMS}{rooms['101'].id}/", {'name': '201'}, format='json')
        assert LessonSchedule.objects.get(group_id=g['id']).room == '201'

    def test_cannot_delete_used_room(self, admin, rooms):
        new_group(admin, 'A', '14:00', '15:30', [1], '101')
        assert admin.delete(f"{ROOMS}{rooms['101'].id}/").status_code == 400
        assert admin.delete(f"{ROOMS}{rooms['102'].id}/").status_code == 204

    def test_teacher_can_view_not_edit(self, rooms):
        user = User.objects.create_user(phone='+998907770002', password='pass1234',
                                        full_name='T', role=User.Role.TEACHER)
        c = APIClient()
        c.force_authenticate(user=user)
        assert c.get(ROOMS).status_code == 200
        assert c.post(ROOMS, {'name': '303'}, format='json').status_code == 403


@pytest.mark.django_db(transaction=True)
def test_migration_builds_rooms_from_free_text():
    before = [('groups', '0008_room')]
    after = [('groups', '0009_rooms_from_schedules')]
    executor = MigrationExecutor(connection)
    executor.migrate(before)
    old = executor.loader.project_state(before).apps
    G, S, R = old.get_model('groups', 'Group'), old.get_model('groups', 'LessonSchedule'), old.get_model('groups', 'Room')
    g1 = G.objects.create(name='A', start_date='2026-01-01', start_time='09:00', end_time='10:00')
    g2 = G.objects.create(name='B', start_date='2026-01-01', start_time='11:00', end_time='12:00')
    S.objects.create(group=g1, day_of_week=1, room='101')
    S.objects.create(group=g2, day_of_week=1, room=' 101 ')
    S.objects.create(group=g2, day_of_week=2, room='Zal')
    S.objects.create(group=g1, day_of_week=2, room='')

    executor = MigrationExecutor(connection)
    executor.migrate(after)
    new = executor.loader.project_state(after).apps
    assert sorted(new.get_model('groups', 'Room').objects.values_list('name', flat=True)) == ['101', 'Zal']
    assert sorted(new.get_model('groups', 'LessonSchedule').objects.values_list('room', flat=True)) == [
        '', '101', '101', 'Zal']

    executor = MigrationExecutor(connection)
    executor.migrate(before)
    assert not executor.loader.project_state(before).apps.get_model('groups', 'Room').objects.exists()
    assert R  # tarixiy model bor

    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())
