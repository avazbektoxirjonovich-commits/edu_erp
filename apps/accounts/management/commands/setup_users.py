from django.core.management.base import BaseCommand
from apps.accounts.models import User
from apps.teachers.models import Teacher


class Command(BaseCommand):
    help = 'Delete non-developer users and create teacher Azizbek'

    def handle(self, *args, **options):
        phone = '+998941549810'
        user, created = User.objects.get_or_create(
            phone=phone,
            defaults={
                'full_name': 'Azizbek',
                'role': User.Role.TEACHER,
                'is_active': True,
            }
        )
        if created:
            user.set_password('9810')
            user.save()
            Teacher.objects.get_or_create(user=user, defaults={'phone': phone})
            self.stdout.write(self.style.SUCCESS('Created: Azizbek teacher (+998941549810)'))
        else:
            self.stdout.write('Already exists: Azizbek (+998941549810) — skipped')