from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('teachers', '0005_add_teachersalarypayment'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='teacher',
            name='branch',
        ),
    ]
