"""PDF hisobot: oylik moliyaviy hisobot"""
from io import BytesIO
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.views import APIView
from apps.accounts.permissions import IsAdmin

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT


ACCENT   = colors.HexColor('#FF6B35')
DARK     = colors.HexColor('#1e293b')
MUTED    = colors.HexColor('#64748b')
SUCCESS  = colors.HexColor('#16a34a')
DANGER   = colors.HexColor('#dc2626')
LIGHT_BG = colors.HexColor('#fff5f2')
WHITE    = colors.white


def _fmt(n):
    try:
        return f"{int(float(n)):,}".replace(',', ' ') + " so'm"
    except Exception:
        return "0 so'm"


MNS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun',
       'Iyul','Avgust','Sentabr','Oktabr','Noyabr','Dekabr']


class MonthlyReportPDFView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        from apps.payments.models import Payment
        from apps.attendance.models import Attendance
        from apps.students.models import Student
        from django.db.models import Sum, Count, Q

        month = int(request.GET.get('month', timezone.now().month))
        year  = int(request.GET.get('year',  timezone.now().year))
        month_name = MNS[month - 1]

        # ── Data ──────────────────────────────────────────────
        payments = Payment.objects.filter(month=month, year=year).select_related(
            'student__user', 'group'
        )
        totals = payments.aggregate(
            total_amount=Sum('amount'),
            total_paid=Sum('paid_amount'),
            total_debt=Sum('debt_amount'),
        )
        paid_count    = payments.filter(status='paid').count()
        partial_count = payments.filter(status='partial').count()
        unpaid_count  = payments.filter(status='unpaid').count()

        students_total  = Student.objects.count()
        students_active = Student.objects.filter(status='active').count()

        att_qs = Attendance.objects.filter(
            date__month=month, date__year=year
        ).aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
            absent=Count('id',  filter=Q(status='absent')),
            late=Count('id',    filter=Q(status='late')),
        )
        att_pct = round(att_qs['present'] / att_qs['total'] * 100) if att_qs['total'] else 0

        # ── PDF Build ─────────────────────────────────────────
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'Title', fontSize=18, textColor=ACCENT,
            fontName='Helvetica-Bold', spaceAfter=4, alignment=TA_CENTER
        )
        subtitle_style = ParagraphStyle(
            'Sub', fontSize=10, textColor=MUTED,
            fontName='Helvetica', spaceAfter=12, alignment=TA_CENTER
        )
        section_style = ParagraphStyle(
            'Sec', fontSize=11, textColor=DARK,
            fontName='Helvetica-Bold', spaceBefore=14, spaceAfter=6
        )
        normal = ParagraphStyle(
            'N', fontSize=9, textColor=DARK, fontName='Helvetica'
        )

        story = []

        # Header
        story.append(Paragraph("EduERP — Oylik Hisobot", title_style))
        story.append(Paragraph(f"{month_name} {year}", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=16))

        # ── Payment summary ────────────────────────────────────
        story.append(Paragraph("To'lovlar xulosasi", section_style))
        pay_data = [
            ["Ko'rsatkich", "Miqdor"],
            ["Jami hisoblangan summa", _fmt(totals['total_amount'] or 0)],
            ["To'langan summa",        _fmt(totals['total_paid']   or 0)],
            ["Qarz summasi",           _fmt(totals['total_debt']   or 0)],
            ["To'liq to'langan",       f"{paid_count} ta o'quvchi"],
            ["Qisman to'langan",       f"{partial_count} ta o'quvchi"],
            ["To'lanmagan",            f"{unpaid_count} ta o'quvchi"],
        ]
        pay_table = Table(pay_data, colWidths=[9*cm, 7*cm])
        pay_table.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,0), ACCENT),
            ('TEXTCOLOR',    (0,0), (-1,0), WHITE),
            ('FONTNAME',     (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0,0), (-1,0), 10),
            ('FONTNAME',     (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE',     (0,1), (-1,-1), 9),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [WHITE, LIGHT_BG]),
            ('GRID',         (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING',   (0,0), (-1,-1), 6),
            ('BOTTOMPADDING',(0,0), (-1,-1), 6),
            ('LEFTPADDING',  (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (0,-1), 10),
            ('ALIGN',        (1,0), (1,-1), 'RIGHT'),
            ('TEXTCOLOR',    (1,3), (1,3), DANGER),   # qarz qizil
            ('FONTNAME',     (1,1), (1,2), 'Helvetica-Bold'),
        ]))
        story.append(pay_table)
        story.append(Spacer(1, 16))

        # ── Attendance summary ─────────────────────────────────
        story.append(Paragraph("Davomat xulosasi", section_style))
        att_data = [
            ["Ko'rsatkich", "Miqdor"],
            ["Jami darslar",  str(att_qs['total'] or 0)],
            ["Keldi",         str(att_qs['present'] or 0)],
            ["Kelmadi",       str(att_qs['absent'] or 0)],
            ["Kech keldi",    str(att_qs['late'] or 0)],
            ["Davomat foizi", f"{att_pct}%"],
        ]
        att_table = Table(att_data, colWidths=[9*cm, 7*cm])
        att_table.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,0), ACCENT),
            ('TEXTCOLOR',    (0,0), (-1,0), WHITE),
            ('FONTNAME',     (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0,0), (-1,0), 10),
            ('FONTNAME',     (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE',     (0,1), (-1,-1), 9),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [WHITE, LIGHT_BG]),
            ('GRID',         (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING',   (0,0), (-1,-1), 6),
            ('BOTTOMPADDING',(0,0), (-1,-1), 6),
            ('LEFTPADDING',  (0,0), (-1,-1), 10),
            ('ALIGN',        (1,0), (1,-1), 'RIGHT'),
        ]))
        story.append(att_table)
        story.append(Spacer(1, 16))

        # ── Student summary ────────────────────────────────────
        story.append(Paragraph("O'quvchilar", section_style))
        st_data = [
            ["Ko'rsatkich", "Miqdor"],
            ["Jami o'quvchilar", str(students_total)],
            ["Faol o'quvchilar", str(students_active)],
        ]
        st_table = Table(st_data, colWidths=[9*cm, 7*cm])
        st_table.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,0), ACCENT),
            ('TEXTCOLOR',    (0,0), (-1,0), WHITE),
            ('FONTNAME',     (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0,0), (-1,0), 10),
            ('FONTNAME',     (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE',     (0,1), (-1,-1), 9),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [WHITE, LIGHT_BG]),
            ('GRID',         (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING',   (0,0), (-1,-1), 6),
            ('BOTTOMPADDING',(0,0), (-1,-1), 6),
            ('LEFTPADDING',  (0,0), (-1,-1), 10),
            ('ALIGN',        (1,0), (1,-1), 'RIGHT'),
        ]))
        story.append(st_table)
        story.append(Spacer(1, 20))

        # ── Payment detail table ───────────────────────────────
        story.append(Paragraph("To'lovlar ro'yxati", section_style))
        det_data = [["#", "O'quvchi", "Guruh", "Hisoblangan", "To'langan", "Qarz", "Holat"]]
        status_map = {'paid': "To'langan", 'partial': 'Qisman', 'unpaid': "To'lanmagan"}
        for i, p in enumerate(payments[:50], 1):
            det_data.append([
                str(i),
                (p.student.user.full_name if p.student else '—')[:20],
                (p.group.name if p.group else '—')[:15],
                _fmt(p.amount),
                _fmt(p.paid_amount),
                _fmt(p.debt_amount) if p.debt_amount > 0 else '—',
                status_map.get(p.status, p.status),
            ])
        det_table = Table(det_data, colWidths=[0.8*cm, 4.5*cm, 3*cm, 3*cm, 3*cm, 2.5*cm, 2.5*cm])
        det_style = [
            ('BACKGROUND',   (0,0), (-1,0), ACCENT),
            ('TEXTCOLOR',    (0,0), (-1,0), WHITE),
            ('FONTNAME',     (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0,0), (-1,0), 8),
            ('FONTNAME',     (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE',     (0,1), (-1,-1), 7.5),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [WHITE, LIGHT_BG]),
            ('GRID',         (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING',   (0,0), (-1,-1), 4),
            ('BOTTOMPADDING',(0,0), (-1,-1), 4),
            ('LEFTPADDING',  (0,0), (-1,-1), 5),
            ('ALIGN',        (0,0), (0,-1), 'CENTER'),
        ]
        for i, p in enumerate(payments[:50], 1):
            if p.status == 'paid':
                det_style.append(('TEXTCOLOR', (6,i), (6,i), SUCCESS))
            elif p.status == 'unpaid':
                det_style.append(('TEXTCOLOR', (6,i), (6,i), DANGER))
                det_style.append(('TEXTCOLOR', (5,i), (5,i), DANGER))
        det_table.setStyle(TableStyle(det_style))
        story.append(det_table)

        if payments.count() > 50:
            story.append(Spacer(1, 6))
            story.append(Paragraph(
                f"* Jami {payments.count()} ta yozuv — faqat birinchi 50 tasi ko'rsatildi",
                ParagraphStyle('note', fontSize=8, textColor=MUTED)
            ))

        # Footer
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=1, color=MUTED))
        story.append(Spacer(1, 6))
        now_str = timezone.now().strftime('%d.%m.%Y %H:%M')
        story.append(Paragraph(
            f"EduERP tomonidan yaratildi | {now_str}",
            ParagraphStyle('footer', fontSize=8, textColor=MUTED, alignment=TA_CENTER)
        ))

        doc.build(story)
        buffer.seek(0)
        filename = f"hisobot_{year}_{month:02d}.pdf"
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response