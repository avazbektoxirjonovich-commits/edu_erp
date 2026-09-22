"""
Eski tizimda Payment.paid_amount chekisiz ham yozilgan (POST/PATCH /payments/,
admin panel). Endi paid_amount = bekor qilinmagan cheklar yig'indisi, shuning
uchun cheklar bilan qoplanmagan farq uchun "Noma'lum (eski yozuv)" turidagi
chek yaratiladi — to'langan summa, holat va qarz O'ZGARMAYDI.

paid_amount cheklar yig'indisidan KAM bo'lgan hisoblarga tegilmaydi —
ularni `python manage.py payments_audit` ko'rsatadi, qo'lda ko'rib chiqiladi.

Orqaga qaytarish: shu migratsiya yaratgan cheklar o'chiriladi.
"""
import uuid
from datetime import datetime, time

from django.db import migrations
from django.db.models import Sum
from django.utils import timezone

LEGACY_PREFIX = 'ESKI'
LEGACY_NOTE = "Eski tizimdan o'tkazildi (chek yo'q edi)"


def create_legacy_receipts(apps, schema_editor):
    Payment = apps.get_model('payments', 'Payment')
    PaymentTransaction = apps.get_model('finance', 'PaymentTransaction')

    for payment in Payment.objects.filter(paid_amount__gt=0).iterator():
        covered = PaymentTransaction.objects.filter(
            payment_id=payment.pk, is_cancelled=False,
        ).aggregate(total=Sum('amount'))['total'] or 0
        gap = payment.paid_amount - covered
        if gap <= 0:
            continue
        if payment.payment_date:
            paid_at = timezone.make_aware(datetime.combine(payment.payment_date, time(12, 0)))
        else:
            paid_at = payment.updated_at
        PaymentTransaction.objects.create(
            payment_id=payment.pk,
            group_id=payment.group_id,
            amount=gap,
            payment_type='unknown',
            receipt_number=f"{LEGACY_PREFIX}{paid_at:%y%m%d}{uuid.uuid4().hex[:6].upper()}",
            note=LEGACY_NOTE,
            received_by_id=payment.received_by_id,
            debt_after=payment.debt_amount,
            paid_at=paid_at,
        )


def delete_legacy_receipts(apps, schema_editor):
    PaymentTransaction = apps.get_model('finance', 'PaymentTransaction')
    PaymentTransaction.objects.filter(
        payment_type='unknown', receipt_number__startswith=LEGACY_PREFIX, note=LEGACY_NOTE,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0005_paymenttransaction_cancel_reason_and_more'),
        ('payments', '0004_alter_payment_student'),
    ]

    operations = [
        migrations.RunPython(create_legacy_receipts, delete_legacy_receipts),
    ]
