from rest_framework import serializers
from django.db.models import Count, Q
from .models import Group, LessonSchedule


class LessonScheduleSerializer(serializers.ModelSerializer):
    day_display = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model  = LessonSchedule
        fields = ['id', 'day_of_week', 'day_display']


class GroupListSerializer(serializers.ModelSerializer):
    teacher_name   = serializers.CharField(source='teacher.user.full_name', read_only=True, allow_null=True)
    branch_name    = serializers.CharField(source='branch.name', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    schedules      = LessonScheduleSerializer(many=True, read_only=True)
    student_count  = serializers.SerializerMethodField()
    days_of_week   = serializers.SerializerMethodField()
    course_name    = serializers.CharField(source='subject', read_only=True)

    class Meta:
        model  = Group
        fields = [
            'id', 'name', 'subject', 'course_name', 'description',
            'branch', 'branch_name',
            'teacher', 'teacher_name',
            'status', 'status_display',
            'student_count', 'max_students', 'monthly_fee',
            'start_date', 'end_date', 'start_time', 'end_time',
            'schedules', 'days_of_week',
        ]

    def get_student_count(self, obj):
        # Prefer annotated value (no extra query); fall back to property
        annotated = getattr(obj, '_student_count', None)
        if annotated is not None:
            return annotated
        return obj.students.filter(status='active').count()

    def get_days_of_week(self, obj):
        # Build from prefetched schedules — zero extra queries
        return sorted([s.day_of_week for s in obj.schedules.all()])


class GroupCreateSerializer(serializers.ModelSerializer):
    days       = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, default=list)
    start_date = serializers.DateField(required=False)

    class Meta:
        model  = Group
        fields = [
            'name', 'subject', 'description', 'branch', 'teacher', 'status',
            'max_students', 'monthly_fee',
            'start_date', 'end_date', 'start_time', 'end_time', 'days',
        ]

    def create(self, validated_data):
        from datetime import date
        validated_data.setdefault('start_date', date.today())
        days  = validated_data.pop('days', [])
        group = Group.objects.create(**validated_data)
        for day in days:
            LessonSchedule.objects.get_or_create(group=group, day_of_week=day)
        return group

    def update(self, instance, validated_data):
        days = validated_data.pop('days', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if days is not None:
            instance.schedules.all().delete()
            for day in days:
                LessonSchedule.objects.create(group=instance, day_of_week=day)
        return instance
