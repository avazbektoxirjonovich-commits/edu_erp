"""
TO'LOV QOIDALARI — pul bilan bog'liq barcha yozuvlar shu yerdan o'tadi.

Asosiy qoidalar:
  1. Payment — o'quvchining bir oylik HISOBI (qancha to'lashi kerak).
     Bir o'quvchi + bir oy = bitta hisob, guruhi o'zgarsa ham (guruh hisob
     ochilgan paytdagi holatda qoladi).
  2. Pul FAQAT chek (PaymentTransaction) orqali kiradi. Payment.paid_amount
     qo'lda o'zgartirilmaydi — u bekor qilinmagan cheklar yig'indisi
     (apps/finance/signals.py).
  3. Hisobdan ortiq pul qabul qilinmaydi — oldindan to'lash uchun keyingi oy
     tanlanadi.
  4. Chek o'chirilmaydi, faqat bekor qilinadi (sabab bilan).
"""
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Payment


def find_invoice(student, month, year):
    """O'quvchining shu oy uchun hisobi (guruhidan qat'i nazar) yoki None.
    Eski ma'lumotda bir oyga bir nechta hisob bo'lishi mumkin — avval joriy
    guruhdagisi, keyin qarzi borlari tanlanadi."""
    invoices = list(Payment.objects.filter(student=student, month=month, year=year))
    if not invoices:
        return None
    invoices.sort(key=lambda p: (p.group_id != student.group_id, p.debt_amount <= 0, p.created_at))
    return invoices[0]


def get_or_create_invoice(student, month, year):
    """(payment, created). Yangi hisob o'quvchining joriy guruhi, narxi va chegirmasi bilan ochiladi."""
    invoice = find_invoice(student, month, year)
    if invoice:
        return invoice, False
    try:
        with transaction.atomic():
            return Payment.objects.create(
                student=student, group=student.group, month=month, year=year,
                amount=student.effective_monthly_fee,
                # O'quvchining doimiy chegirmasi hisob ochilgan paytdagi holatda
                # muhrlanadi — keyin chegirma o'zgarsa, eski hisoblar tegilmaydi.
                discount=student.effective_discount,
            ), True
    except IntegrityError:
        # Parallel so'rov xuddi shu hisobni ochib ulgurdi
        return find_invoice(student, month, year), False


def generate_monthly_invoices(month, year):
    """Barcha faol o'quvchilarga shu oy uchun hisob ochadi. Qayta chaqirilsa
    takrorlamaydi. Narxi 0 bo'lgan (guruhsiz, shaxsiy narxsiz) o'quvchilar o'tkaziladi."""
    from apps.students.models import Student

    created = existing = skipped = 0
    students = Student.objects.filter(status=Student.Status.ACTIVE).select_related('group')
    for student in students:
        if not student.effective_monthly_fee:
            skipped += 1
            continue
        _, was_created = get_or_create_invoice(student, month, year)
        if was_created:
            created += 1
        else:
            existing += 1
    return {'month': month, 'year': year, 'created': created,
            'existing': existing, 'skipped_no_fee': skipped}


def remaining_debt(payment):
    return max(0, payment.amount - payment.discount - payment.paid_amount)


def record_payment(*, student, month, year, amount, payment_type, note, user):
    """Chek yozadi. Hisob bo'lmasa ochadi. Ortiqcha to'lovni rad etadi."""
    from apps.finance.models import PaymentTransaction

    with transaction.atomic():
        invoice, _ = get_or_create_invoice(student, month, year)
        # Qatorni qulflash — bir vaqtda ikki kassir bitta qarzni ikki marta yopa olmasin
        invoice = Payment.objects.select_for_update().get(pk=invoice.pk)
        remaining = remaining_debt(invoice)
        if remaining <= 0:
            if invoice.amount - invoice.discount <= 0:
                raise ValidationError({'amount': [
                    "Bu o'quvchiga narx belgilanmagan (guruh yoki shaxsiy narx yo'q)."
                ]})
            raise ValidationError({'amount': [
                f"{year}-yil {month}-oy to'liq to'langan. Oldindan to'lash uchun keyingi oyni tanlang."
            ]})
        if amount > remaining:
            raise ValidationError({'amount': [
                f"Bu oy uchun qolgan qarz: {remaining:,.0f} so'm. Ortiqcha to'lov qabul qilinmaydi — "
                f"qolganini keyingi oy uchun alohida kiriting."
            ]})
        return PaymentTransaction.objects.create(
            payment=invoice,
            group=invoice.group,
            amount=amount,
            payment_type=payment_type,
            note=note,
            received_by=user,
        )


def cancel_transaction(txn, *, user, reason):
    """Chekni bekor qiladi (o'chirmaydi). Hisobning to'langan summasi qayta hisoblanadi."""
    from apps.finance.models import PaymentTransaction

    reason = (reason or '').strip()
    if len(reason) < 3:
        raise ValidationError({'reason': ["Bekor qilish sababini yozing."]})
    with transaction.atomic():
        txn = PaymentTransaction.objects.select_for_update().get(pk=txn.pk)
        if txn.is_cancelled:
            raise ValidationError({'detail': "Bu chek allaqachon bekor qilingan."})
        txn.is_cancelled  = True
        txn.cancelled_at  = timezone.now()
        txn.cancelled_by  = user
        txn.cancel_reason = reason[:200]
        txn.save(update_fields=['is_cancelled', 'cancelled_at', 'cancelled_by', 'cancel_reason'])
    return txn
