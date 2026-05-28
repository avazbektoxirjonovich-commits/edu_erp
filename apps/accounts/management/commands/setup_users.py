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
        user.set_password('9810')
        user.full_name = 'Azizbek'
        user.role = User.Role.TEACHER
        user.is_active = True
        user.save()
        Teacher.objects.get_or_create(user=user, defaults={'phone': phone})
        status = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{status}: Azizbek teacher (+998941549810)'))