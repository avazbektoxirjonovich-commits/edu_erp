"""ERP "Arizalar" paneli: ko'rish, bog'lanish va PANEL OCHISH (akkaunt yaratish)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.arizalar.models import Application
from apps.groups.models import Group
from apps.notifications.models import ActivityLog
from apps.students.models import Student

URL = '/api/v1/arizalar/'


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(phone='+998905550001', password='pass1234',
                                    full_name='Admin', role=User.Role.ADMIN)


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(phone='+998905550002', password='pass1234',
                                    full_name='Kassir', role=User.Role.FINANCE)


@pytest.fixture
def group(db):
    return Group.objects.create(name='Ariza guruh', start_date='2026-01-01',
                                start_time='09:00', end_time='10:00')


@pytest.fixture
def ariza(db):
    return Application.objects.create(
        full_name="Aliyev Vali Anvar o'g'li", phone='+998901112233',
        address="Qorako'l, Navoiy 12", parent_name='Aliyev Anvar',
        age=12, direction='Matematika')


@pytest.mark.django_db
class TestAccess:

    def test_admin_sees_applications(self, admin_user, ariza):
        resp = client_for(admin_user).get(URL)
        assert resp.status_code == 200
        rows = resp.data.get('results', resp.data)
        assert rows[0]['full_name'] == ariza.full_name

    @pytest.mark.parametrize('role', [User.Role.FINANCE, User.Role.TEACHER, User.Role.STUDENT])
    def test_other_roles_denied(self, db, ariza, role):
        user = User.objects.create_user(phone='+998905559999', password='pass1234',
                                        full_name='X', role=role)
        assert client_for(user).get(URL).status_code == 403

    def test_anonymous_denied(self, ariza):
        assert APIClient().get(URL).status_code == 401

    def test_cannot_create_application_from_erp(self, admin_user):
        """Ariza faqat saytdan keladi — ERP'dan qo'lda yaratilmaydi."""
        resp = client_for(admin_user).post(URL, {'full_name': 'X'}, format='json')
        assert resp.status_code == 405

    def test_detail_shows_everything(self, admin_user, ariza):
        d = client_for(admin_user).get(f'{URL}{ariza.id}/').data
        assert (d['address'], d['parent_name'], d['age'], d['direction']) == (
            ariza.address, ariza.parent_name, 12, 'Matematika')

    def test_search_and_filter(self, admin_user, ariza):
        Application.objects.create(full_name='Boshqa Odam', phone='+998901119999',
                                   address='manzil', parent_name='Ota Ona', age=9,
                                   direction='Ingliz tili', status=Application.Status.REJECTED)
        client = client_for(admin_user)
        rows = client.get(f'{URL}?search=Matematika').data
        assert len(rows.get('results', rows)) == 1
        rows = client.get(f'{URL}?status=rejected').data
        assert len(rows.get('results', rows)) == 1


@pytest.mark.django_db
class TestHandling:

    def test_mark_contacted(self, admin_user, ariza):
        resp = client_for(admin_user).post(f'{URL}{ariza.id}/contacted/')
        assert resp.status_code == 200
        ariza.refresh_from_db()
        assert (ariza.status, ariza.handled_by) == (Application.Status.CONTACTED, admin_user)
        assert ariza.handled_at is not None
        log = ActivityLog.objects.filter(model_name='Application').latest('created_at')
        assert log.changes['status'] == {'old': 'new', 'new': 'contacted'}

    def test_reject(self, admin_user, ariza):
        assert client_for(admin_user).post(f'{URL}{ariza.id}/reject/').status_code == 200
        ariza.refresh_from_db()
        assert ariza.status == Application.Status.REJECTED

    def test_note_saved(self, admin_user, ariza):
        resp = client_for(admin_user).patch(f'{URL}{ariza.id}/',
                                            {'note': 'Ertaga keladi'}, format='json')
        assert resp.status_code == 200
        ariza.refresh_from_db()
        assert ariza.note == 'Ertaga keladi'

    def test_stats(self, admin_user, ariza):
        Application.objects.create(full_name='Ikkinchi Odam', phone='+998901118888',
                                   address='m', parent_name='O O', age=8, direction='Fizika',
                                   status=Application.Status.CONTACTED)
        d = client_for(admin_user).get(f'{URL}stats/').data
        assert (d['new'], d['open']) == (1, 2)


@pytest.mark.django_db
class TestOpenPanel:
    """"Panel ochish" — arizadan o'quvchi akkaunti."""

    def test_fee_is_required(self, admin_user, ariza):
        resp = client_for(admin_user).post(f'{URL}{ariza.id}/convert/', {}, format='json')
        assert resp.status_code == 400
        assert 'monthly_fee' in resp.data
        assert not Student.objects.exists() and not User.objects.filter(role='student').exists()
        ariza.refresh_from_db()
        assert ariza.status == Application.Status.NEW

    @pytest.mark.parametrize('fee', [0, -1000])
    def test_zero_or_negative_fee_refused(self, admin_user, ariza, fee):
        resp = client_for(admin_user).post(f'{URL}{ariza.id}/convert/',
                                           {'monthly_fee': fee}, format='json')
        assert resp.status_code == 400
        assert not Student.objects.exists()

    def test_panel_opens_with_all_data(self, admin_user, ariza, group):
        resp = client_for(admin_user).post(
            f'{URL}{ariza.id}/convert/',
            {'monthly_fee': 500000, 'discount': 100000, 'group': str(group.id)}, format='json')
        assert resp.status_code == 201

        student = Student.objects.get()
        assert student.full_name == ariza.full_name
        assert (student.phone, student.monthly_fee, student.discount) == (ariza.phone, 500000, 100000)
        assert student.group == group
        assert student.address == ariza.address
        assert student.parent_name == ariza.parent_name
        # Arizadagi yosh va yo'nalish yo'qolmaydi
        assert '12' in student.notes and 'Matematika' in student.notes
        assert student.user.role == User.Role.STUDENT

        ariza.refresh_from_db()
        assert ariza.status == Application.Status.ENROLLED
        assert ariza.student_id == student.id
        assert ariza.handled_by == admin_user

        # Javobda kirish ma'lumotlari
        assert resp.data['phone'] == ariza.phone
        assert len(resp.data['parol']) == 6 and resp.data['parol'].isdigit()
        assert student.user.check_password(resp.data['parol'])

    def test_custom_password_used(self, admin_user, ariza):
        resp = client_for(admin_user).post(
            f'{URL}{ariza.id}/convert/',
            {'monthly_fee': 300000, 'password': 'maxfiy123'}, format='json')
        assert resp.status_code == 201
        assert Student.objects.get().user.check_password('maxfiy123')

    def test_group_optional(self, admin_user, ariza):
        resp = client_for(admin_user).post(f'{URL}{ariza.id}/convert/',
                                           {'monthly_fee': 300000}, format='json')
        assert resp.status_code == 201
        assert Student.objects.get().group is None

    def test_second_click_refused(self, admin_user, ariza):
        client = client_for(admin_user)
        assert client.post(f'{URL}{ariza.id}/convert/', {'monthly_fee': 300000},
                           format='json').status_code == 201
        resp = client.post(f'{URL}{ariza.id}/convert/', {'monthly_fee': 300000}, format='json')
        assert resp.status_code == 400
        # Aynan "allaqachon ochilgan" tekshiruvi ishlashi kerak (telefon bandligi emas)
        assert 'allaqachon' in resp.data['detail']
        assert Student.objects.count() == 1          # ikkinchi akkaunt ochilmadi

    def test_busy_phone_blocks_and_creates_nothing(self, admin_user, ariza):
        User.objects.create_user(phone=ariza.phone, password='pass1234',
                                 full_name='Boshqa Odam', role=User.Role.PARENT)
        resp = client_for(admin_user).post(f'{URL}{ariza.id}/convert/',
                                           {'monthly_fee': 300000}, format='json')
        assert resp.status_code == 400
        assert 'band' in resp.data['detail']
        assert not Student.objects.exists()
        ariza.refresh_from_db()
        assert ariza.status == Application.Status.NEW

    def test_rejected_application_cannot_be_opened(self, admin_user, ariza):
        ariza.status = Application.Status.REJECTED
        ariza.save(update_fields=['status'])
        resp = client_for(admin_user).post(f'{URL}{ariza.id}/convert/',
                                           {'monthly_fee': 300000}, format='json')
        assert resp.status_code == 400
        assert not Student.objects.exists()

    def test_discount_above_fee_refused(self, admin_user, ariza):
        resp = client_for(admin_user).post(
            f'{URL}{ariza.id}/convert/', {'monthly_fee': 300000, 'discount': 400000}, format='json')
        assert resp.status_code == 400
        assert not Student.objects.exists()

    def test_unknown_group_refused(self, admin_user, ariza):
        import uuid
        resp = client_for(admin_user).post(
            f'{URL}{ariza.id}/convert/',
            {'monthly_fee': 300000, 'group': str(uuid.uuid4())}, format='json')
        assert resp.status_code == 400
        assert not Student.objects.exists()

    def test_finance_cannot_open_panel(self, finance_user, ariza):
        resp = client_for(finance_user).post(f'{URL}{ariza.id}/convert/',
                                             {'monthly_fee': 300000}, format='json')
        assert resp.status_code == 403
        assert not Student.objects.exists()

    def test_opening_is_logged(self, admin_user, ariza):
        client_for(admin_user).post(f'{URL}{ariza.id}/convert/',
                                    {'monthly_fee': 300000}, format='json')
        models = set(ActivityLog.objects.values_list('model_name', flat=True))
        assert {'Student', 'Application'} <= models

    def test_new_student_can_log_in(self, admin_user, ariza):
        """Panel haqiqatan ochiladi: o'quvchi berilgan parol bilan tizimga kiradi."""
        resp = client_for(admin_user).post(f'{URL}{ariza.id}/convert/',
                                           {'monthly_fee': 300000}, format='json')
        login = APIClient().post('/api/v1/auth/login/',
                                 {'phone': ariza.phone, 'password': resp.data['parol']},
                                 format='json')
        assert login.status_code == 200
        assert 'access' in login.data
