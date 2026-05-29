from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('groups', '0004_add_room_to_lessonschedule'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='group',
            name='branch',
        ),
    ]
