"""PDF chek: bitta to'lov operatsiyasi (PaymentTransaction) uchun professional chek."""
from io import BytesIO

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsFinanceOrAdmin

from .models import PaymentTransaction

BRAND    = "Qorako'l Ilm Ziyo"
ACCENT   = colors.HexColor('#059669')
DARK     = colors.HexColor('#0D1B2A')
MUTED    = colors.HexColor('#64748b')
DANGER   = colors.HexColor('#dc2626')
LIGHT_BG = colors.HexColor('#f0fdf9')
WHITE    = colors.white

PAYMENT_TYPE_LABELS = {
    'cash':     'Naqd',
    'card':     'Karta',
    'transfer': "O'tkazma",
}


def _fmt(n):
    try:
        return f"{int(float(n)):,}".replace(',', ' ') + " so'm"
    except (TypeError, ValueError):
        return "0 so'm"


class TransactionReceiptPDFView(APIView):
    """GET /api/v1/finance/transactions/<uuid:pk>/receipt-pdf/ — Admin yoki Moliyachi."""
    permission_classes = [IsFinanceOrAdmin]

    def get(self, request, pk):
        try:
            txn = PaymentTransaction.objects.select_related(
                'payment__student__user', 'payment__group', 'received_by'
            ).get(pk=pk)
        except PaymentTransaction.DoesNotExist:
            return Response({'detail': 'Chek topilmadi.'}, status=404)

        payment = txn.payment
        student = payment.student
        group   = payment.group

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A5,
            leftMargin=1.5*cm, rightMargin=1.5*cm,
            topMargin=1.5*cm, bottomMargin=1.5*cm,
        )

        title_style = ParagraphStyle(
            'Title', fontSize=16, textColor=ACCENT, leading=20,
            fontName='Helvetica-Bold', spaceAfter=6, alignment=TA_CENTER,
        )
        subtitle_style = ParagraphStyle(
            'Sub', fontSize=10, textColor=MUTED,
            fontName='Helvetica', spaceAfter=10, alignment=TA_CENTER,
        )
        label_style = ParagraphStyle('L', fontSize=9, textColor=MUTED, fontName='Helvetica')

        story = [
            Paragraph(BRAND, title_style),
            Paragraph("To'lov cheki", subtitle_style),
            HRFlowable(width="100%", thickness=1.5, color=ACCENT, spaceAfter=4),
            Paragraph(f"Chek raqami: <b>{txn.receipt_number}</b>", label_style),
            Paragraph(f"Sana: {txn.paid_at.strftime('%d.%m.%Y %H:%M')}", label_style),
            Spacer(1, 12),
        ]

        rows = [
            ["O'quvchi", student.full_name],
            ["Guruh", group.name if group else "—"],
            ["To'lov summasi", _fmt(txn.amount)],
            ["To'lov turi", PAYMENT_TYPE_LABELS.get(txn.payment_type, txn.payment_type)],
            ["Qabul qildi", txn.received_by.full_name if txn.received_by else "—"],
        ]
        info_table = Table(rows, colWidths=[5*cm, 7.5*cm])
        info_table.setStyle(TableStyle([
            ('FONTNAME',      (0, 0), (0, -1), 'Helvetica'),
            ('FONTNAME',      (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, -1), 9.5),
            ('TEXTCOLOR',     (0, 0), (0, -1), MUTED),
            ('TEXTCOLOR',     (1, 0), (1, -1), DARK),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [WHITE, LIGHT_BG]),
            ('GRID',          (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('ALIGN',         (1, 0), (1, -1), 'RIGHT'),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 10))

        debt = txn.debt_after if txn.debt_after is not None else payment.debt_amount
        debt_rows = [["Qolgan qarz", _fmt(debt) if debt > 0 else "Yo'q (to'liq to'langan)"]]
        debt_table = Table(debt_rows, colWidths=[5*cm, 7.5*cm])
        debt_table.setStyle(TableStyle([
            ('FONTNAME',  (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME',  (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTSIZE',  (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (1, 0), (1, -1), DANGER if debt > 0 else ACCENT),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BG),
            ('GRID',      (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('ALIGN',     (1, 0), (1, -1), 'RIGHT'),
        ]))
        story.append(debt_table)

        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"{BRAND} | Bu hujjat avtomatik yaratildi",
            ParagraphStyle('footer', fontSize=7.5, textColor=MUTED, alignment=TA_CENTER),
        ))

        doc.build(story)
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="chek_{txn.receipt_number}.pdf"'
        return response
