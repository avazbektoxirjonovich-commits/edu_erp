from rest_framework import serializers
from django.utils import timezone
from .models import Assignment, Submission


class AssignmentListSerializer(serializers.ModelSerializer):
    group_name       = serializers.CharField(source='group.name', read_only=True)
    teacher_name     = serializers.CharField(source='teacher.user.full_name', read_only=True, allow_null=True)
    status_display   = serializers.CharField(source='get_status_display', read_only=True)
    is_overdue       = serializers.BooleanField(read_only=True)
    submission_count = serializers.SerializerMethodField()
    graded_count     = serializers.SerializerMethodField()

    class Meta:
        model  = Assignment
        fields = [
            'id', 'title', 'group', 'group_name', 'teacher_name',
            'assigned_date', 'lesson_date', 'due_date',
            'max_score', 'xp_reward', 'status', 'status_display',
            'submission_count', 'graded_count', 'is_overdue', 'created_at',
        ]

    def get_submission_count(self, obj):
        # Use annotated value if available (set by view), else fallback
        v = getattr(obj, '_submission_count', None)
        return v if v is not None else obj.submissions.count()

    def get_graded_count(self, obj):
        v = getattr(obj, '_graded_count', None)
        return v if v is not None else obj.submissions.filter(status=Submission.Status.GRADED).count()


class AssignmentDetailSerializer(serializers.ModelSerializer):
    group_name        = serializers.CharField(source='group.name', read_only=True)
    teacher_name      = serializers.CharField(source='teacher.user.full_name', read_only=True)
    status_display    = serializers.CharField(source='get_status_display', read_only=True)
    is_overdue        = serializers.BooleanField(read_only=True)
    submission_count  = serializers.IntegerField(read_only=True)
    graded_count      = serializers.IntegerField(read_only=True)
    submissions       = serializers.SerializerMethodField()

    class Meta:
        model  = Assignment
        fields = [
            'id', 'title', 'description', 'group', 'group_name',
            'teacher', 'teacher_name', 'due_date', 'max_score', 'xp_reward',
            'status', 'status_display', 'file', 'is_overdue',
            'submission_count', 'graded_count', 'submissions',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_submissions(self, obj):
        from .models import Submission
        subs = Submission.objects.filter(assignment=obj).select_related('student__user', 'graded_by')
        return SubmissionSerializer(subs, many=True).data


class AssignmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Assignment
        fields = [
            'title', 'description', 'group',
            'assigned_date', 'lesson_date', 'due_date',
            'max_score', 'xp_reward', 'status', 'file',
        ]

    def create(self, validated_data):
        request = self.context.get('request')
        # Teacher bo'lsa auto-assign; Admin bo'lsa teacher=None (intentional)
        teacher = getattr(request.user, 'teacher_profile', None) if request else None
        return Assignment.objects.create(teacher=teacher, **validated_data)


class SubmissionSerializer(serializers.ModelSerializer):
    student_name      = serializers.CharField(source='student.user.full_name', read_only=True)
    assignment_title  = serializers.CharField(source='assignment.title', read_only=True)
    max_score         = serializers.IntegerField(source='assignment.max_score', read_only=True)
    status_display    = serializers.CharField(source='get_status_display', read_only=True)
    score_percentage  = serializers.FloatField(read_only=True)
    graded_by_name    = serializers.CharField(source='graded_by.full_name', read_only=True, allow_null=True, default=None)

    class Meta:
        model  = Submission
        fields = [
            'id', 'assignment', 'assignment_title', 'student', 'student_name',
            'answer', 'file', 'score', 'max_score', 'score_percentage',
            'feedback', 'status', 'status_display',
            'submitted_at', 'graded_at', 'graded_by_name',
        ]
        read_only_fields = ['id', 'submitted_at', 'graded_at', 'graded_by_name']


class SubmissionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Submission
        fields = ['assignment', 'answer', 'file']

    def validate_assignment(self, value):
        if value.status != Assignment.Status.ACTIVE:
            raise serializers.ValidationError("Bu vazifa faol emas.")
        return value

    def validate(self, data):
        request = self.context.get('request')
        student = getattr(request.user, 'student_profile', None) if request else None
        if student and Submission.objects.filter(
            assignment=data['assignment'], student=student
        ).exists():
            raise serializers.ValidationError("Siz bu vazifani allaqachon topshirgansiz.")
        return data

    def create(self, validated_data):
        from rest_framework.exceptions import PermissionDenied
        request    = self.context['request']
        student    = getattr(request.user, 'student_profile', None)
        if student is None:
            raise PermissionDenied("Faqat o'quvchilar vazifa topshira oladi.")
        assignment = validated_data['assignment']

        is_late = bool(assignment.due_date) and timezone.now().date() > assignment.due_date
        status  = Submission.Status.LATE if is_late else Submission.Status.SUBMITTED

        return Submission.objects.create(
            student=student, status=status, **validated_data
        )


class GradeSubmissionSerializer(serializers.Serializer):
    score    = serializers.IntegerField(min_value=0)
    feedback = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_score(self, value):
        submission = self.context['submission']
        if value > submission.assignment.max_score:
            raise serializers.ValidationError(
                f"Ball {submission.assignment.max_score} dan oshmasligi kerak."
            )
        return value
