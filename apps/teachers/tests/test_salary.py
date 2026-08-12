import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.teachers.models import Teacher, TeacherSalaryPayment


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        phone='+998900000050', password='pass1234',
        full_name='Finance User', role=User.Role.FINANCE,
    )


@pytest.fixture
def teacher_role_user(db):
    return User.objects.create_user(
        phone='+998900000051', password='pass1234',
        full_name='Plain Teacher User', role=User.Role.TEACHER,
    )


def make_teacher(phone, name, salary_type=Teacher.SalaryType.FIXED, salary=1000000, hourly_rate=0):
    user = User.objects.create_user(phone=phone, password='pass1234', full_name=name, role=User.Role.TEACHER)
    return Teacher.objects.create(
        user=user, phone=phone, salary_type=salary_type, salary=salary, hourly_rate=hourly_rate,
    )


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestFixedSalary:

    def test_backward_compatible_payload_still_works(self, finance_user):
        """The existing salary.html frontend only ever sends teacher/month/year/amount/bonus/note."""
        teacher = make_teacher('+998900000060', 'Fixed Teacher')
        client = auth_client(finance_user)
        resp = client.post('/api/v1/teachers/salaries/', {
            'teacher': str(teacher.id), 'month': 1, 'year': 2026,
            'amount': 1000000, 'bonus': 50000, 'note': 'test',
        })
        assert resp.status_code == 201
        assert resp.data['total'] == 1050000
        assert resp.data['status'] == 'paid'  # default, matches old implicit "row exists = paid"

    def test_deductions_reduce_total(self, finance_user):
        teacher = make_teacher('+998900000061', 'Deduction Teacher')
        client = auth_client(finance_user)
        resp = client.post('/api/v1/teachers/salaries/', {
            'teacher': str(teacher.id), 'month': 2, 'year': 2026,
            'amount': 1000000, 'bonus': 50000, 'deductions': 100000,
        })
        assert resp.status_code == 201
        assert resp.data['total'] == 950000

    def test_duplicate_month_still_blocked(self, finance_user):
        teacher = make_teacher('+998900000062', 'Dup Teacher')
        TeacherSalaryPayment.objects.create(teacher=teacher, month=3, year=2026, amount=1000000)
        client = auth_client(finance_user)
        resp = client.post('/api/v1/teachers/salaries/', {
            'teacher': str(teacher.id), 'month': 3, 'year': 2026, 'amount': 1000000,
        })
        assert resp.status_code == 400


@pytest.mark.django_db
class TestHourlySalary:

    def test_amount_auto_calculated_from_hours(self, finance_user):
        teacher = make_teacher('+998900000063', 'Hourly Teacher',
                               salary_type=Teacher.SalaryType.HOURLY, hourly_rate=50000)
        client = auth_client(finance_user)
        resp = client.post('/api/v1/teachers/salaries/', {
            'teacher': str(teacher.id), 'month': 4, 'year': 2026, 'worked_hours': 20,
        })
        assert resp.status_code == 201
        assert resp.data['amount'] == '1000000'  # 50000 * 20
        assert resp.data['salary_type'] == 'hourly'

    def test_explicit_amount_overrides_auto_calc(self, finance_user):
        teacher = make_teacher('+998900000064', 'Hourly Override Teacher',
                               salary_type=Teacher.SalaryType.HOURLY, hourly_rate=50000)
        client = auth_client(finance_user)
        resp = client.post('/api/v1/teachers/salaries/', {
            'teacher': str(teacher.id), 'month': 5, 'year': 2026, 'worked_hours': 20, 'amount': 900000,
        })
        assert resp.status_code == 201
        assert resp.data['amount'] == '900000'

    def test_fixed_teacher_without_amount_is_rejected(self, finance_user):
        teacher = make_teacher('+998900000065', 'No Amount Teacher')
        client = auth_client(finance_user)
        resp = client.post('/api/v1/teachers/salaries/', {
            'teacher': str(teacher.id), 'month': 6, 'year': 2026,
        })
        assert resp.status_code == 400


@pytest.mark.django_db
class TestSalaryStatusAndUpdate:

    def test_pending_can_be_marked_paid_via_patch(self, finance_user):
        teacher = make_teacher('+998900000066', 'Pending Teacher')
        payment = TeacherSalaryPayment.objects.create(
            teacher=teacher, month=7, year=2026, amount=1000000,
            status=TeacherSalaryPayment.Status.PENDING,
        )
        client = auth_client(finance_user)
        resp = client.patch(f'/api/v1/teachers/salaries/{payment.id}/', {'status': 'paid'})
        assert resp.status_code == 200
        payment.refresh_from_db()
        assert payment.status == TeacherSalaryPayment.Status.PAID

    def test_filter_by_status(self, finance_user):
        teacher = make_teacher('+998900000067', 'Status Filter Teacher')
        TeacherSalaryPayment.objects.create(teacher=teacher, month=8, year=2026, amount=1000000,
                                            status=TeacherSalaryPayment.Status.PENDING)
        client = auth_client(finance_user)
        resp = client.get('/api/v1/teachers/salaries/?status=pending&month=8&year=2026')
        assert resp.status_code == 200


@pytest.mark.django_db
class TestSalaryPermissions:

    def test_teacher_role_cannot_access_salaries(self, teacher_role_user):
        client = auth_client(teacher_role_user)
        resp = client.get('/api/v1/teachers/salaries/')
        assert resp.status_code == 403

    def test_finance_can_delete_salary(self, finance_user):
        teacher = make_teacher('+998900000068', 'Delete Teacher')
        payment = TeacherSalaryPayment.objects.create(teacher=teacher, month=9, year=2026, amount=1000000)
        client = auth_client(finance_user)
        resp = client.delete(f'/api/v1/teachers/salaries/{payment.id}/')
        assert resp.status_code == 204
