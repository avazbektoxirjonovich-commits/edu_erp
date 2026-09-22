from rest_framework import serializers

from .models import Competition, Participant


class CompetitionSerializer(serializers.ModelSerializer):
    status_display    = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name   = serializers.CharField(source='created_by.full_name', read_only=True, default=None)
    participant_count = serializers.IntegerField(read_only=True, default=0)
    confirmed_count   = serializers.IntegerField(read_only=True, default=0)
    next_status       = serializers.SerializerMethodField()

    class Meta:
        model  = Competition
        fields = [
            'id', 'name', 'grade_from', 'grade_to', 'status', 'status_display', 'next_status',
            'location', 'registration_deadline', 'competition_date', 'show_full_names',
            'participant_count', 'confirmed_count',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        # Holat faqat /set-status/ orqali (tartib bilan) o'zgaradi
        read_only_fields = ['id', 'status', 'created_by', 'created_at', 'updated_at']

    def get_next_status(self, obj):
        return Competition.NEXT_STATUS.get(obj.status)

    def validate(self, data):
        grade_from = data.get('grade_from', getattr(self.instance, 'grade_from', None))
        grade_to   = data.get('grade_to', getattr(self.instance, 'grade_to', None))
        if grade_from and grade_to and grade_from > grade_to:
            raise serializers.ValidationError({'grade_to': ["Tugash sinfi boshlanish sinfidan kichik bo'lmasligi kerak."]})
        if self.instance and ('grade_from' in data or 'grade_to' in data):
            outside = self.instance.participants.exclude(grade__gte=grade_from, grade__lte=grade_to)
            if outside.exists():
                raise serializers.ValidationError({'grade_from': [
                    "Bu oraliqdan tashqaridagi sinflarda ro'yxatdan o'tganlar bor — oraliqni toraytirib bo'lmaydi."
                ]})
        return data


class SetStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Competition.Status.choices)


class ParticipantSerializer(serializers.ModelSerializer):
    status_display    = serializers.CharField(source='get_status_display', read_only=True)
    confirmed_by_name = serializers.CharField(source='confirmed_by.full_name', read_only=True, default=None)
    score             = serializers.IntegerField(source='result.score', read_only=True, default=None)
    place             = serializers.IntegerField(source='result.place', read_only=True, default=None)

    class Meta:
        model  = Participant
        fields = [
            'id', 'competition', 'first_name', 'last_name', 'phone', 'address', 'grade',
            'status', 'status_display', 'confirmed_by_name', 'confirmed_at', 'registered_at',
            'score', 'place',
        ]
        read_only_fields = fields
