"""
Group.monthly_fee olib tashlanadi — oylik to'lov endi faqat o'quvchida
(students.0007 avval narxlarni o'quvchilarga ko'chiradi).

Orqaga qaytarish: ustun qayta qo'shiladi va har bir guruhga o'quvchilari
orasida eng ko'p uchraydigan narx yoziladi (o'quvchisi bo'lmasa — 500000).
"""
from collections import Counter

from django.db import migrations


def restore_group_fee_from_students(apps, schema_editor):
    Group = apps.get_model('groups', 'Group')
    Student = apps.get_model('students', 'Student')
    for group in Group.objects.all():
        fees = Counter(
            Student.objects.filter(group=group, monthly_fee__isnull=False)
            .values_list('monthly_fee', flat=True)
        )
        if fees:
            group.monthly_fee = fees.most_common(1)[0][0]
            group.save(update_fields=['monthly_fee'])


class Migration(migrations.Migration):

    dependencies = [
        ('groups', '0006_group_payment_due_day'),
        ('students', '0007_copy_fee_from_group'),
    ]

    operations = [
        # Oldinga: hech narsa. Orqaga: RemoveField teskarisi ustunni qaytargandan
        # KEYIN ishlaydi va narxni o'quvchilardan tiklaydi.
        migrations.RunPython(migrations.RunPython.noop, restore_group_fee_from_students),
        migrations.RemoveField(model_name='group', name='monthly_fee'),
    ]
