from datetime import date, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from .models import Student


class LeaderboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = request.query_params.get('period', 'all')   # all | month | week
        group  = request.query_params.get('group', '')
        limit  = min(int(request.query_params.get('limit', 50)), 200)

        qs = Student.objects.select_related('user', 'group').filter(status='active')

        if group:
            qs = qs.filter(group__id=group)

        # Period filter — filter by joined_date or just by xp earned in period
        if period == 'week':
            week_ago = date.today() - timedelta(days=7)
            qs = qs.filter(created_at__date__gte=week_ago)
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
                'attendance': s.attendance_percentage,
            }
            for s in qs
        ]

        return Response({'results': results, 'count': len(results)})