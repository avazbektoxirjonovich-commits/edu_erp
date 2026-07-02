"""
Management command: cleanup_expired_tokens
------------------------------------------
Removes expired rows from the UsedToken table.

Run manually:
    python manage.py cleanup_expired_tokens

Recommended scheduling:
  - Cron (every hour):
        0 * * * * /path/to/venv/bin/python /path/to/manage.py cleanup_expired_tokens

  - Celery beat (add to CELERY_BEAT_SCHEDULE in settings):
        'cleanup-expired-face-tokens': {
            'task':     'apps.face_auth.tasks.cleanup_expired_tokens',
            'schedule': crontab(minute=0),   # every hour
        }
        Then implement a Celery task that calls:
            from apps.face_auth.token_store import cleanup_expired
            cleanup_expired()

Usage notes:
  - Safe to run any time; idempotent.
  - Token TTLs are short (5–10 min), so an hourly sweep is sufficient.
  - Django cache handles most replay prevention; the DB table is a secondary
    process-safety layer. Rows older than max(FACE_PENDING_MAX_AGE,
    FALLBACK_MAX_AGE, OTP_MAX_AGE) = 10 minutes can always be deleted.
"""
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger('apps.face_auth')


class Command(BaseCommand):
    help = "FaceAuth: muddati o'tgan UsedToken yozuvlarini o'chirish"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Haqiqatda o\'chirmay, faqat nechta yozuv o\'chirilishini ko\'rsatish',
        )

    def handle(self, *args, **options):
        from apps.face_auth.models import UsedToken
        dry_run = options['dry_run']

        now     = timezone.now()
        expired = UsedToken.objects.filter(expires_at__lte=now)
        count   = expired.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry-run: {count} ta muddati o'tgan token o'chirilishi mumkin edi."
                )
            )
        else:
            deleted, _ = expired.delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f"{deleted} ta muddati o'tgan UsedToken yozuvi o'chirildi."
                )
            )
            logger.info("cleanup_expired_tokens: %d yozuv o'chirildi", deleted)
