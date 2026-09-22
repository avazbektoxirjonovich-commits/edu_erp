"""
Oylik to'lov guruhdan o'quvchiga ko'chiriladi: narxi belgilanmagan har bir
o'quvchiga uning guruhining hozirgi oylik narxi yoziladi. Shundan keyin
groups.0007 Group.monthly_fee ustunini olib tashlaydi — hech kimning to'lovi
o'zgarmaydi.

Orqaga qaytarish: o'quvchi narxlari saqlanib qoladi (ular to'g'ri qiymat),
guruh narxini esa groups.0007 ning teskari amali tiklaydi.
"""
from django.db import migrations


def copy_fee_from_group(apps, schema_editor):
    Student = apps.get_model('students', 'Student')
    for student in Student.objects.filter(monthly_fee__isnull=True, group__isnull=False).select_related('group'):
        student.monthly_fee = student.group.monthly_fee
        student.save(update_fields=['monthly_fee'])


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0006_student_monthly_fee'),
        ('groups', '0006_group_payment_due_day'),
    ]

    operations = [
        migrations.RunPython(copy_fee_from_group, migrations.RunPython.noop),
    ]
