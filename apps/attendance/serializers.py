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
    records = AttendanceSerializer(many=True)

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
