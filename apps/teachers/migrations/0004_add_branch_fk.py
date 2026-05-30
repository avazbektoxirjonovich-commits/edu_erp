from django.db import migrations


class Migration(migrations.Migration):
    # branches app o'chirilganligi sababli bu migratsiya no-op qilindi.
    # Field 0006_remove_branch.py da ham olib tashlangan.

    dependencies = [
        ('teachers', '0003_subject_blank'),
    ]

    operations = []
