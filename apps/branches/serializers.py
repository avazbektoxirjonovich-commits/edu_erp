from rest_framework import serializers
from .models import Branch


class BranchSerializer(serializers.ModelSerializer):
    active_groups_count   = serializers.SerializerMethodField()
    active_students_count = serializers.SerializerMethodField()

    class Meta:
        model  = Branch
        fields = [
            'id', 'name', 'address', 'phone', 'is_active',
            'active_groups_count', 'active_students_count',
            'created_at',
        ]

    def get_active_groups_count(self, obj):
        v = getattr(obj, '_groups_count', None)
        return v if v is not None else obj.groups.filter(status='active').count()

    def get_active_students_count(self, obj):
        v = getattr(obj, '_students_count', None)
        return v if v is not None else obj.active_students_count


class BranchCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Branch
        fields = ['name', 'address', 'phone', 'is_active']