"""
Homework grading → KUMUSH reward tests.

Business rule: KUMUSH = score percentage (score/max_score*100, integer
arithmetic). Re-submitting the same grade must not duplicate the reward;
changing the score must award only the delta.
"""
import pytest

from apps.notifications.models import ActivityLog
from apps.store.models import KumushTransaction
from apps.homework.tests.conftest import auth_client


@pytest.mark.django_db
class TestHomeworkKumushFormula:

    @pytest.mark.parametrize('score,expected_kumush', [(100, 100), (80, 80), (70, 70), (50, 50), (0, 0)])
    def test_score_percentage_formula(self, teacher_a, submission, score, expected_kumush):
        teacher_user, _, _ = teacher_a
        submission.grade(score=score, feedback='', graded_by=teacher_user)

        submission.student.refresh_from_db()
        assert submission.student.coins == expected_kumush
        submission.refresh_from_db()
        assert submission.kumush_awarded == expected_kumush

    def test_non_100_max_score_uses_correct_percentage(self, teacher_a, student_a):
        from apps.homework.models import Assignment, Submission
        teacher_user, teacher, group = teacher_a
        _, student = student_a
        assignment = Assignment.objects.create(
            title='50-point quiz', description='d', group=group, teacher=teacher,
            max_score=50, xp_reward=25,
        )
        sub = Submission.objects.create(assignment=assignment, student=student)

        sub.grade(score=40, feedback='', graded_by=teacher_user)  # 40/50 = 80%

        student.refresh_from_db()
        assert student.coins == 80

    def test_xp_uses_old_formula_unchanged(self, teacher_a, submission):
        """XP must remain on the pre-existing xp_reward-based formula,
        decoupled from the new KUMUSH percentage rule."""
        teacher_user, _, _ = teacher_a
        # xp_reward=50, max_score=100 → xp = 50 * score // 100
        submission.grade(score=80, feedback='', graded_by=teacher_user)

        submission.student.refresh_from_db()
        assert submission.student.xp_points == 40  # 50 * 80 // 100
        assert submission.student.coins == 80        # unrelated new KUMUSH formula


@pytest.mark.django_db
class TestHomeworkDuplicateProtection:

    def test_regrading_same_score_awards_nothing_extra(self, teacher_a, submission):
        teacher_user, _, _ = teacher_a
        submission.grade(score=80, feedback='', graded_by=teacher_user)
        submission.grade(score=80, feedback='updated feedback', graded_by=teacher_user)

        submission.student.refresh_from_db()
        assert submission.student.coins == 80  # not 160
        assert KumushTransaction.objects.filter(
            student=submission.student, source_type='homework', source_id=str(submission.pk),
        ).count() == 1

    def test_regrading_via_api_same_score_no_duplicate(self, teacher_a, submission):
        teacher_user, _, _ = teacher_a
        client = auth_client(teacher_user)
        url = f'/api/v1/homework/submissions/{submission.pk}/grade/'

        client.post(url, {'score': 80}, format='json')
        client.post(url, {'score': 80}, format='json')  # double-click / retry

        submission.student.refresh_from_db()
        assert submission.student.coins == 80

    def test_repeated_identical_grade_call_five_times(self, teacher_a, submission):
        teacher_user, _, _ = teacher_a
        for _ in range(5):
            submission.grade(score=100, feedback='', graded_by=teacher_user)

        submission.student.refresh_from_db()
        assert submission.student.coins == 100

    def test_score_increase_awards_only_the_delta(self, teacher_a, submission):
        teacher_user, _, _ = teacher_a
        submission.grade(score=60, feedback='', graded_by=teacher_user)
        submission.student.refresh_from_db()
        assert submission.student.coins == 60

        submission.grade(score=80, feedback='', graded_by=teacher_user)
        submission.student.refresh_from_db()
        assert submission.student.coins == 80  # 60 + 20 delta, not 60+80=140

        txns = KumushTransaction.objects.filter(
            student=submission.student, source_type='homework', source_id=str(submission.pk),
        ).order_by('created_at')
        assert [t.amount for t in txns] == [60, 20]

    def test_score_decrease_claws_back_the_difference(self, teacher_a, submission):
        teacher_user, _, _ = teacher_a
        submission.grade(score=80, feedback='', graded_by=teacher_user)
        submission.grade(score=50, feedback='corrected', graded_by=teacher_user)

        submission.student.refresh_from_db()
        assert submission.student.coins == 50
        submission.refresh_from_db()
        assert submission.kumush_awarded == 50

    def test_final_reward_matches_final_score_after_multiple_regrades(self, teacher_a, submission):
        teacher_user, _, _ = teacher_a
        for score in [60, 80, 70, 90]:
            submission.grade(score=score, feedback='', graded_by=teacher_user)

        submission.student.refresh_from_db()
        assert submission.student.coins == 90  # matches the last/final score only


@pytest.mark.django_db
class TestHomeworkLedgerAndAttribution:

    def test_ledger_row_records_grading_teacher(self, teacher_a, submission):
        teacher_user, _, _ = teacher_a
        submission.grade(score=100, feedback='', graded_by=teacher_user)

        txn = KumushTransaction.objects.get(student=submission.student, source_type='homework')
        assert txn.created_by == teacher_user
        assert txn.amount == 100
        assert txn.type == KumushTransaction.Type.EARN
        assert txn.balance_before == 0
        assert txn.balance_after == 100
        assert txn.source_id == str(submission.pk)

    def test_max_score_zero_awards_nothing_no_crash(self, teacher_a, student_a):
        from apps.homework.models import Assignment, Submission
        teacher_user, teacher, group = teacher_a
        _, student = student_a
        # max_score has MinValueValidator(1) at the serializer/admin level,
        # but the model itself doesn't enforce it — exercise the model's
        # own guard directly (defense-in-depth already present in grade()).
        assignment = Assignment(
            title='Zero max', description='d', group=group, teacher=teacher,
            max_score=0, xp_reward=10,
        )
        assignment.save()
        sub = Submission.objects.create(assignment=assignment, student=student)

        sub.grade(score=0, feedback='', graded_by=teacher_user)  # must not raise

        student.refresh_from_db()
        assert student.coins == 0


@pytest.mark.django_db
class TestHomeworkKumushAuditLog:

    def test_grading_creates_activity_log(self, teacher_a, submission):
        teacher_user, _, _ = teacher_a
        submission.grade(score=80, feedback='', graded_by=teacher_user)

        log = ActivityLog.objects.get(model_name='Submission', object_id=str(submission.pk))
        assert log.user == teacher_user
        assert log.changes['kumush_delta'] == 80
        assert log.changes['kumush_awarded'] == 80

    def test_regrade_delta_creates_second_log_entry(self, teacher_a, submission):
        teacher_user, _, _ = teacher_a
        submission.grade(score=60, feedback='', graded_by=teacher_user)
        submission.grade(score=80, feedback='', graded_by=teacher_user)

        logs = ActivityLog.objects.filter(model_name='Submission', object_id=str(submission.pk)).order_by('created_at')
        assert [l.changes['kumush_delta'] for l in logs] == [60, 20]

    def test_same_score_regrade_creates_no_extra_log(self, teacher_a, submission):
        teacher_user, _, _ = teacher_a
        submission.grade(score=80, feedback='', graded_by=teacher_user)
        submission.grade(score=80, feedback='again', graded_by=teacher_user)

        assert ActivityLog.objects.filter(model_name='Submission', object_id=str(submission.pk)).count() == 1
