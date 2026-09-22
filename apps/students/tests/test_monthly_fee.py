"""Oylik to'lov faqat o'quvchida: ochilganda e'lon qilinadi, keyin o'zgartiriladi."""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.groups.models import Group
from apps.notifications.models import ActivityLog
from apps.students.models import Student


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(phone='+998902220001', password='pass1234',
                                    full_name='Admin', role=User.Role.ADMIN)


@pytest.fixture
def group(db):
    return Group.objects.create(name='Fee Group', start_date='2026-01-01',
                                start_time='09:00', end_time='10:00')


def new_student_payload(group, **extra):
    return {'full_name': 'Yangi O\'quvchi', 'phone': '+998902220010', 'password': 'pass1234',
            'group': str(group.id), **extra}


@pytest.mark.django_db
class TestStudentFee:

    def test_fee_required_when_student_created(self, admin_user, group):
        resp = auth_client(admin_user).post('/api/v1/students/', new_student_payload(group), format='json')
        assert resp.status_code == 400
        assert 'monthly_fee' in resp.data
        assert not Student.objects.exists()

    def test_fee_saved_on_create(self, admin_user, group):
        resp = auth_client(admin_user).post(
            '/api/v1/students/', new_student_payload(group, monthly_fee=450000), format='json')
        assert resp.status_code == 201
        assert Student.objects.get().monthly_fee == 450000

    def test_negative_fee_rejected(self, admin_user, group):
        resp = auth_client(admin_user).post(
            '/api/v1/students/', new_student_payload(group, monthly_fee=-1), format='json')
        assert resp.status_code == 400

    def test_fee_change_logged(self, admin_user, group):
        client = auth_client(admin_user)
        client.post('/api/v1/students/', new_student_payload(group, monthly_fee=450000), format='json')
        student = Student.objects.get()
        resp = client.patch(f'/api/v1/students/{student.id}/', {'monthly_fee': 380000}, format='json')
        assert resp.status_code == 200
        log = ActivityLog.objects.filter(model_name='Student', action='update').latest('created_at')
        assert log.changes['monthly_fee'] == {'old': '450000', 'new': '380000'}

    def test_fee_not_inherited_from_group(self, admin_user, group):
        """Guruhda narx yo'q — guruhga qo'shilish narxni o'zgartirmaydi."""
        assert not hasattr(group, 'monthly_fee')
        resp = auth_client(admin_user).get(f'/api/v1/groups/{group.id}/')
        assert 'monthly_fee' not in resp.data


@pytest.mark.django_db(transaction=True)
def test_migration_moves_group_fee_to_students_and_back():
    """Haqiqiy migratsiya: guruh narxi o'quvchilarga ko'chadi, orqaga qaytsa guruhga tiklanadi."""
    before = [('students', '0006_student_monthly_fee'), ('groups', '0006_group_payment_due_day')]
    after = [('students', '0007_copy_fee_from_group'), ('groups', '0007_remove_group_monthly_fee')]

    executor = MigrationExecutor(connection)
    executor.migrate(before)
    old = executor.loader.project_state(before).apps
    OldUser, OldGroup, OldStudent = (old.get_model('accounts', 'User'), old.get_model('groups', 'Group'),
                                     old.get_model('students', 'Student'))
    g = OldGroup.objects.create(name='Eski', start_date='2026-01-01', start_time='09:00',
                                end_time='10:00', monthly_fee=650000)
    u1 = OldUser.objects.create(phone='+998902220101', full_name='A', role='student')
    u2 = OldUser.objects.create(phone='+998902220102', full_name='B', role='student')
    u3 = OldUser.objects.create(phone='+998902220103', full_name='C', role='student')
    s_inherit = OldStudent.objects.create(user=u1, phone=u1.phone, group=g)
    s_personal = OldStudent.objects.create(user=u2, phone=u2.phone, group=g, monthly_fee=300000)
    s_nogroup = OldStudent.objects.create(user=u3, phone=u3.phone, group=None)

    executor = MigrationExecutor(connection)
    executor.migrate(after)
    new = executor.loader.project_state(after).apps.get_model('students', 'Student')
    assert new.objects.get(pk=s_inherit.pk).monthly_fee == 650000   # guruhdan ko'chdi
    assert new.objects.get(pk=s_personal.pk).monthly_fee == 300000  # shaxsiysi saqlandi
    assert new.objects.get(pk=s_nogroup.pk).monthly_fee is None

    executor = MigrationExecutor(connection)
    executor.migrate(before)
    restored = executor.loader.project_state(before).apps.get_model('groups', 'Group')
    assert restored.objects.get(pk=g.pk).monthly_fee in (650000, 300000)

    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())
