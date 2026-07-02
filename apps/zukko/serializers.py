from rest_framework import serializers

from .models import (
    AntiCheatEvent,
    BugFindChallenge,
    ChallengeCategory,
    ChallengeSession,
    ChallengeSubmission,
    CodingChallenge,
    StudentProgress,
)


def _is_teacher(request):
    user = request.user if request else None
    if not (user and user.is_authenticated):
        return False
    return user.role == 'teacher' or user.is_staff_level


class ChallengeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChallengeCategory
        fields = ['id', 'name', 'slug', 'description', 'created_by', 'created_at']
        read_only_fields = ['created_by', 'created_at']


# ---------- BugFindChallenge ----------

class BugFindDetailSerializer(serializers.ModelSerializer):
    """Talaba uchun — correct_code, bug_line_number, bug_explanation YASHIRIN."""

    class Meta:
        model = BugFindChallenge
        fields = [
            'id', 'title', 'description', 'category', 'buggy_code',
            'difficulty', 'bug_type', 'programming_language',
            'time_limit_seconds', 'points', 'hint',
        ]


class BugFindTeacherSerializer(serializers.ModelSerializer):
    """O'qituvchi uchun — to'liq."""

    class Meta:
        model = BugFindChallenge
        fields = [
            'id', 'title', 'description', 'category', 'buggy_code', 'correct_code',
            'bug_line_number', 'bug_explanation', 'difficulty', 'bug_type',
            'programming_language', 'time_limit_seconds', 'points', 'hint',
            'created_by', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


# ---------- CodingChallenge ----------

class CodingDetailSerializer(serializers.ModelSerializer):
    """Talaba uchun — solution_code va hidden_test_cases YASHIRIN."""

    class Meta:
        model = CodingChallenge
        fields = [
            'id', 'title', 'description', 'category', 'constraints',
            'input_format', 'output_format', 'sample_input', 'sample_output',
            'sample_explanation', 'starter_code', 'difficulty',
            'programming_language', 'time_limit_seconds', 'memory_limit_mb', 'points',
        ]


class CodingTeacherSerializer(serializers.ModelSerializer):
    """O'qituvchi uchun — to'liq."""

    class Meta:
        model = CodingChallenge
        fields = [
            'id', 'title', 'description', 'category', 'constraints',
            'input_format', 'output_format', 'sample_input', 'sample_output',
            'sample_explanation', 'hidden_test_cases', 'starter_code', 'solution_code',
            'difficulty', 'programming_language', 'time_limit_seconds', 'memory_limit_mb',
            'points', 'created_by', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


# ---------- ChallengeSession ----------

class ChallengeSessionSerializer(serializers.ModelSerializer):
    submissions_count = serializers.SerializerMethodField()

    class Meta:
        model = ChallengeSession
        fields = [
            'id', 'title', 'session_type', 'status', 'group',
            'bugfind_pool', 'coding_pool', 'bugfind_count', 'coding_count',
            'time_limit_minutes', 'starts_at', 'ends_at',
            'anti_paste_enabled', 'tab_switch_limit', 'shuffle_questions',
            'share_link', 'submissions_count', 'created_by', 'created_at',
        ]
        read_only_fields = ['share_link', 'created_by', 'created_at']

    def get_submissions_count(self, obj):
        return obj.submissions.count()


# ---------- ChallengeSubmission ----------

class ChallengeSubmissionSerializer(serializers.ModelSerializer):
    bugfind_explanation = serializers.SerializerMethodField()

    class Meta:
        model = ChallengeSubmission
        fields = '__all__'
        read_only_fields = [f.name for f in ChallengeSubmission._meta.fields]

    def get_bugfind_explanation(self, obj):
        if obj.status == ChallengeSubmission.Status.PENDING or not obj.bugfind_challenge:
            return None
        return obj.bugfind_challenge.bug_explanation


class SubmitBugFindSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    session_id = serializers.UUIDField(required=False, allow_null=True)
    identified_line = serializers.IntegerField(min_value=1)
    submitted_code = serializers.CharField(required=False, allow_blank=True, default='')
    used_hint = serializers.BooleanField(default=False)
    time_spent_seconds = serializers.IntegerField(min_value=0)


class SubmitCodingSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    session_id = serializers.UUIDField(required=False, allow_null=True)
    code = serializers.CharField(allow_blank=False)
    time_spent_seconds = serializers.IntegerField(min_value=0)
    keystroke_log = serializers.ListField(child=serializers.DictField(), required=False, default=list)


# ---------- AntiCheat ----------

class AntiCheatEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AntiCheatEvent
        fields = ['id', 'submission', 'event_type', 'severity', 'details', 'timestamp']
        read_only_fields = ['id', 'timestamp']


# ---------- StudentProgress ----------

class StudentProgressSerializer(serializers.ModelSerializer):
    total_solved = serializers.SerializerMethodField()

    class Meta:
        model = StudentProgress
        fields = [
            'id', 'category', 'total_attempts', 'correct_count',
            'wrong_count', 'partial_count', 'easy_solved', 'medium_solved',
            'hard_solved', 'total_solved', 'total_time_seconds', 'avg_time_seconds',
            'fastest_solve_seconds', 'total_points', 'total_xp', 'mastery_percentage',
            'daily_stats', 'error_breakdown', 'last_activity',
        ]

    def get_total_solved(self, obj):
        return obj.total_solved()


class MonthlyReportSerializer(serializers.Serializer):
    """Oylik hisobot uchun to'liq agregatlangan ma'lumot."""
    user_id = serializers.UUIDField()
    full_name = serializers.CharField()
    month = serializers.CharField()
    total_attempts = serializers.IntegerField()
    correct_count = serializers.IntegerField()
    wrong_count = serializers.IntegerField()
    partial_count = serializers.IntegerField()
    total_points = serializers.IntegerField()
    total_xp = serializers.IntegerField()
    mastery_percentage = serializers.FloatField()
    easy_solved = serializers.IntegerField()
    medium_solved = serializers.IntegerField()
    hard_solved = serializers.IntegerField()
    daily_stats = serializers.DictField()
    error_breakdown = serializers.DictField()
    suspicion_events = serializers.IntegerField()
