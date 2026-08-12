from django.db.models import Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.payments.models import Payment

from .models import PaymentTransaction


def _sync_payment(payment):
    """Payment.paid_amount ni uning PaymentTransaction'lari yig'indisiga tenglaydi.
    Payment.save() ichida compute_status() ishlaydi, shuning uchun status/debt_amount
    ham shu chaqiruv bilan avtomatik yangilanadi."""
    total = payment.transactions.aggregate(total=Sum('amount'))['total'] or 0
    payment.paid_amount = total
    payment.save(update_fields=['paid_amount', 'status', 'debt_amount', 'updated_at'])


@receiver(post_save, sender=PaymentTransaction)
def on_transaction_saved(sender, instance, created, **kwargs):
    _sync_payment(instance.payment)
    if created and instance.debt_after is None:
        debt = instance.payment.debt_amount
        # .update() — instance.save() emas — post_save'ni qayta chaqirmasligi uchun.
        PaymentTransaction.objects.filter(pk=instance.pk).update(debt_after=debt)
        instance.debt_after = debt  # chaqiruvchidagi xotiradagi obyekt ham yangilansin


@receiver(post_delete, sender=PaymentTransaction)
def on_transaction_deleted(sender, instance, **kwargs):
    # Payment o'zi cascade orqali o'chirilayotgan bo'lishi mumkin (masalan admin
    # panelidan) — bunday holda qatorni qayta sinxronlash keraksiz va xavfli.
    try:
        payment = instance.payment
        payment.refresh_from_db()
    except Payment.DoesNotExist:
        return
    _sync_payment(payment)
