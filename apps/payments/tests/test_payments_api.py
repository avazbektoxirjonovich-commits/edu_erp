"""
FIN-006 — regression safety net for apps/payments.

This app backs PaymentViewSet, PaymentDetailView, UnpaidStudentsView,
MonthlySummaryView, and MyPaymentsView, none of which had any test coverage
before this file. The goal here is to pin down CURRENT behavior (including
the still-reachable legacy overwrite/upsert path and its quirks) so future
changes to this app have a regression net — not to fix anything.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.groups.models import Group
from apps.payments.models import Payment
from apps.students.models import Student
from apps.teachers.models import Teacher


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        phone='+998900000300', password='pass1234',
        full_name='Finance User', role=User.Role.FINANCE,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        phone='+998900000301', password='pass1234',
        full_name='Admin User', role=User.Role.ADMIN,
    )


@pytest.fixture
def group(db):
    return Group.objects.create(
        name='Payments Group', start_date='2026-01-01',
        start_time='09:00', end_time='10:00', monthly_fee=500000,
    )


@pytest.fixture
def other_group(db):
    return Group.objects.create(
        name='Other Payments Group', start_date='2026-01-01',
        start_time='09:00', end_time='10:00', monthly_fee=400000,
    )


@pytest.fixture
def teacher_role_user(db, group):
    """A teacher whose Teacher profile owns `group`."""
    user = User.objects.create_user(
        phone='+998900000302', password='pass1234',
        full_name='Teacher User', role=User.Role.TEACHER,
    )
    teacher = Teacher.objects.create(user=user, phone=user.phone)
    group.teacher = teacher
    group.save(update_fields=['teacher'])
    return user


@pytest.fixture
def teacher_without_profile(db):
    """Role=teacher but no Teacher row exists yet — an edge case the view must
    handle gracefully (empty queryset, not a crash)."""
    return User.objects.create_user(
        phone='+998900000303', password='pass1234',
        full_name='Profileless Teacher', role=User.Role.TEACHER,
    )


@pytest.fixture
def student_user(db):
    return User.objects.create_user(
        phone='+998900000304', password='pass1234',
        full_name='Bare Student Role', role=User.Role.STUDENT,
    )


@pytest.fixture
def parent_user(db):
    return User.objects.create_user(
        phone='+998900000305', password='pass1234',
        full_name='Parent User', role=User.Role.PARENT,
    )


@pytest.fixture
def student(db, group):
    """Student in the teacher-owned group."""
    user = User.objects.create_user(
        phone='+998900000306', password='pass1234',
        full_name='Payments Student', role=User.Role.STUDENT,
    )
    return Student.objects.create(user=user, phone=user.phone, group=group)


@pytest.fixture
def other_student(db, other_group):
    """Student in a *different* group, owned by no teacher fixture here —
    used to prove teacher scoping and MyPaymentsView ownership boundaries."""
    user = User.objects.create_user(
        phone='+998900000307', password='pass1234',
        full_name='Other Payments Student', role=User.Role.STUDENT,
    )
    return Student.objects.create(user=user, phone=user.phone, group=other_group)


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ─────────────────────────────────────────────────────────────────────────
# PaymentViewSet — GET (list)
# ─────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestPaymentListPermissions:

    def test_finance_can_list(self, finance_user, student):
        Payment.objects.create(student=student, group=student.group, month=1, year=2026, amount=500000)
        resp = auth_client(finance_user).get('/api/v1/payments/')
        assert resp.status_code == 200

    def test_admin_can_list(self, admin_user, student):
        resp = auth_client(admin_user).get('/api/v1/payments/')
        assert resp.status_code == 200

    def test_teacher_can_list(self, teacher_role_user, student):
        resp = auth_client(teacher_role_user).get('/api/v1/payments/')
        assert resp.status_code == 200

    def test_student_role_cannot_list(self, student_user):
        resp = auth_client(student_user).get('/api/v1/payments/')
        assert resp.status_code == 403

    def test_parent_cannot_list(self, parent_user):
        resp = auth_client(parent_user).get('/api/v1/payments/')
        assert resp.status_code == 403

    def test_unauthenticated_cannot_list(self):
        resp = APIClient().get('/api/v1/payments/')
        assert resp.status_code == 401


@pytest.mark.django_db
class TestPaymentListTeacherScoping:

    def test_teacher_sees_only_own_group_students(self, teacher_role_user, student, other_student):
        Payment.objects.create(student=student, group=student.group, month=2, year=2026, amount=500000)
        Payment.objects.create(student=other_student, group=other_student.group, month=2, year=2026, amount=400000)

        resp = auth_client(teacher_role_user).get('/api/v1/payments/?month=2&year=2026')
        assert resp.status_code == 200
        rows = resp.data['results'] if 'results' in resp.data else resp.data
        ids = [str(row['student']) for row in rows]
        assert str(student.id) in ids
        assert str(other_student.id) not in ids

    def test_teacher_without_profile_gets_empty_list(self, teacher_without_profile, student):
        Payment.objects.create(student=student, group=student.group, month=2, year=2026, amount=500000)
        resp = auth_client(teacher_without_profile).get('/api/v1/payments/')
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        assert results == []

    def test_finance_sees_all_groups(self, finance_user, student, other_student):
        Payment.objects.create(student=student, group=student.group, month=2, year=2026, amount=500000)
        Payment.objects.create(student=other_student, group=other_student.group, month=2, year=2026, amount=400000)
        resp = auth_client(finance_user).get('/api/v1/payments/?month=2&year=2026')
        results = resp.data.get('results', resp.data)
        assert len(results) == 2


# ─────────────────────────────────────────────────────────────────────────
# PaymentViewSet — POST (create / legacy upsert)
# ─────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestPaymentCreatePermissions:

    def test_finance_can_create(self, finance_user, student):
        resp = auth_client(finance_user).post('/api/v1/payments/', {
            'student': str(student.id), 'month': 3, 'year': 2026, 'paid_amount': 100000,
        })
        assert resp.status_code == 201

    def test_admin_can_create(self, admin_user, student):
        resp = auth_client(admin_user).post('/api/v1/payments/', {
            'student': str(student.id), 'month': 3, 'year': 2026, 'paid_amount': 100000,
        })
        assert resp.status_code == 201

    def test_teacher_cannot_create(self, teacher_role_user, student):
        resp = auth_client(teacher_role_user).post('/api/v1/payments/', {
            'student': str(student.id), 'month': 3, 'year': 2026, 'paid_amount': 100000,
        })
        assert resp.status_code == 403

    def test_student_cannot_create(self, student_user, student):
        resp = auth_client(student_user).post('/api/v1/payments/', {
            'student': str(student.id), 'month': 3, 'year': 2026, 'paid_amount': 100000,
        })
        assert resp.status_code == 403


@pytest.mark.django_db
class TestPaymentCreateBehavior:

    def test_amount_defaults_from_group_monthly_fee(self, finance_user, student):
        resp = auth_client(finance_user).post('/api/v1/payments/', {
            'student': str(student.id), 'month': 4, 'year': 2026, 'paid_amount': 100000,
        })
        assert resp.status_code == 201
        assert resp.data['amount'] == '500000'  # student.group.monthly_fee

    def test_negative_paid_amount_rejected(self, finance_user, student):
        resp = auth_client(finance_user).post('/api/v1/payments/', {
            'student': str(student.id), 'month': 4, 'year': 2026, 'paid_amount': -1000,
        })
        assert resp.status_code == 400

    def test_missing_student_rejected(self, finance_user):
        resp = auth_client(finance_user).post('/api/v1/payments/', {
            'month': 4, 'year': 2026, 'paid_amount': 100000,
        })
        assert resp.status_code == 400

    def test_second_post_for_same_bill_overwrites_rather_than_accumulates(self, finance_user, student):
        """
        Documents the legacy endpoint's known upsert/overwrite semantics (FIN-001):
        this is unchanged in this phase — Phase 20.1 moved the live payment UI off
        this endpoint onto the receipted PaymentTransaction ledger, but the endpoint
        itself is intentionally kept reachable for compatibility. `group` must be
        omitted here to match the real payload the old UI sent — see the note in
        apps/finance/tests/test_audit.py::TestPaymentUpsertAuditLabel for why an
        explicit `group` value hits DRF's auto unique-together validator instead
        (400) and never reaches this upsert branch at all.
        """
        first = auth_client(finance_user).post('/api/v1/payments/', {
            'student': str(student.id), 'month': 5, 'year': 2026, 'paid_amount': 100000,
        })
        assert first.status_code == 201

        second = auth_client(finance_user).post('/api/v1/payments/', {
            'student': str(student.id), 'month': 5, 'year': 2026, 'paid_amount': 300000,
        })
        assert second.status_code == 201
        assert second.data['paid_amount'] == '300000'  # overwritten, not 100000+300000

        assert Payment.objects.filter(student=student, month=5, year=2026).count() == 1


# ─────────────────────────────────────────────────────────────────────────
# PaymentDetailView — GET / PATCH
# ─────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestPaymentDetailView:

    def test_finance_can_get_and_patch(self, finance_user, student):
        payment = Payment.objects.create(student=student, group=student.group, month=6, year=2026, amount=500000)
        client = auth_client(finance_user)

        get_resp = client.get(f'/api/v1/payments/{payment.id}/')
        assert get_resp.status_code == 200

        patch_resp = client.patch(f'/api/v1/payments/{payment.id}/', {'paid_amount': 200000})
        assert patch_resp.status_code == 200
        assert patch_resp.data['paid_amount'] == '200000'
        # PaymentUpdateSerializer's response only echoes paid_amount/note/payment_date
        # (not status/debt_amount) — confirm the model-derived fields via the DB row.
        payment.refresh_from_db()
        assert payment.status == Payment.Status.PARTIAL
        assert payment.debt_amount == 300000

    def test_admin_can_get_and_patch(self, admin_user, student):
        payment = Payment.objects.create(student=student, group=student.group, month=6, year=2026, amount=500000)
        resp = auth_client(admin_user).get(f'/api/v1/payments/{payment.id}/')
        assert resp.status_code == 200

    def test_teacher_cannot_access_detail_even_though_they_can_list(self, teacher_role_user, student):
        """
        Current (undisturbed) behavior: PaymentDetailView.permission_classes is
        IsFinanceOrAdmin only, unlike PaymentViewSet's list action which also
        allows IsAdminOrTeacher — so a teacher who can see this payment in the
        list view is still blocked from its detail endpoint. Documented as-is.
        """
        payment = Payment.objects.create(student=student, group=student.group, month=6, year=2026, amount=500000)
        resp = auth_client(teacher_role_user).get(f'/api/v1/payments/{payment.id}/')
        assert resp.status_code == 403

    def test_negative_patch_amount_rejected(self, finance_user, student):
        payment = Payment.objects.create(student=student, group=student.group, month=6, year=2026, amount=500000)
        resp = auth_client(finance_user).patch(f'/api/v1/payments/{payment.id}/', {'paid_amount': -500})
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────
# UnpaidStudentsView
# ─────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestUnpaidStudentsView:

    def test_returns_only_unpaid_and_partial(self, finance_user, student, other_student):
        Payment.objects.create(student=student, group=student.group, month=7, year=2026,
                                amount=500000, paid_amount=500000)  # paid -> excluded
        Payment.objects.create(student=other_student, group=other_student.group, month=7, year=2026,
                                amount=400000, paid_amount=100000)  # partial -> included

        resp = auth_client(finance_user).get('/api/v1/payments/unpaid/?month=7&year=2026')
        assert resp.status_code == 200
        ids = [str(row['student']) for row in resp.data]
        assert str(other_student.id) in ids
        assert str(student.id) not in ids

    def test_invalid_month_rejected(self, finance_user):
        resp = auth_client(finance_user).get('/api/v1/payments/unpaid/?month=13&year=2026')
        assert resp.status_code == 400

    def test_teacher_denied(self, teacher_role_user):
        resp = auth_client(teacher_role_user).get('/api/v1/payments/unpaid/')
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────
# MonthlySummaryView
# ─────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestMonthlySummaryView:

    def test_aggregates_correctly(self, finance_user, student, other_student):
        Payment.objects.create(student=student, group=student.group, month=8, year=2026,
                                amount=500000, paid_amount=500000)
        Payment.objects.create(student=other_student, group=other_student.group, month=8, year=2026,
                                amount=400000, paid_amount=100000)

        resp = auth_client(finance_user).get('/api/v1/payments/summary/?month=8&year=2026')
        assert resp.status_code == 200
        assert resp.data['total_amount'] == 900000
        assert resp.data['total_paid'] == 600000
        assert resp.data['total_debt'] == 300000
        assert resp.data['paid_count'] == 1
        assert resp.data['partial_count'] == 1

    def test_invalid_year_rejected(self, finance_user):
        resp = auth_client(finance_user).get('/api/v1/payments/summary/?month=1&year=1899')
        assert resp.status_code == 400

    def test_teacher_denied(self, teacher_role_user):
        resp = auth_client(teacher_role_user).get('/api/v1/payments/summary/')
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────
# MyPaymentsView
# ─────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestMyPaymentsView:

    def test_student_sees_only_own_payments(self, student, other_student):
        Payment.objects.create(student=student, group=student.group, month=9, year=2026, amount=500000)
        Payment.objects.create(student=other_student, group=other_student.group, month=9, year=2026, amount=400000)

        resp = auth_client(student.user).get('/api/v1/payments/my/')
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        assert len(results) == 1
        assert str(results[0]['student']) == str(student.id)

    def test_non_student_user_gets_empty_list_not_error(self, finance_user):
        resp = auth_client(finance_user).get('/api/v1/payments/my/')
        assert resp.status_code == 200
        assert resp.data.get('results', resp.data) == []

    def test_unauthenticated_denied(self):
        resp = APIClient().get('/api/v1/payments/my/')
        assert resp.status_code == 401
