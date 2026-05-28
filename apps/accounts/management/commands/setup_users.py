from django.core.management.base import BaseCommand
from apps.accounts.models import User
from apps.teachers.models import Teacher


class Command(BaseCommand):
    help = 'Delete non-developer users and create teacher Azizbek'

    def handle(self, *args, **options):
        # 1 — Delete all users except developer
        deleted = User.objects.exclude(role=User.Role.DEVELOPER).delete()
        self.stdout.write(f'Deleted: {deleted}')

        # 2 — Create teacher Azizbek
        phone = '+998941549810'
        if User.objects.filter(phone=phone).exists():
            user = User.objects.get(phone=phone)
            user.set_password('9810')
            user.full_name = 'Azizbek'
            user.role = User.Role.TEACHER
            user.is_active = True
            user.save()
            self.stdout.write(f'Updated user: {phone}')
        else:
            user = User.objects.create_user(
                phone=phone,
                password='9810',
                full_name='Azizbek',
                role=User.Role.TEACHER,
            )
            self.stdout.write(f'Created user: {phone}')

        Teacher.objects.get_or_create(user=user, defaults={'phone': phone})
        self.stdout.write(self.style.SUCCESS('Done! Azizbek teacher created.'))