from rest_framework import serializers

from .models import Group, LessonSchedule, Room
from .rooms import assert_no_conflicts, resolve_room_name


class LessonScheduleSerializer(serializers.ModelSerializer):
    day_display  = serializers.CharField(source='get_day_of_week_display', read_only=True)
    group_name   = serializers.CharField(source='group.name', read_only=True)
    start_time   = serializers.TimeField(source='group.start_time', read_only=True)
    end_time     = serializers.TimeField(source='group.end_time', read_only=True)
    teacher_name = serializers.CharField(source='group.teacher.user.full_name', read_only=True, default=None)

    class Meta:
        model  = LessonSchedule
        fields = ['id', 'day_of_week', 'day_display', 'room',
                  'group_name', 'start_time', 'end_time', 'teacher_name']


class GroupListSerializer(serializers.ModelSerializer):
    teacher_name   = serializers.CharField(source='teacher.user.full_name', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    schedules      = LessonScheduleSerializer(many=True, read_only=True)
    student_count  = serializers.SerializerMethodField()
    days_of_week   = serializers.SerializerMethodField()
    course_name    = serializers.CharField(source='subject', read_only=True)

    class Meta:
        model  = Group
        fields = [
            'id', 'name', 'subject', 'course_name', 'description',
            'teacher', 'teacher_name',
            'status', 'status_display',
            'student_count', 'max_students',
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
    days       = serializers.ListField(child=serializers.IntegerField(min_value=1, max_value=7),
                                       write_only=True, required=False)
    # Guruh ochilayotganda tanlangan kunlar uchun xona (ro'yxatdan)
    room       = serializers.CharField(write_only=True, required=False, allow_blank=True)
    start_date = serializers.DateField(required=False)

    class Meta:
        model  = Group
        fields = [
            'id', 'name', 'subject', 'description', 'teacher', 'status',
            'max_students',
            'start_date', 'end_date', 'start_time', 'end_time', 'days', 'room',
        ]
        read_only_fields = ['id']

    def validate(self, data):
        from datetime import date

        room = resolve_room_name(data.get('room', ''))
        if 'room' in data:
            data['room'] = room
        # Saqlanadigan holat (yangi guruh yoki tahrirlangan) — band xonani tekshirish uchun
        state = Group(**{f: data.get(f, getattr(self.instance, f, None))
                         for f in ('start_time', 'end_time', 'start_date', 'end_date', 'status')})
        state.pk = getattr(self.instance, 'pk', None)
        state.start_date = state.start_date or date.today()
        state.status = state.status or Group.Status.ACTIVE
        if state.start_time and state.end_time and state.start_time >= state.end_time:
            raise serializers.ValidationError({'end_time': ["Tugash vaqti boshlanishdan keyin bo'lishi kerak."]})
        assert_no_conflicts(state, self._day_room_pairs(data, room))
        return data

    def _day_room_pairs(self, data, room):
        existing = ({s.day_of_week: s.room for s in self.instance.schedules.all()}
                    if self.instance else {})
        if 'days' in data:
            return [(d, room or existing.get(d, '')) for d in data['days']]
        return list(existing.items())

    def create(self, validated_data):
        from datetime import date
        validated_data.setdefault('start_date', date.today())
        days  = validated_data.pop('days', [])
        room  = validated_data.pop('room', '')
        group = Group.objects.create(**validated_data)
        for day in days:
            LessonSchedule.objects.get_or_create(group=group, day_of_week=day, defaults={'room': room})
        return group

    def update(self, instance, validated_data):
        days = validated_data.pop('days', None)
        room = validated_data.pop('room', '')
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if days is not None:
            # Kunlar qayta yozilsa ham xonalar saqlanib qoladi (oldin yo'qolardi)
            old_rooms = {s.day_of_week: s.room for s in instance.schedules.all()}
            instance.schedules.all().delete()
            for day in days:
                LessonSchedule.objects.create(group=instance, day_of_week=day,
                                              room=room or old_rooms.get(day, ''))
        return instance


class RoomSerializer(serializers.ModelSerializer):
    # Xona qaysi guruhlarga, qaysi kun va soatda band
    usages = serializers.SerializerMethodField()

    class Meta:
        model  = Room
        fields = ['id', 'name', 'capacity', 'is_active', 'usages']
        read_only_fields = ['id']

    def validate_name(self, value):
        value = value.strip()
        clash = Room.objects.filter(name__iexact=value)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("Bunday nomli xona allaqachon bor.")
        return value

    def get_usages(self, obj):
        rows = (LessonSchedule.objects.filter(room__iexact=obj.name, group__status=Group.Status.ACTIVE)
                .select_related('group').order_by('day_of_week', 'group__start_time'))
        return [{'day_of_week': s.day_of_week, 'day_display': s.get_day_of_week_display(),
                 'group_id': str(s.group_id), 'group_name': s.group.name,
                 'start_time': s.group.start_time, 'end_time': s.group.end_time} for s in rows]
