"""
python manage.py send_payment_reminders
Qarzdor o'quvchilarga to'lov eslatmasi yuboradi.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.payments.models import Payment
from apps.notifications.models import Notification


class Command(BaseCommand):
    help = "Qarzdor o'quvchilarga to'lov eslatmasi yuboradi"

    def add_arguments(self, parser):
        parser.add_argument('--month', type=int, default=None)
        parser.add_argument('--year',  type=int, default=None)
        parser.add_argument('--dry-run', action='store_true',
                            help="Xabar yubormay faqat ko'rsatadi")

    def handle(self, *args, **options):
        now   = timezone.now()
        month = options['month'] or now.month
        year  = options['year']  or now.year
        dry   = options['dry_run']

        unpaid = (
            Payment.objects
            .filter(month=month, year=year, status__in=['unpaid', 'partial'])
            .select_related('student__user', 'group')
        )

        if not unpaid.exists():
            self.stdout.write(self.style.SUCCESS("Qarzdor o'quvchilar topilmadi."))
            return

        count = 0
        for pay in unpaid:
            user = pay.student.user
            if not user.is_active:
                continue
            already = Notification.objects.filter(
                recipient=user,
                notif_type=Notification.Type.PAYMENT_REMINDER,
                created_at__month=now.month,
                created_at__year=now.year,
            ).exists()
            if already:
                continue

            msg = (
                f"Hurmatli {user.full_name},\n"
                f"{year}-yil {month}-oy uchun to'lovingiz amalga oshirilmagan.\n"
                f"Qarz miqdori: {pay.debt_amount:,.0f} so'm.\n"
                f"Iltimos, to'lovni amalga oshiring."
            )
            if not dry:
                Notification.objects.create(
                    recipient  = user,
                    channel    = Notification.Channel.SYSTEM,
                    notif_type = Notification.Type.PAYMENT_REMINDER,
                    title      = f"{month}-oy to'lov eslatmasi",
                    message    = msg,
                    status     = Notification.Status.SENT,
                )
            self.stdout.write(f"  {'[DRY]' if dry else '✓'} {user.full_name} — {pay.debt_amount:,.0f} so'm")
            count += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n{'[DRY RUN] ' if dry else ''}Jami {count} ta eslatma {'yuborildi' if not dry else 'ko\\'rinadi'}."
        ))