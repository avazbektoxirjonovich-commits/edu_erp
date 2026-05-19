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
        records = validated_data.pop('records')
        created = []
        for rec in records:
            obj, _ = Attendance.objects.update_or_create(
                student=rec['student'],
                group_id=validated_data['group'],
                date=validated_data['date'],
                defaults={
                    'status':    rec.get('status', Attendance.Status.PRESENT),
                    'note':      rec.get('note', ''),
                    'marked_by': self.context['request'].user,
                }
            )
            created.append(obj)
        return created
