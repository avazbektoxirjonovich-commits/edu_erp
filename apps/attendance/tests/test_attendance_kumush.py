"""
Attendance → KUMUSH reward tests.

Business rule under test: marking a student PRESENT gives exactly +10
KUMUSH, exactly once per attendance record, no matter how many times the
record is saved, retried, or double-submitted — and reversing away from
PRESENT claws the +10 back (once), with re-award if flipped back.
"""
import datetime

import pytest

from apps.attendance.models import Attendance
from apps.notifications.models import ActivityLog
from apps.store.models import KumushTransaction
from apps.attendance.tests.conftest import auth_client

TODAY = datetime.date(2026, 2, 1)


@pytest.mark.django_db
class TestAttendancePresentReward:

    def test_present_gives_exactly_ten_kumush(self, teacher_a, student_a):
        teacher_user, _, group = teacher_a
        _, student = student_a
        client = auth_client(teacher_user)

        resp = client.post('/api/v1/attendance/', {
            'student': str(student.id), 'group': str(group.id),
            'date': str(TODAY), 'status': 'present',
        }, format='json')
        assert resp.status_code == 201

        student.refresh_from_db()
        assert student.coins == 10

    def test_absent_gives_no_kumush(self, teacher_a, student_a):
        teacher_user, _, group = teacher_a
        _, student = student_a
        client = auth_client(teacher_user)

        client.post('/api/v1/attendance/', {
            'student': str(student.id), 'group': str(group.id),
            'date': str(TODAY), 'status': 'absent',
        }, format='json')

        student.refresh_from_db()
        assert student.coins == 0

    def test_ledger_row_has_correct_forensic_fields(self, teacher_a, student_a):
        teacher_user, _, group = teacher_a
        _, student = student_a
        client = auth_client(teacher_user)

        client.post('/api/v1/attendance/', {
            'student': str(student.id), 'group': str(group.id),
            'date': str(TODAY), 'status': 'present',
        }, format='json')

        txn = KumushTransaction.objects.get(student=student, source_type='attendance')
        assert txn.amount == 10
        assert txn.type == KumushTransaction.Type.EARN
        assert txn.created_by == teacher_user
        assert txn.balance_before == 0
        assert txn.balance_after == 10
        attendance = Attendance.objects.get(student=student, group=group, date=TODAY)
        assert txn.source_id == str(attendance.pk)


@pytest.mark.django_db
class TestAttendanceDuplicateProtection:

    def test_editing_the_same_record_to_same_status_does_not_double_award(self, teacher_a, student_a):
        teacher_user, _, group = teacher_a
        _, student = student_a
        client = auth_client(teacher_user)

        create_resp = client.post('/api/v1/attendance/', {
            'student': str(student.id), 'group': str(group.id),
            'date': str(TODAY), 'status': 'present',
        }, format='json')
        attendance_id = create_resp.data['id']

        # Save again with the same status — simulates double-click / retry
        client.put(f'/api/v1/attendance/{attendance_id}/', {
            'student': str(student.id), 'group': str(group.id),
            'date': str(TODAY), 'status': 'present',
        }, format='json')

        student.refresh_from_db()
        assert student.coins == 10  # not 20
        assert KumushTransaction.objects.filter(student=student, source_type='attendance').count() == 1

    def test_repeated_raw_api_call_same_effect(self, teacher_a, student_a):
        """Direct call to the sync function itself, simulating a retried
        request hitting the exact same code path multiple times."""
        from apps.attendance.services import sync_attendance_kumush

        teacher_user, _, group = teacher_a
        _, student = student_a
        attendance = Attendance.objects.create(
            student=student, group=group, date=TODAY,
            status=Attendance.Status.PRESENT, marked_by=teacher_user,
        )
        for _ in range(5):
            sync_attendance_kumush(attendance, actor=teacher_user)

        student.refresh_from_db()
        assert student.coins == 10
        assert KumushTransaction.objects.filter(student=student, source_type='attendance').count() == 1


@pytest.mark.django_db
class TestAttendanceReversal:

    def test_present_to_absent_claws_back_reward(self, teacher_a, student_a):
        teacher_user, _, group = teacher_a
        _, student = student_a
        client = auth_client(teacher_user)

        create_resp = client.post('/api/v1/attendance/', {
            'student': str(student.id), 'group': str(group.id),
            'date': str(TODAY), 'status': 'present',
        }, format='json')
        attendance_id = create_resp.data['id']
        student.refresh_from_db()
        assert student.coins == 10

        client.put(f'/api/v1/attendance/{attendance_id}/', {
            'student': str(student.id), 'group': str(group.id),
            'date': str(TODAY), 'status': 'absent',
        }, format='json')

        student.refresh_from_db()
        assert student.coins == 0
        reversal = KumushTransaction.objects.get(student=student, source_type='attendance_reversal')
        assert reversal.amount == -10

    def test_reversal_is_idempotent(self, teacher_a, student_a):
        from apps.attendance.services import sync_attendance_kumush

        teacher_user, _, group = teacher_a
        _, student = student_a
        attendance = Attendance.objects.create(
            student=student, group=group, date=TODAY,
            status=Attendance.Status.PRESENT, marked_by=teacher_user,
        )
        sync_attendance_kumush(attendance, actor=teacher_user)
        student.refresh_from_db()
        assert student.coins == 10

        attendance.status = Attendance.Status.ABSENT
        attendance.save(update_fields=['status'])
        for _ in range(3):
            sync_attendance_kumush(attendance, actor=teacher_user)

        student.refresh_from_db()
        assert student.coins == 0
        assert KumushTransaction.objects.filter(student=student, source_type='attendance_reversal').count() == 1

    def test_flip_back_to_present_reawards_exactly_once(self, teacher_a, student_a):
        from apps.attendance.services import sync_attendance_kumush

        teacher_user, _, group = teacher_a
        _, student = student_a
        attendance = Attendance.objects.create(
            student=student, group=group, date=TODAY,
            status=Attendance.Status.PRESENT, marked_by=teacher_user,
        )
        sync_attendance_kumush(attendance, actor=teacher_user)  # +10

        attendance.status = Attendance.Status.ABSENT
        attendance.save(update_fields=['status'])
        sync_attendance_kumush(attendance, actor=teacher_user)  # -10

        attendance.status = Attendance.Status.PRESENT
        attendance.save(update_fields=['status'])
        sync_attendance_kumush(attendance, actor=teacher_user)  # +10 again
        sync_attendance_kumush(attendance, actor=teacher_user)  # no-op, already present+awarded

        student.refresh_from_db()
        assert student.coins == 10
        assert KumushTransaction.objects.filter(student=student, source_type='attendance').count() == 2
        assert KumushTransaction.objects.filter(student=student, source_type='attendance_reversal').count() == 1

    def test_reversal_clamps_instead_of_going_negative(self, teacher_a, student_a):
        """If the student already spent the reward elsewhere before the
        correction, the reversal must clamp to available balance rather
        than take coins negative — a disclosed, deliberate edge case."""
        from apps.attendance.services import sync_attendance_kumush

        teacher_user, _, group = teacher_a
        _, student = student_a
        attendance = Attendance.objects.create(
            student=student, group=group, date=TODAY,
            status=Attendance.Status.PRESENT, marked_by=teacher_user,
        )
        sync_attendance_kumush(attendance, actor=teacher_user)  # +10
        student.refresh_from_db()
        assert student.coins == 10

        # Simulate the student having spent most of it elsewhere
        student.apply_kumush_and_xp(coins_delta=-7, reason='spent at store', source_type='test')
        student.refresh_from_db()
        assert student.coins == 3

        attendance.status = Attendance.Status.ABSENT
        attendance.save(update_fields=['status'])
        sync_attendance_kumush(attendance, actor=teacher_user)

        student.refresh_from_db()
        assert student.coins == 0  # clamped, never negative


@pytest.mark.django_db
class TestAttendanceKumushAuditLog:

    def test_award_creates_activity_log(self, teacher_a, student_a):
        teacher_user, _, group = teacher_a
        _, student = student_a
        client = auth_client(teacher_user)

        client.post('/api/v1/attendance/', {
            'student': str(student.id), 'group': str(group.id),
            'date': str(TODAY), 'status': 'present',
        }, format='json')

        attendance = Attendance.objects.get(student=student, group=group, date=TODAY)
        log = ActivityLog.objects.get(model_name='Attendance', object_id=str(attendance.pk))
        assert log.user == teacher_user
        assert log.changes['kumush_awarded'] == 10

    def test_reversal_creates_activity_log(self, teacher_a, student_a):
        from apps.attendance.services import sync_attendance_kumush

        teacher_user, _, group = teacher_a
        _, student = student_a
        attendance = Attendance.objects.create(
            student=student, group=group, date=TODAY,
            status=Attendance.Status.PRESENT, marked_by=teacher_user,
        )
        sync_attendance_kumush(attendance, actor=teacher_user)
        attendance.status = Attendance.Status.ABSENT
        attendance.save(update_fields=['status'])
        sync_attendance_kumush(attendance, actor=teacher_user)

        logs = ActivityLog.objects.filter(model_name='Attendance', object_id=str(attendance.pk))
        assert logs.count() == 2
        reversal_log = [l for l in logs if 'kumush_reversed' in l.changes][0]
        assert reversal_log.changes['kumush_reversed'] == 10


@pytest.mark.django_db
class TestBulkAttendanceKumush:

    def test_bulk_present_awards_all_students(self, teacher_a, student_a, student_b):
        teacher_user, _, group = teacher_a
        _, student1 = student_a
        _, student2 = student_b
        client = auth_client(teacher_user)

        resp = client.post('/api/v1/attendance/bulk/', {
            'group': str(group.id), 'date': str(TODAY),
            'records': [
                {'student': str(student1.id), 'status': 'present'},
                {'student': str(student2.id), 'status': 'present'},
            ],
        }, format='json')
        assert resp.status_code == 201

        student1.refresh_from_db()
        student2.refresh_from_db()
        assert student1.coins == 10
        assert student2.coins == 10

    def test_bulk_double_submit_does_not_double_award(self, teacher_a, student_a):
        teacher_user, _, group = teacher_a
        _, student = student_a
        client = auth_client(teacher_user)
        payload = {
            'group': str(group.id), 'date': str(TODAY),
            'records': [{'student': str(student.id), 'status': 'present'}],
        }

        client.post('/api/v1/attendance/bulk/', payload, format='json')
        client.post('/api/v1/attendance/bulk/', payload, format='json')  # resubmit whole group

        student.refresh_from_db()
        assert student.coins == 10
        assert KumushTransaction.objects.filter(student=student, source_type='attendance').count() == 1

    def test_bulk_mixed_present_and_absent(self, teacher_a, student_a, student_b):
        teacher_user, _, group = teacher_a
        _, student1 = student_a
        _, student2 = student_b
        client = auth_client(teacher_user)

        client.post('/api/v1/attendance/bulk/', {
            'group': str(group.id), 'date': str(TODAY),
            'records': [
                {'student': str(student1.id), 'status': 'present'},
                {'student': str(student2.id), 'status': 'absent'},
            ],
        }, format='json')

        student1.refresh_from_db()
        student2.refresh_from_db()
        assert student1.coins == 10
        assert student2.coins == 0
