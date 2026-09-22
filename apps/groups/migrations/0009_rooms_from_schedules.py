"""
Jadvallarda erkin matn sifatida yozilgan xona nomlaridan xonalar ro'yxati
yaratiladi. "101", " 101 " va "101" kabi yozuvlar (katta-kichik harf, bo'sh joy)
bitta xonaga birlashtiriladi va jadvaldagi nom shu xona nomiga tenglashtiriladi.

Orqaga qaytarish: xonalar o'chiriladi (jadvaldagi nomlar o'z holicha qoladi).
"""
from django.db import migrations


def create_rooms(apps, schema_editor):
    Room = apps.get_model('groups', 'Room')
    LessonSchedule = apps.get_model('groups', 'LessonSchedule')
    canonical = {r.name.strip().lower(): r.name for r in Room.objects.all()}
    for sched in LessonSchedule.objects.exclude(room='').order_by('created_at'):
        key = sched.room.strip().lower()
        if not key:
            continue
        if key not in canonical:
            name = sched.room.strip()
            Room.objects.create(name=name)
            canonical[key] = name
        if sched.room != canonical[key]:
            sched.room = canonical[key]
            sched.save(update_fields=['room'])


def delete_rooms(apps, schema_editor):
    apps.get_model('groups', 'Room').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('groups', '0008_room'),
    ]

    operations = [
        migrations.RunPython(create_rooms, delete_rooms),
    ]
