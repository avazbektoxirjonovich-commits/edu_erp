from rest_framework.viewsets import ModelViewSet
from rest_framework import filters
from django.db.models import Count, Q
from apps.accounts.permissions import IsAdmin
from .models import Branch
from .serializers import BranchSerializer, BranchCreateSerializer


class BranchViewSet(ModelViewSet):
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields   = ['name', 'address']
    ordering        = ['name']

    def get_permissions(self):
        return [IsAdmin()]

    def get_queryset(self):
        return (
            Branch.objects
            .annotate(
                _groups_count=Count(
                    'groups',
                    filter=Q(groups__status='active'),
                    distinct=True,
                )
            )
        )

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return BranchCreateSerializer
        return BranchSerializer