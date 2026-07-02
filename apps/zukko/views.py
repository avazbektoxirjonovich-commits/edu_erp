import math
import random
from collections import defaultdict
from datetime import datetime, timezone as dt_timezone
from difflib import SequenceMatcher

from django.contrib.auth import get_user_model
from django.db.models import Avg
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .models import (
    AntiCheatEvent,
    BugFindChallenge,
    ChallengeCategory,
    ChallengeSession,
    ChallengeSubmission,
    CodingChallenge,
    StudentProgress,
)
from .permissions import IsTeacherOrAssistant, IsTeacherOrReadOnly
from .sandbox import execute_student_code
from .serializers import (
    AntiCheatEventSerializer,
    BugFindDetailSerializer,
    BugFindTeacherSerializer,
    ChallengeCategorySerializer,
    ChallengeSessionSerializer,
    ChallengeSubmissionSerializer,
    CodingDetailSerializer,
    CodingTeacherSerializer,
    MonthlyReportSerializer,
    StudentProgressSerializer,
    SubmitBugFindSerializer,
    SubmitCodingSerializer,
)


def _is_teacher(request):
    user = request.user
    return bool(user.is_authenticated and (user.role == 'teacher' or user.is_staff_level))


def _student_group(user):
    """ERP'da talaba guruhi User.student_profile.group orqali olinadi."""
    profile = getattr(user, 'student_profile', None)
    return profile.group if profile else None


def _add_xp(user, points):
    """ERP'da XP students.Student.add_xp() orqali boshqariladi (User'da xp maydoni yo'q)."""
    if not points:
        return
    profile = getattr(user, 'student_profile', None)
    if profile:
        profile.add_xp(points, reason='ZUKKO Challenge')


def _student_xp(user):
    profile = getattr(user, 'student_profile', None)
    return profile.xp_points if profile else 0


def _run_test_cases(code, test_cases, time_limit_seconds, language='python'):
    """Talaba kodini har bir yashirin test case bilan sandbox orqali ishga tushiradi."""
    results = []
    passed = 0
    timeout = max(1, min(time_limit_seconds, 30))
    for tc in test_cases:
        inp = tc.get('input', '')
        expected = str(tc.get('expected_output', '')).strip()
        output = execute_student_code(code, inp, timeout=timeout, language=language)
        actual = output.strip()
        ok = not actual.startswith('XATO:') and actual == expected
        results.append({'input': inp, 'expected': expected, 'actual': actual, 'passed': ok})
        if ok:
            passed += 1
    return results, passed, len(test_cases)


# ---------- ViewSets ----------

class ChallengeCategoryViewSet(viewsets.ModelViewSet):
    queryset = ChallengeCategory.objects.all()
    serializer_class = ChallengeCategorySerializer
    permission_classes = [IsTeacherOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class BugFindChallengeViewSet(viewsets.ModelViewSet):
    queryset = BugFindChallenge.objects.filter(is_active=True)
    permission_classes = [IsTeacherOrReadOnly]

    def get_serializer_class(self):
        if _is_teacher(self.request):
            return BugFindTeacherSerializer
        return BugFindDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CodingChallengeViewSet(viewsets.ModelViewSet):
    queryset = CodingChallenge.objects.filter(is_active=True)
    permission_classes = [IsTeacherOrReadOnly]

    def get_serializer_class(self):
        if _is_teacher(self.request):
            return CodingTeacherSerializer
        return CodingDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ChallengeSessionViewSet(viewsets.ModelViewSet):
    serializer_class = ChallengeSessionSerializer
    permission_classes = [IsTeacherOrAssistant]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff_level:
            return ChallengeSession.objects.all()
        return ChallengeSession.objects.filter(group__teacher__user=user)

    def perform_create(self, serializer):
        session = serializer.save(created_by=self.request.user)
        session.bugfind_pool.set(BugFindChallenge.objects.filter(is_active=True))
        session.coding_pool.set(CodingChallenge.objects.filter(is_active=True))

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        session = self.get_object()
        session.status = ChallengeSession.Status.ACTIVE
        session.save(update_fields=['status'])
        return Response(ChallengeSessionSerializer(session).data)

    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        session = self.get_object()
        submissions = session.submissions.select_related('user', 'bugfind_challenge', 'coding_challenge')
        grouped = defaultdict(list)
        for sub in submissions:
            grouped[sub.user.full_name].append(ChallengeSubmissionSerializer(sub).data)
        return Response(grouped)


# ---------- Sessiyaga kirish ----------

class StartSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, share_link):
        try:
            session = ChallengeSession.objects.get(
                share_link=share_link, status=ChallengeSession.Status.ACTIVE
            )
        except ChallengeSession.DoesNotExist:
            return Response({'detail': 'Sessiya topilmadi yoki aktiv emas'}, status=status.HTTP_404_NOT_FOUND)

        now = datetime.now(tz=dt_timezone.utc)
        if session.starts_at and now < session.starts_at:
            return Response({'detail': 'Sessiya hali boshlanmagan'}, status=status.HTTP_403_FORBIDDEN)
        if session.ends_at and now > session.ends_at:
            return Response({'detail': 'Sessiya muddati tugagan'}, status=status.HTTP_403_FORBIDDEN)

        if ChallengeSubmission.objects.filter(session=session, user=request.user).exists():
            return Response(
                {'detail': 'Siz bu sessiyada allaqachon qatnashgansiz'}, status=status.HTTP_403_FORBIDDEN
            )

        bugfind, coding = session.get_random_challenges()
        if session.shuffle_questions:
            random.shuffle(bugfind)
            random.shuffle(coding)

        return Response({
            'session_id': session.id,
            'title': session.title,
            'session_type': session.session_type,
            'time_limit_minutes': session.time_limit_minutes,
            'anti_paste_enabled': session.anti_paste_enabled,
            'tab_switch_limit': session.tab_switch_limit,
            'bugfind_challenges': BugFindDetailSerializer(bugfind, many=True).data,
            'coding_challenges': CodingDetailSerializer(coding, many=True).data,
        })


# ---------- Javob yuborish ----------

class SubmitRateThrottle(UserRateThrottle):
    scope = 'submit'


class SubmitChallengeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [SubmitRateThrottle]

    def post(self, request):
        submission_type = request.data.get('submission_type')
        if submission_type == 'bugfind':
            return self._submit_bugfind(request)
        if submission_type == 'coding':
            return self._submit_coding(request)
        return Response(
            {'detail': "submission_type 'bugfind' yoki 'coding' bo'lishi kerak"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def _check_session_timing(self, user, session):
        """Server-side vaqt tekshirish — klient timeri o'chirilsa ham vaqtdan oshib ketib bo'lmaydi."""
        if not session:
            return None
        first_sub = ChallengeSubmission.objects.filter(
            user=user, session=session
        ).order_by('started_at').first()
        if not first_sub:
            return None
        elapsed = (timezone.now() - first_sub.started_at).total_seconds()
        max_allowed = session.time_limit_minutes * 60 + 60
        if elapsed > max_allowed:
            return Response(
                {'error': 'Vaqt tugagan — server tomondan tekshirildi'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    def _check_duplicate(self, user, session, *, bugfind_challenge=None, coding_challenge=None):
        if not session:
            return None
        qs = ChallengeSubmission.objects.filter(user=user, session=session)
        if bugfind_challenge is not None:
            qs = qs.filter(bugfind_challenge=bugfind_challenge)
        else:
            qs = qs.filter(coding_challenge=coding_challenge)
        if qs.exists():
            return Response(
                {'error': 'Bu savolga allaqachon javob yuborgansiz'},
                status=status.HTTP_409_CONFLICT,
            )
        return None

    def _submit_bugfind(self, request):
        ser = SubmitBugFindSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        challenge = get_object_or_404(BugFindChallenge, pk=data['challenge_id'])
        session = None
        if data.get('session_id'):
            session = get_object_or_404(ChallengeSession, pk=data['session_id'])

        timing_error = self._check_session_timing(request.user, session)
        if timing_error:
            return timing_error
        duplicate_error = self._check_duplicate(request.user, session, bugfind_challenge=challenge)
        if duplicate_error:
            return duplicate_error

        line_correct = data['identified_line'] == challenge.bug_line_number
        code_ratio = 0.0
        if data['submitted_code']:
            code_ratio = SequenceMatcher(None, data['submitted_code'], challenge.correct_code).ratio()
        code_correct = code_ratio > 0.85

        if line_correct and code_correct:
            sub_status = ChallengeSubmission.Status.CORRECT
            points = challenge.get_points()
        elif line_correct or code_correct:
            sub_status = ChallengeSubmission.Status.PARTIAL
            points = challenge.get_points() // 2
        else:
            sub_status = ChallengeSubmission.Status.WRONG
            points = 0

        if data['used_hint'] and points > 0:
            points = max(0, points - 2)

        ip = self._get_client_ip(request)
        submission = ChallengeSubmission.objects.create(
            user=request.user, session=session, submission_type='bugfind',
            bugfind_challenge=challenge, submitted_code=data['submitted_code'],
            identified_line=data['identified_line'], status=sub_status,
            points_earned=points, submitted_at=datetime.now(tz=dt_timezone.utc),
            time_spent_seconds=data['time_spent_seconds'], ip_address=ip,
        )
        self._update_progress(
            request.user, challenge.difficulty, sub_status, points,
            challenge.bug_type, data['time_spent_seconds'], category=challenge.category,
        )
        self._flag_shared_ip(request.user, session, ip)
        self._flag_rapid_typing(request.user, session, data['submitted_code'], data['time_spent_seconds'])
        self._attach_suspicion(submission, data.get('session_id'))

        return Response({
            'submission': ChallengeSubmissionSerializer(submission).data,
            'correct_line': challenge.bug_line_number,
            'bug_explanation': challenge.bug_explanation,
            'points_earned': points,
        }, status=status.HTTP_201_CREATED)

    def _submit_coding(self, request):
        ser = SubmitCodingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        challenge = get_object_or_404(CodingChallenge, pk=data['challenge_id'])
        session = None
        if data.get('session_id'):
            session = get_object_or_404(ChallengeSession, pk=data['session_id'])

        timing_error = self._check_session_timing(request.user, session)
        if timing_error:
            return timing_error
        duplicate_error = self._check_duplicate(request.user, session, coding_challenge=challenge)
        if duplicate_error:
            return duplicate_error

        test_results, passed_count, total_count = _run_test_cases(
            data['code'], challenge.hidden_test_cases, challenge.time_limit_seconds,
            language=challenge.programming_language,
        )

        if total_count == 0 or passed_count == 0:
            sub_status = ChallengeSubmission.Status.WRONG
            points = 0
        elif passed_count == total_count:
            sub_status = ChallengeSubmission.Status.CORRECT
            points = challenge.points
        else:
            sub_status = ChallengeSubmission.Status.PARTIAL
            points = round(challenge.points * passed_count / total_count)

        ip = self._get_client_ip(request)
        submission = ChallengeSubmission.objects.create(
            user=request.user, session=session, submission_type='coding',
            coding_challenge=challenge, submitted_code=data['code'],
            status=sub_status, points_earned=points, test_results={'cases': test_results},
            submitted_at=datetime.now(tz=dt_timezone.utc),
            time_spent_seconds=data['time_spent_seconds'],
            keystroke_log=data.get('keystroke_log', []), ip_address=ip,
        )
        self._update_progress(
            request.user, challenge.difficulty, sub_status, points,
            None, data['time_spent_seconds'], category=challenge.category,
        )
        self._flag_shared_ip(request.user, session, ip)
        self._flag_rapid_typing(request.user, session, data['code'], data['time_spent_seconds'])
        if session:
            self._flag_auto_similarity(request.user, session, challenge, data['code'])
        self._attach_suspicion(submission, data.get('session_id'))

        return Response({
            'submission': ChallengeSubmissionSerializer(submission).data,
            'test_results': test_results,
            'passed': passed_count,
            'total': total_count,
            'points_earned': points,
        }, status=status.HTTP_201_CREATED)

    def _update_progress(self, user, difficulty, sub_status, points, bug_type, time_spent, category=None):
        progress, _ = StudentProgress.objects.get_or_create(user=user, category=category)
        progress.total_attempts += 1

        if sub_status == ChallengeSubmission.Status.CORRECT:
            progress.correct_count += 1
            if difficulty == 'easy':
                progress.easy_solved += 1
            elif difficulty == 'medium':
                progress.medium_solved += 1
            elif difficulty == 'hard':
                progress.hard_solved += 1
            if progress.fastest_solve_seconds == 0 or time_spent < progress.fastest_solve_seconds:
                progress.fastest_solve_seconds = time_spent
        elif sub_status == ChallengeSubmission.Status.PARTIAL:
            progress.partial_count += 1
        else:
            progress.wrong_count += 1
            if bug_type:
                progress.error_breakdown[bug_type] = progress.error_breakdown.get(bug_type, 0) + 1

        progress.total_time_seconds += time_spent
        progress.avg_time_seconds = progress.total_time_seconds // progress.total_attempts
        progress.total_points += points
        progress.total_xp += points

        today = datetime.now(tz=dt_timezone.utc).strftime('%Y-%m-%d')
        day_stats = progress.daily_stats.get(today, {'attempts': 0, 'correct': 0})
        day_stats['attempts'] += 1
        if sub_status == ChallengeSubmission.Status.CORRECT:
            day_stats['correct'] += 1
        progress.daily_stats[today] = day_stats

        progress.update_mastery()
        progress.save()

        _add_xp(user, points)

    def _attach_suspicion(self, submission, session_id):
        """Sessiya davomida to'plangan anti-cheat hodisalar asosida sigmoid shubha balli."""
        events = list(AntiCheatEvent.objects.filter(user=submission.user, submission__isnull=True))
        if session_id:
            events = [e for e in events if str(e.details.get('session_id', '')) == str(session_id)]

        if events:
            AntiCheatEvent.objects.filter(id__in=[e.id for e in events]).update(submission=submission)
        self._recalculate_submission_suspicion(submission)

    @staticmethod
    def _recalculate_submission_suspicion(submission):
        total_severity = sum(e.severity for e in submission.anticheat_events.all())
        score = round(1 / (1 + math.exp(-(total_severity - 3))), 3)

        submission.suspicion_score = score
        if score >= 0.7 and submission.status == ChallengeSubmission.Status.CORRECT:
            submission.status = ChallengeSubmission.Status.CHEATING
        submission.save(update_fields=['suspicion_score', 'status'])

    @staticmethod
    def _get_client_ip(request):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    @staticmethod
    def _flag_shared_ip(user, session, ip):
        if not session or not ip:
            return
        shared = ChallengeSubmission.objects.filter(
            session=session, ip_address=ip
        ).exclude(user=user).exists()
        if shared:
            AntiCheatEvent.objects.create(
                user=user, event_type=AntiCheatEvent.EventType.IP_SHARED, severity=0.3,
                details={'ip': ip, 'session_id': str(session.id)},
            )

    @staticmethod
    def _flag_rapid_typing(user, session, code, time_spent_seconds):
        if not code or time_spent_seconds <= 0:
            return
        lines = code.count('\n') + 1
        chars_per_second = len(code) / time_spent_seconds
        is_suspicious = (lines >= 200 and time_spent_seconds <= 30) or (
            len(code) >= 300 and chars_per_second > 15
        )
        if is_suspicious:
            details = {'lines': lines, 'seconds': time_spent_seconds, 'chars_per_second': round(chars_per_second, 1)}
            if session:
                details['session_id'] = str(session.id)
            AntiCheatEvent.objects.create(
                user=user, event_type=AntiCheatEvent.EventType.RAPID_TYPE, severity=0.5, details=details,
            )

    def _flag_auto_similarity(self, user, session, challenge, code):
        if not code:
            return
        others = ChallengeSubmission.objects.filter(
            session=session, submission_type='coding', coding_challenge=challenge,
        ).exclude(user=user).exclude(submitted_code='')

        for other in others:
            ratio = SequenceMatcher(None, code, other.submitted_code).ratio()
            if ratio < 0.85:
                continue
            details = {
                'session_id': str(session.id), 'challenge_id': str(challenge.id),
                'similarity': round(ratio, 3), 'other_user': other.user.full_name,
            }
            AntiCheatEvent.objects.create(
                user=user, event_type=AntiCheatEvent.EventType.SIMILARITY, severity=0.5, details=details,
            )
            AntiCheatEvent.objects.create(
                user=other.user, submission=other, event_type=AntiCheatEvent.EventType.SIMILARITY,
                severity=0.5, details={**details, 'other_user': user.full_name},
            )
            self._recalculate_submission_suspicion(other)


# ---------- Anti-cheat log ----------

class AntiCheatLogView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        events_data = request.data if isinstance(request.data, list) else request.data.get('events', [])
        created = [
            AntiCheatEvent.objects.create(
                user=request.user,
                event_type=ev.get('event_type'),
                severity=ev.get('severity', 0.1),
                details=ev.get('details', {}),
            )
            for ev in events_data
        ]
        return Response(AntiCheatEventSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


# ---------- Progress / hisobotlar ----------

class StudentProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        progress = StudentProgress.objects.filter(user=request.user)
        return Response(StudentProgressSerializer(progress, many=True).data)


class MonthlyReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        if str(request.user.id) != str(user_id) and not _is_teacher(request):
            return Response({'detail': "Ruxsat yo'q"}, status=status.HTTP_403_FORBIDDEN)

        User = get_user_model()
        user = get_object_or_404(User, pk=user_id)
        month = request.query_params.get('month') or datetime.now(tz=dt_timezone.utc).strftime('%Y-%m')
        year_str, month_str = month.split('-')

        submissions = ChallengeSubmission.objects.filter(
            user=user, submitted_at__year=int(year_str), submitted_at__month=int(month_str),
        )
        progresses = StudentProgress.objects.filter(user=user)

        daily_stats, error_breakdown = {}, {}
        easy_solved = medium_solved = hard_solved = 0
        for p in progresses:
            for day, stat in p.daily_stats.items():
                if day.startswith(month):
                    agg = daily_stats.setdefault(day, {'attempts': 0, 'correct': 0})
                    agg['attempts'] += stat.get('attempts', 0)
                    agg['correct'] += stat.get('correct', 0)
            for etype, cnt in p.error_breakdown.items():
                error_breakdown[etype] = error_breakdown.get(etype, 0) + cnt
            easy_solved += p.easy_solved
            medium_solved += p.medium_solved
            hard_solved += p.hard_solved

        mastery_avg = progresses.aggregate(avg=Avg('mastery_percentage'))['avg'] or 0.0
        suspicion_events = AntiCheatEvent.objects.filter(
            user=user, timestamp__year=int(year_str), timestamp__month=int(month_str), severity__gte=0.3,
        ).count()

        data = {
            'user_id': user.id, 'full_name': user.full_name, 'month': month,
            'total_attempts': submissions.count(),
            'correct_count': submissions.filter(status=ChallengeSubmission.Status.CORRECT).count(),
            'wrong_count': submissions.filter(status=ChallengeSubmission.Status.WRONG).count(),
            'partial_count': submissions.filter(status=ChallengeSubmission.Status.PARTIAL).count(),
            'total_points': sum(s.points_earned for s in submissions),
            'total_xp': _student_xp(user),
            'mastery_percentage': round(mastery_avg, 1),
            'easy_solved': easy_solved, 'medium_solved': medium_solved, 'hard_solved': hard_solved,
            'daily_stats': daily_stats, 'error_breakdown': error_breakdown,
            'suspicion_events': suspicion_events,
        }
        return Response(MonthlyReportSerializer(data).data)


class AvailableSessionsView(APIView):
    """O'quvchi o'z guruhidagi aktiv sessiyalarni ko'radi."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        group = _student_group(user)
        if not group:
            return Response([])

        sessions = ChallengeSession.objects.filter(
            group=group, status=ChallengeSession.Status.ACTIVE,
        ).order_by('-created_at')

        data = []
        for session in sessions:
            has_submitted = ChallengeSubmission.objects.filter(user=user, session=session).exists()
            data.append({
                'id': str(session.id),
                'title': session.title,
                'session_type': session.session_type,
                'time_limit_minutes': session.time_limit_minutes,
                'share_link': session.share_link,
                'created_at': session.created_at.isoformat(),
                'already_submitted': has_submitted,
                'challenges_count': session.bugfind_pool.count() + session.coding_pool.count(),
            })

        return Response(data)


class SimilarityCheckView(APIView):
    """Sessiya ichidagi coding javoblarini juftma-juft solishtirib plagiat ehtimolini topadi."""
    permission_classes = [IsTeacherOrAssistant]

    def get(self, request, session_id):
        submissions = list(
            ChallengeSubmission.objects.filter(session_id=session_id, submission_type='coding')
            .exclude(submitted_code='')
            .select_related('user', 'coding_challenge')
        )

        flagged = []
        for i in range(len(submissions)):
            for j in range(i + 1, len(submissions)):
                a, b = submissions[i], submissions[j]
                if a.coding_challenge_id != b.coding_challenge_id:
                    continue
                ratio = SequenceMatcher(None, a.submitted_code, b.submitted_code).ratio()
                if ratio >= 0.7:
                    flagged.append({
                        'challenge_id': str(a.coding_challenge_id),
                        'challenge_title': a.coding_challenge.title if a.coding_challenge else '',
                        'user_a': a.user.full_name,
                        'user_b': b.user.full_name,
                        'similarity': round(ratio, 3),
                    })

        return Response({'checked_submissions': len(submissions), 'flagged_pairs': flagged})
