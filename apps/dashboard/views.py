import logging
from datetime import date
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Count, Q, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts.permissions import IsAdmin
from apps.students.models import Student
from apps.groups.models import Group
from apps.attendance.models import Attendance
from apps.payments.models import Payment

logger = logging.getLogger('apps.dashboard')


class DashboardView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        now   = timezone.now()
        month = now.month
        year  = now.year
        today = date.today()

        # ── Students — 1 query ──
        student_stats = Student.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status='active')),
            new=Count('id', filter=Q(created_at__month=month, created_at__year=year)),
        )

        # ── Groups — 1 query ──
        group_stats = Group.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status='active')),
        )

        # ── Payments current month — 1 query ──
        _df = DecimalField(max_digits=14, decimal_places=0)
        pay_stats = Payment.objects.filter(month=month, year=year).aggregate(
            income=Coalesce(Sum('paid_amount'), 0, output_field=_df),
            debt=Coalesce(Sum('debt_amount'),   0, output_field=_df),
            unpaid_count=Count('id', filter=Q(status__in=['unpaid', 'partial'])),
        )

        # ── Attendance today — 1 query ──
        att_today = Attendance.objects.filter(date=today).aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
        )
        att_pct = (
            round(att_today['present'] / att_today['total'] * 100, 1)
            if att_today['total'] else 0
        )

        # ── 6-month income — 1 query (was 6) ──
        six_months_ago = date(year if month > 6 else year - 1,
                              (month - 6) % 12 or 12, 1)
        monthly_rows = (
            Payment.objects
            .filter(
                year__gte=six_months_ago.year,
                year__lte=year,
            )
            .values('month', 'year')
            .annotate(
                paid=Coalesce(Sum('paid_amount'), 0, output_field=_df),
                debt=Coalesce(Sum('debt_amount'), 0, output_field=_df),
            )
            .order_by('year', 'month')
        )
        monthly_map = {(r['year'], r['month']): r for r in monthly_rows}

        monthly_income = []
        for i in range(5, -1, -1):
            m = month - i
            y = year
            if m <= 0:
                m += 12
                y -= 1
            row = monthly_map.get((y, m), {})
            monthly_income.append({
                'month': m, 'year': y,
                'paid': float(row.get('paid', 0)),
                'debt': float(row.get('debt', 0)),
            })

        # ── Top groups — 1 annotated query ──
        groups_qs = (
            Group.objects
            .filter(status='active')
            .select_related('branch')
            .annotate(
                attend_total=Count('attendances', distinct=True),
                attend_present=Count('attendances',
                                     filter=Q(attendances__status='present'),
                                     distinct=True),
                active_students=Count('students',
                                      filter=Q(students__status='active'),
                                      distinct=True),
            )
            .order_by('-active_students')[:5]
        )

        top_groups = [
            {
                'id':         str(g.id),
                'name':       g.name,
                'branch':     g.branch.name if g.branch else '',
                'students':   g.active_students,
                'attendance': (
                    round(g.attend_present / g.attend_total * 100, 1)
                    if g.attend_total else 0
                ),
            }
            for g in groups_qs
        ]

        # ── Branches summary — 1 query ──
        from apps.branches.models import Branch
        branches = (
            Branch.objects
            .filter(is_active=True)
            .annotate(
                grp_count=Count('groups', filter=Q(groups__status='active'), distinct=True),
                stu_count=Count('groups__students',
                                filter=Q(groups__students__status='active'),
                                distinct=True),
            )
            .values('id', 'name', 'grp_count', 'stu_count')
        )
        branches_list = [
            {
                'id':       str(b['id']),
                'name':     b['name'],
                'groups':   b['grp_count'],
                'students': b['stu_count'],
            }
            for b in branches
        ]

        # ── Debtors list — 1 query ──
        unpaid = (
            Payment.objects
            .filter(month=month, year=year, status__in=['unpaid', 'partial'])
            .select_related('student__user', 'group')
            .order_by('-debt_amount')[:10]
        )
        unpaid_list = [
            {
                'student_id':   str(p.student.id),
                'student_name': p.student.user.full_name,
                'group':        p.group.name if p.group else '',
                'debt':         float(p.debt_amount),
                'status':       p.status,
            }
            for p in unpaid
        ]

        return Response({
            'students': {
                'total':  student_stats['total'],
                'active': student_stats['active'],
                'new':    student_stats['new'],
            },
            'groups': {
                'total':  group_stats['total'],
                'active': group_stats['active'],
            },
            'payments': {
                'income':       float(pay_stats['income']),
                'debt':         float(pay_stats['debt']),
                'unpaid_count': pay_stats['unpaid_count'],
                'month':        month,
                'year':         year,
            },
            'attendance': {
                'today_total':   att_today['total'],
                'today_present': att_today['present'],
                'percentage':    att_pct,
            },
            'monthly_income':  monthly_income,
            'top_groups':      top_groups,
            'branches':        branches_list,
            'unpaid_students': unpaid_list,
        })
