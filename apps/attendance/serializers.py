from rest_framework import serializers
from .models import Attendance


class AttendanceSerializer(serializers.ModelSerializer):
    student_name   = serializers.CharField(source='student.user.full_name', read_only=True)
    group_name     = serializers.CharField(source='group.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model  = Attendance
        fields = ['id', 'student', 'student_name', 'group', 'group_name',
                  'date', 'status', 'status_display', 'note', 'created_at']
        read_only_fields = ['id', 'created_at']


class BulkRecordSerializer(serializers.Serializer):
    """records[] ichidagi har bir satr uchun — faqat student UUID va status kerak."""
    student = serializers.UUIDField()
    status  = serializers.ChoiceField(choices=Attendance.Status.choices)
    note    = serializers.CharField(required=False, allow_blank=True, default='')


class BulkAttendanceSerializer(serializers.Serializer):
    """
    Bir kunda guruhning barcha o'quvchilari uchun davomat belgilash.
    Body: {
        "group": "uuid",
        "date": "2025-05-14",
        "records": [
            {"student": "uuid", "status": "present"},
            {"student": "uuid", "status": "absent"}
        ]
    }
    """
    group   = serializers.UUIDField()
    date    = serializers.DateField()
    records = BulkRecordSerializer(many=True)

    def validate(self, data):
        from apps.students.models import Student
        records     = data.get('records', [])
        student_ids = [r['student'] for r in records]
        # 1 ta query — N+1 dan saqlaymiz
        found = {str(s.pk): s for s in Student.objects.filter(pk__in=student_ids)}
        missing = [str(sid) for sid in student_ids if str(sid) not in found]
        if missing:
            raise serializers.ValidationError(
                f"O'quvchilar topilmadi: {', '.join(missing)}"
            )
        for r in records:
            r['student'] = found[str(r['student'])]
        return data

    def create(self, validated_data):
        from django.db import transaction
        records   = validated_data.pop('records')
        group_id  = validated_data['group']
        date      = validated_data['date']
        marked_by = self.context['request'].user

        student_ids = [r['student'].pk for r in records]
        existing = {
            a.student_id: a
            for a in Attendance.objects.filter(
                group_id=group_id, date=date, student_id__in=student_ids
            )
        }

        to_create, to_update = [], []
        for rec in records:
            sid    = rec['student'].pk
            status = rec.get('status', Attendance.Status.PRESENT)
            note   = rec.get('note', '')
            if sid in existing:
                obj = existing[sid]
                obj.status    = status
                obj.note      = note
                obj.marked_by = marked_by
                to_update.append(obj)
            else:
                to_create.append(Attendance(
                    student=rec['student'], group_id=group_id, date=date,
                    status=status, note=note, marked_by=marked_by,
                ))

        with transaction.atomic():
            if to_create:
                Attendance.objects.bulk_create(to_create, batch_size=500)
            if to_update:
                Attendance.objects.bulk_update(
                    to_update, ['status', 'note', 'marked_by'], batch_size=500
                )

        return list(existing.values()) + to_create
