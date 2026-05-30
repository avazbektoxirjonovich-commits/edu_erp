from datetime import date, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from apps.common.utils import calculate_attendance_pct
from .models import Student


class LeaderboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = request.query_params.get('period', 'all')   # all | month | week
        group  = request.query_params.get('group', '')
        try:
            limit = min(int(request.query_params.get('limit', 50)), 200)
        except (ValueError, TypeError):
            limit = 50

        qs = (
            Student.objects
            .select_related('user', 'group')
            .filter(status='active')
            .annotate(
                _att_total=Count('attendances', distinct=True),
                _att_present=Count(
                    'attendances',
                    filter=Q(attendances__status='present'),
                    distinct=True
                ),
            )
        )

        if group:
            qs = qs.filter(group__id=group)

        if period == 'week':
            qs = qs.filter(created_at__date__gte=date.today() - timedelta(days=7))
        elif period == 'month':
            today = date.today()
            qs = qs.filter(created_at__year=today.year, created_at__month=today.month)

        qs = qs.order_by('-xp_points', '-level', '-coins')[:limit]

        results = [
            {
                'id':         str(s.id),
                'full_name':  s.user.full_name,
                'group_name': s.group.name if s.group else None,
                'xp_points':  s.xp_points,
                'coins':      s.coins,
                'level':      s.level,
                'attendance': calculate_attendance_pct(s._att_present, s._att_total),
            }
            for s in qs
        ]

        return Response({'results': results, 'count': len(results)})