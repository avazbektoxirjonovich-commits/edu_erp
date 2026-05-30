from django.db import migrations


class Migration(migrations.Migration):
    # 0003 no-op bo'lgani uchun bu migratsiya ham no-op.

    dependencies = [
        ('groups', '0004_add_room_to_lessonschedule'),
    ]

    operations = []
