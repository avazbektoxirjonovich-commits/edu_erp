from django.db import migrations


class Migration(migrations.Migration):
    # branches app o'chirilganligi sababli no-op qilindi.
    # Field 0005_remove_branch.py da ham olib tashlangan.

    dependencies = [
        ('groups', '0002_backend_fixes'),
    ]

    operations = []
