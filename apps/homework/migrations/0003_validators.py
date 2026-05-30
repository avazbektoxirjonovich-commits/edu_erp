import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('homework', '0002_backend_fixes'),
    ]

    operations = [
        # Assignment.max_score — minimal qiymat 1 bo'lishi shart (0 ga bo'lish xatosi oldini oladi)
        migrations.AlterField(
            model_name='assignment',
            name='max_score',
            field=models.PositiveSmallIntegerField(
                default=100,
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name='Maksimal ball',
            ),
        ),
        # Assignment.file — ruxsat etilgan fayl turlari
        migrations.AlterField(
            model_name='assignment',
            name='file',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='homework/assignments/',
                validators=[django.core.validators.FileExtensionValidator(
                    ['pdf', 'doc', 'docx', 'txt', 'odt',
                     'jpg', 'jpeg', 'png', 'gif',
                     'ppt', 'pptx', 'xls', 'xlsx', 'zip']
                )],
                verbose_name='Fayl (ixtiyoriy)',
            ),
        ),
        # Submission.file — ruxsat etilgan fayl turlari
        migrations.AlterField(
            model_name='submission',
            name='file',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='homework/submissions/',
                validators=[django.core.validators.FileExtensionValidator(
                    ['pdf', 'doc', 'docx', 'txt', 'odt',
                     'jpg', 'jpeg', 'png', 'gif',
                     'ppt', 'pptx', 'xls', 'xlsx', 'zip']
                )],
                verbose_name='Topshirilgan fayl',
            ),
        ),
    ]
