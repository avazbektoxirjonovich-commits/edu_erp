from datetime import datetime
from datetime import timezone as dt_timezone

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.finance.models import Expense, PaymentTransaction
from apps.groups.models import Group
from apps.payments.models import Payment
from apps.students.models import Student
from apps.teachers.models import Teacher, TeacherSalaryPayment


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        phone='+998900000070', password='pass1234',
        full_name='Finance User', role=User.Role.FINANCE,
    )


@pytest.fixture
def teacher_role_user(db):
    return User.objects.create_user(
        phone='+998900000071', password='pass1234',
        full_name='Teacher User', role=User.Role.TEACHER,
    )


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestExpenseCRUD:

    def test_finance_can_create_expense(self, finance_user):
        client = auth_client(finance_user)
        resp = client.post('/api/v1/finance/expenses/', {
            'name': 'Oylik ijara', 'category': 'rent', 'amount': 3000000,
            'expense_date': '2026-03-05', 'description': 'Mart oyi ijarasi',
        })
        assert resp.status_code == 201
        assert resp.data['category_display'] == 'Ijara'
        assert resp.data['created_by_name'] == 'Finance User'

    def test_teacher_cannot_access_expenses(self, teacher_role_user):
        client = auth_client(teacher_role_user)
        resp = client.get('/api/v1/finance/expenses/')
        assert resp.status_code == 403

    def test_filter_by_category(self, finance_user):
        client = auth_client(finance_user)
        Expense.objects.create(name='Internet to\'lovi', category='internet', amount=500000,
                               expense_date='2026-03-10')
        Expense.objects.create(name='Reklama', category='advertising', amount=200000,
                               expense_date='2026-03-11')
        resp = client.get('/api/v1/finance/expenses/?category=internet')
        results = resp.data.get('results', resp.data)
        assert len(results) == 1
        assert results[0]['category'] == 'internet'

    def test_filter_by_month_year(self, finance_user):
        client = auth_client(finance_user)
        Expense.objects.create(name='March expense', category='other', amount=100000, expense_date='2026-03-15')
        Expense.objects.create(name='April expense', category='other', amount=100000, expense_date='2026-04-15')
        resp = client.get('/api/v1/finance/expenses/?month=3&year=2026')
        results = resp.data.get('results', resp.data)
        assert len(results) == 1
        assert results[0]['name'] == 'March expense'

    def test_search_by_name(self, finance_user):
        client = auth_client(finance_user)
        Expense.objects.create(name='Konditsioner ta\'mirlash', category='repair', amount=300000,
                               expense_date='2026-03-20')
        Expense.objects.create(name='Qog\'oz sotib olish', category='other', amount=50000,
                               expense_date='2026-03-21')
        resp = client.get('/api/v1/finance/expenses/?search=Konditsioner')
        results = resp.data.get('results', resp.data)
        assert len(results) == 1

    def test_update_and_delete_expense(self, finance_user):
        client = auth_client(finance_user)
        expense = Expense.objects.create(name='Old name', category='other', amount=100000,
                                         expense_date='2026-03-01')
        resp = client.patch(f'/api/v1/finance/expenses/{expense.id}/', {'name': 'New name'})
        assert resp.status_code == 200
        assert resp.data['name'] == 'New name'

        resp2 = client.delete(f'/api/v1/finance/expenses/{expense.id}/')
        assert resp2.status_code == 204
        assert not Expense.objects.filter(id=expense.id).exists()


@pytest.mark.django_db
class TestFinancialSummary:

    def test_net_result_calculation(self, finance_user):
        # Income: one student payment of 500000 in March 2026.
        student_user = User.objects.create_user(
            phone='+998900000072', password='pass1234', full_name='Summary Student', role=User.Role.STUDENT,
        )
        group = Group.objects.create(name='Summary Group', start_date='2026-01-01',
                                     start_time='09:00', end_time='10:00', monthly_fee=500000)
        student = Student.objects.create(user=student_user, phone=student_user.phone, group=group)
        payment = Payment.objects.create(student=student, group=group, month=3, year=2026, amount=500000)
        PaymentTransaction.objects.create(
            payment=payment, amount=500000,
            paid_at=datetime(2026, 3, 5, 10, 0, tzinfo=dt_timezone.utc),
        )

        # Salary expense: 1,000,000 (paid) in March 2026.
        teacher_user = User.objects.create_user(
            phone='+998900000073', password='pass1234', full_name='Summary Teacher', role=User.Role.TEACHER,
        )
        teacher = Teacher.objects.create(user=teacher_user, phone=teacher_user.phone, salary=1000000)
        TeacherSalaryPayment.objects.create(
            teacher=teacher, month=3, year=2026, amount=1000000,
            paid_at=datetime(2026, 3, 10, 10, 0, tzinfo=dt_timezone.utc),
            status=TeacherSalaryPayment.Status.PAID,
        )
        # A PENDING salary must NOT count as an expense yet.
        TeacherSalaryPayment.objects.create(
            teacher=teacher, month=4, year=2026, amount=99999999,
            paid_at=datetime(2026, 3, 12, 10, 0, tzinfo=dt_timezone.utc),
            status=TeacherSalaryPayment.Status.PENDING,
        )

        # Other expense: 300,000 rent in March 2026.
        Expense.objects.create(name='Rent', category='rent', amount=300000, expense_date='2026-03-15')

        client = auth_client(finance_user)
        resp = client.get('/api/v1/finance/expenses/summary/?month=3&year=2026')
        assert resp.status_code == 200
        assert resp.data['total_income'] == 500000.0
        assert resp.data['total_salaries'] == 1000000.0
        assert resp.data['total_other_expenses'] == 300000.0
        assert resp.data['total_expenses'] == 1300000.0
        assert resp.data['net_result'] == -800000.0

    def test_custom_date_range(self, finance_user):
        Expense.objects.create(name='Range expense', category='other', amount=100000, expense_date='2026-05-15')
        client = auth_client(finance_user)
        resp = client.get('/api/v1/finance/expenses/summary/?start=2026-05-01&end=2026-05-31')
        assert resp.status_code == 200
        assert resp.data['total_other_expenses'] == 100000.0

    def test_invalid_month_returns_400(self, finance_user):
        client = auth_client(finance_user)
        resp = client.get('/api/v1/finance/expenses/summary/?month=13&year=2026')
        assert resp.status_code == 400

    def test_teacher_cannot_view_summary(self, teacher_role_user):
        client = auth_client(teacher_role_user)
        resp = client.get('/api/v1/finance/expenses/summary/')
        assert resp.status_code == 403
