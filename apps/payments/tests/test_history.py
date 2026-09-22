"""To'lov bosilganda: to'liq ma'lumot + kim qachon nima qilgani."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.groups.models import Group
from apps.payments.models import Payment
from apps.students.models import Student


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def people(db):
    mk = lambda phone, role, name: User.objects.create_user(  # noqa: E731
        phone=phone, password='pass1234', full_name=name, role=role)
    return {
        'kassir': mk('+998904440001', User.Role.FINANCE, 'Kassir Karim'),
        'admin': mk('+998904440002', User.Role.ADMIN, 'Admin Anvar'),
        'teacher': mk('+998904440003', User.Role.TEACHER, 'Ustoz'),
    }


@pytest.fixture
def student(db):
    group = Group.objects.create(name='H', start_date='2026-01-01', start_time='09:00', end_time='10:00')
    user = User.objects.create_user(phone='+998904440010', password='pass1234',
                                    full_name='Vali', role=User.Role.STUDENT)
    return Student.objects.create(user=user, phone=user.phone, group=group, monthly_fee=600000)


@pytest.mark.django_db
def test_history_shows_who_did_what(people, student):
    kassir, admin = client_for(people['kassir']), client_for(people['admin'])
    first = kassir.post('/api/v1/finance/transactions/record/', {
        'student': str(student.id), 'month': 9, 'year': 2026, 'amount': 200000, 'payment_type': 'terminal'})
    kassir.post('/api/v1/finance/transactions/record/', {
        'student': str(student.id), 'month': 9, 'year': 2026, 'amount': 100000, 'payment_type': 'cash'})
    admin.post(f"/api/v1/finance/transactions/{first.data['transaction']['id']}/cancel/", {'reason': 'Xato'})
    payment = Payment.objects.get(student=student)
    admin.patch(f'/api/v1/payments/{payment.id}/', {'discount': 50000})

    resp = kassir.get(f'/api/v1/payments/{payment.id}/history/')
    assert resp.status_code == 200
    p = resp.data['payment']
    assert (p['amount'], p['discount'], p['paid_amount'], p['debt_amount']) == ('600000', '50000', '100000', '450000')
    assert p['student_phone'] == student.phone

    txns = resp.data['transactions']
    assert [(t['amount'], t['payment_type'], t['is_cancelled'], t['received_by_name']) for t in txns] == [
        ('200000', 'terminal', True, 'Kassir Karim'), ('100000', 'cash', False, 'Kassir Karim')]
    assert txns[0]['cancelled_by_name'] == 'Admin Anvar'

    events = [(h['model_name'], h['user_name'], h['action']) for h in resp.data['history']]
    assert events == [
        ('PaymentTransaction', 'Kassir Karim', 'create'),
        ('PaymentTransaction', 'Kassir Karim', 'create'),
        ('PaymentTransaction', 'Admin Anvar', 'update'),
        ('Payment', 'Admin Anvar', 'update'),
    ]
    assert resp.data['history'][2]['receipt_number'] == first.data['transaction']['receipt_number']
    assert resp.data['history'][3]['changes']['discount'] == {'old': '0', 'new': '50000'}


@pytest.mark.django_db
def test_history_not_for_teacher(people, student):
    payment = Payment.objects.create(student=student, group=student.group, month=9, year=2026, amount=600000)
    resp = client_for(people['teacher']).get(f'/api/v1/payments/{payment.id}/history/')
    assert resp.status_code == 403
