"""
ZUKKO submission → KUMUSH reward tests.

Business rule: every correct/partial ZUKKO submission earns KUMUSH via the
same ledger-backed Student.add_xp() primitive as XP (1:1 coupled, unchanged
reward amounts/scoring). The bugs being fixed here are financial/security
only: (1) sessionless ("practice") submissions used to bypass duplicate
checking entirely, allowing unlimited re-reward; (2) a race between the
app-level duplicate check and the DB write could double-create a row before
the DB constraint existed; (3) the 'submit' throttle scope was completely
unconfigured under some settings modules, crashing every submission with a
500. None of ZUKKO's challenge/scoring/retry logic changes.
"""
from unittest.mock import patch

import pytest
from django.db import connection
from rest_framework import status

from apps.notifications.models import ActivityLog
from apps.store.models import KumushTransaction
from apps.zukko.models import ChallengeSubmission
from apps.zukko.tests.conftest import auth_client

# The coding-challenge sandbox (apps/zukko/sandbox.py) shells out to a
# RestrictedPython-based runner to actually execute submitted code. That
# runner's correctness is unrelated to the KUMUSH/financial logic under
# test here, so coding-reward tests mock the test-case runner directly
# instead of depending on the sandbox's runtime environment.
_ALL_PASS = ([{'input': '', 'expected': 'ok', 'actual': 'ok', 'passed': True}], 1, 1)


@pytest.mark.django_db
class TestZukkoBugfindReward:

    def test_correct_bugfind_awards_reward_with_ledger(self, student_a, bugfind_challenge):
        student_user, student = student_a
        client = auth_client(student_user)

        resp = client.post('/api/v1/challenges/submit/', {
            'submission_type': 'bugfind',
            'challenge_id': str(bugfind_challenge.id),
            'identified_line': bugfind_challenge.bug_line_number,
            'submitted_code': bugfind_challenge.correct_code,
            'used_hint': False,
            'time_spent_seconds': 30,
        }, format='json')

        assert resp.status_code == status.HTTP_201_CREATED
        student.refresh_from_db()
        assert student.coins == bugfind_challenge.get_points()  # easy → 10*1

        submission = ChallengeSubmission.objects.get(user=student_user, bugfind_challenge=bugfind_challenge)
        txn = KumushTransaction.objects.get(student=student)
        assert txn.type == KumushTransaction.Type.EARN
        assert txn.amount == bugfind_challenge.get_points()
        assert txn.reason == 'ZUKKO BugFind reward'
        assert txn.source_type == 'zukko_bugfind'
        assert txn.source_id == str(submission.pk)
        assert txn.balance_before == 0
        assert txn.balance_after == bugfind_challenge.get_points()
        # No app user forged this — system-attributed, not falsely blamed on someone else.
        assert txn.created_by is None


@pytest.mark.django_db
class TestZukkoCodingReward:

    def test_correct_coding_awards_reward_with_ledger(self, student_a, coding_challenge):
        student_user, student = student_a
        client = auth_client(student_user)

        with patch('apps.zukko.views._run_test_cases', return_value=_ALL_PASS):
            resp = client.post('/api/v1/challenges/submit/', {
                'submission_type': 'coding',
                'challenge_id': str(coding_challenge.id),
                'code': "print('ok')",
                'time_spent_seconds': 30,
            }, format='json')

        assert resp.status_code == status.HTTP_201_CREATED
        student.refresh_from_db()
        assert student.coins == coding_challenge.points  # 20, fully passed

        submission = ChallengeSubmission.objects.get(user=student_user, coding_challenge=coding_challenge)
        txn = KumushTransaction.objects.get(student=student)
        assert txn.reason == 'ZUKKO Coding reward'
        assert txn.source_type == 'zukko_coding'
        assert txn.source_id == str(submission.pk)
        assert txn.amount == coding_challenge.points


@pytest.mark.django_db
class TestZukkoDuplicateProtection:

    def _submit_bugfind(self, client, challenge, session_id=None):
        payload = {
            'submission_type': 'bugfind',
            'challenge_id': str(challenge.id),
            'identified_line': challenge.bug_line_number,
            'submitted_code': challenge.correct_code,
            'used_hint': False,
            'time_spent_seconds': 10,
        }
        if session_id is not None:
            payload['session_id'] = str(session_id)
        return client.post('/api/v1/challenges/submit/', payload, format='json')

    def test_duplicate_within_session_blocked(self, student_a, bugfind_challenge, session_a):
        student_user, student = student_a
        client = auth_client(student_user)

        first = self._submit_bugfind(client, bugfind_challenge, session_id=session_a.id)
        second = self._submit_bugfind(client, bugfind_challenge, session_id=session_a.id)

        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_409_CONFLICT
        student.refresh_from_db()
        assert student.coins == bugfind_challenge.get_points()  # only once
        assert KumushTransaction.objects.filter(student=student).count() == 1

    def test_sessionless_duplicate_now_blocked(self, student_a, bugfind_challenge):
        """The confirmed bug: session_id omitted used to bypass duplicate
        checking entirely, allowing the same challenge to be resubmitted for
        reward without limit. This must now be blocked exactly like the
        with-session case."""
        student_user, student = student_a
        client = auth_client(student_user)

        first = self._submit_bugfind(client, bugfind_challenge)
        second = self._submit_bugfind(client, bugfind_challenge)
        third = self._submit_bugfind(client, bugfind_challenge)

        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_409_CONFLICT
        assert third.status_code == status.HTTP_409_CONFLICT
        student.refresh_from_db()
        assert student.coins == bugfind_challenge.get_points()
        assert KumushTransaction.objects.filter(student=student).count() == 1

    def test_legitimate_retry_on_different_challenge_still_works(
        self, student_a, bugfind_challenge, coding_challenge,
    ):
        """Fixing the duplicate bug must not block genuinely distinct
        submissions — a different challenge for the same student earns its
        own, separate reward."""
        student_user, student = student_a
        client = auth_client(student_user)

        bug_resp = self._submit_bugfind(client, bugfind_challenge)
        assert bug_resp.status_code == status.HTTP_201_CREATED

        with patch('apps.zukko.views._run_test_cases', return_value=_ALL_PASS):
            code_resp = client.post('/api/v1/challenges/submit/', {
                'submission_type': 'coding',
                'challenge_id': str(coding_challenge.id),
                'code': "print('ok')",
                'time_spent_seconds': 10,
            }, format='json')
        assert code_resp.status_code == status.HTTP_201_CREATED

        student.refresh_from_db()
        assert student.coins == bugfind_challenge.get_points() + coding_challenge.points
        assert KumushTransaction.objects.filter(student=student).count() == 2

    @pytest.mark.skipif(
        not connection.features.supports_nulls_distinct_unique_constraints,
        reason=(
            "This backend (e.g. SQLite, used by the pytest test runner) "
            "silently skips creating a nulls_distinct=False unique "
            "constraint (Django omits it rather than erroring — see "
            "django/db/backends/base/schema.py:_unique_supported). "
            "Production runs PostgreSQL 15+, which does support and "
            "enforce it — verified by successfully applying this "
            "migration against the live dev Postgres database."
        ),
    )
    def test_db_constraint_blocks_direct_duplicate_create(self, student_a, bugfind_challenge):
        """Defense-in-depth: even bypassing the view's app-level
        _check_duplicate() and writing directly via the ORM (simulating a
        genuine concurrent-request race), the DB-level unique constraint
        refuses a second (user, session=None, bugfind_challenge) row."""
        from django.db import IntegrityError, transaction

        student_user, _ = student_a
        ChallengeSubmission.objects.create(
            user=student_user, session=None, submission_type='bugfind',
            bugfind_challenge=bugfind_challenge, status=ChallengeSubmission.Status.CORRECT,
            points_earned=10,
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ChallengeSubmission.objects.create(
                    user=student_user, session=None, submission_type='bugfind',
                    bugfind_challenge=bugfind_challenge, status=ChallengeSubmission.Status.CORRECT,
                    points_earned=10,
                )
        assert ChallengeSubmission.objects.filter(
            user=student_user, session=None, bugfind_challenge=bugfind_challenge,
        ).count() == 1


@pytest.mark.django_db
class TestZukkoKumushAuditLog:

    def test_bugfind_reward_creates_activity_log(self, student_a, bugfind_challenge):
        student_user, _ = student_a
        client = auth_client(student_user)

        resp = client.post('/api/v1/challenges/submit/', {
            'submission_type': 'bugfind',
            'challenge_id': str(bugfind_challenge.id),
            'identified_line': bugfind_challenge.bug_line_number,
            'submitted_code': bugfind_challenge.correct_code,
            'used_hint': False,
            'time_spent_seconds': 10,
        }, format='json')
        submission = ChallengeSubmission.objects.get(user=student_user, bugfind_challenge=bugfind_challenge)

        log = ActivityLog.objects.get(model_name='ChallengeSubmission', object_id=str(submission.pk))
        assert log.user == student_user
        assert log.changes['kumush_awarded'] == bugfind_challenge.get_points()


@pytest.mark.django_db
class TestZukkoThrottleConfig:

    def test_submit_endpoint_does_not_500(self, student_a, bugfind_challenge):
        """Regression guard for the confirmed bug where the 'submit' DRF
        throttle scope was entirely unconfigured under some settings
        modules, raising ImproperlyConfigured (surfaced as a 500) on every
        single submission."""
        student_user, _ = student_a
        client = auth_client(student_user)

        resp = client.post('/api/v1/challenges/submit/', {
            'submission_type': 'bugfind',
            'challenge_id': str(bugfind_challenge.id),
            'identified_line': bugfind_challenge.bug_line_number,
            'submitted_code': bugfind_challenge.correct_code,
            'used_hint': False,
            'time_spent_seconds': 10,
        }, format='json')

        assert resp.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
        assert resp.status_code == status.HTTP_201_CREATED
