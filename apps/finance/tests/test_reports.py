"""Moliya hisobotlari: kassirlar, to'lov turlari, oyliklar."""
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.groups.models import Group
from apps.students.models import Student
from apps.teachers.models import Teacher, TeacherSalaryPayment

RECORD = '/api/v1/finance/transactions/record/'


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def mk(phone, role, name):
    return User.objects.create_user(phone=phone, password='pass1234', full_name=name, role=role)


@pytest.fixture
def setup(db):
    k1, k2 = mk('+998905550001', User.Role.FINANCE, 'Kassir Bir'), mk('+998905550002', User.Role.FINANCE, 'Kassir Ikki')
    admin = mk('+998905550003', User.Role.ADMIN, 'Admin')
    group = Group.objects.create(name='R', start_date='2026-01-01', start_time='09:00', end_time='10:00')
    su = mk('+998905550010', User.Role.STUDENT, 'Oquvchi')
    student = Student.objects.create(user=su, phone=su.phone, group=group, monthly_fee=5000000)
    return {'k1': k1, 'k2': k2, 'admin': admin, 'student': student}


def pay(user, student, amount, ptype):
    return client_for(user).post(RECORD, {'student': str(student.id), 'month': 9, 'year': 2026,
                                          'amount': amount, 'payment_type': ptype})


@pytest.mark.django_db
def test_cashier_report_totals_by_person_and_type(setup):
    s = setup
    pay(s['k1'], s['student'], 100000, 'cash')
    pay(s['k1'], s['student'], 200000, 'terminal')
    pay(s['k2'], s['student'], 300000, 'bank_account')
    gone = pay(s['k2'], s['student'], 999000, 'card_transfer').data['transaction']['id']
    client_for(s['admin']).post(f'/api/v1/finance/transactions/{gone}/cancel/', {'reason': 'Xato'})

    today = timezone.localdate().isoformat()
    resp = client_for(s['k1']).get(f'/api/v1/finance/reports/?start={today}&end={today}')
    assert resp.status_code == 200
    P = resp.data['payments']
    assert (P['total'], P['count']) == (600000, 3)
    assert P['cancelled'] == {'total': 999000, 'count': 1}
    assert {t['payment_type']: t['total'] for t in P['by_type']} == {
        'cash': 100000, 'terminal': 200000, 'bank_account': 300000}
    assert [(c['name'], c['total'], c['count'], c['by_type']) for c in P['cashiers']] == [
        ('Kassir Bir', 300000, 2, {'cash': 100000, 'terminal': 200000}),
        ('Kassir Ikki', 300000, 1, {'bank_account': 300000}),
    ]  # teng summada ism bo'yicha
    # Har bir chek (bekor qilingani ham) ro'yxatda — qachon, kim, qancha
    assert len(P['receipts']) == 4
    assert sum(1 for r in P['receipts'] if r['is_cancelled']) == 1
    assert {r['received_by_name'] for r in P['receipts']} == {'Kassir Bir', 'Kassir Ikki'}


@pytest.mark.django_db
def test_period_filter_excludes_other_days(setup):
    s = setup
    pay(s['k1'], s['student'], 100000, 'cash')
    resp = client_for(s['k1']).get('/api/v1/finance/reports/?start=2020-01-01&end=2020-01-31')
    assert resp.data['payments']['total'] == 0
    assert resp.data['payments']['receipts'] == []


@pytest.mark.django_db
def test_salary_report_who_how_much_when(setup):
    tu = mk('+998905550020', User.Role.TEACHER, 'Ustoz Olim')
    teacher = Teacher.objects.create(user=tu, phone=tu.phone, salary=3000000)
    TeacherSalaryPayment.objects.create(teacher=teacher, month=8, year=2026, amount=3000000,
                                        bonus=200000, deductions=100000, paid_by=setup['admin'])
    TeacherSalaryPayment.objects.create(teacher=teacher, month=7, year=2026, amount=1000,
                                        status=TeacherSalaryPayment.Status.PENDING)
    today = timezone.localdate().isoformat()
    resp = client_for(setup['k1']).get(f'/api/v1/finance/reports/?start={today}&end={today}')
    S = resp.data['salaries']
    assert S['total'] == 3100000  # faqat to'langani, bonus/ushlab qolinganni hisobga olib
    assert [(i['teacher_name'], i['total'], i['paid_by_name']) for i in S['items']] == [
        ('Ustoz Olim', 3100000, 'Admin')]
    assert S['by_teacher'] == [{'teacher_name': 'Ustoz Olim', 'total': 3100000}]


@pytest.mark.django_db
def test_bad_period_rejected(setup):
    c = client_for(setup['k1'])
    assert c.get('/api/v1/finance/reports/?start=2026-02-10&end=2026-02-01').status_code == 400
    assert c.get('/api/v1/finance/reports/?start=xx&end=yy').status_code == 400


@pytest.mark.django_db
def test_teacher_cannot_see_reports(setup):
    tu = mk('+998905550030', User.Role.TEACHER, 'T')
    assert client_for(tu).get('/api/v1/finance/reports/').status_code == 403
