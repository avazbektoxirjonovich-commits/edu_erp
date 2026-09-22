"""
XONA BANDLIGI — guruh ochishda/tahrirlashda bir xonaga bir vaqtda ikki guruh
qo'yilmasligi uchun.

Ikki dars to'qnashadi, agar:
  - xona bir xil (katta-kichik harf va bo'sh joy farqi hisobga olinmaydi),
  - hafta kuni bir xil,
  - dars vaqtlari kesishadi (09:00–10:30 va 10:30–12:00 kesishmaydi),
  - ikkala guruh ham faol va o'qish davrlari (start_date..end_date) ustma-ust.
"""
from rest_framework.exceptions import ValidationError

from .models import Group, LessonSchedule, Room

DAY_NAMES = dict(Group.DayOfWeek.choices)


def normalize(name):
    return (name or '').strip().lower()


def resolve_room_name(name):
    """Kiritilgan nomni ro'yxatdagi xona nomiga aylantiradi ('' — xonasiz).
    Ro'yxatda yo'q yoki nofaol xona bo'lsa — xato."""
    key = normalize(name)
    if not key:
        return ''
    for room in Room.objects.filter(is_active=True):
        if normalize(room.name) == key:
            return room.name
    raise ValidationError({'room': [f"\"{name.strip()}\" xonasi ro'yxatda yo'q. Avval \"Xonalar\"ga qo'shing."]})


def _periods_overlap(a, b):
    a_end, b_end = a.end_date, b.end_date
    return (a_end is None or a_end >= b.start_date) and (b_end is None or b_end >= a.start_date)


def find_conflicts(group, day_room_pairs):
    """group — saqlanmoqchi bo'lgan holat (vaqt, sana, holat); day_room_pairs — [(kun, xona nomi)].
    To'qnashgan jadvallar ro'yxatini qaytaradi."""
    if group.status != Group.Status.ACTIVE or not group.start_time or not group.end_time:
        return []
    wanted = {(day, normalize(room)) for day, room in day_room_pairs if normalize(room)}
    if not wanted:
        return []
    others = (LessonSchedule.objects
              .filter(day_of_week__in={d for d, _ in wanted}, group__status=Group.Status.ACTIVE)
              .exclude(room='')
              .select_related('group__teacher__user'))
    if group.pk:
        others = others.exclude(group_id=group.pk)
    conflicts = []
    for other in others:
        g = other.group
        if (other.day_of_week, normalize(other.room)) not in wanted:
            continue
        if not (group.start_time < g.end_time and g.start_time < group.end_time):
            continue
        if not _periods_overlap(group, g):
            continue
        conflicts.append(other)
    return conflicts


def assert_no_conflicts(group, day_room_pairs):
    conflicts = find_conflicts(group, day_room_pairs)
    if conflicts:
        lines = [
            f"{c.room} xonasi {DAY_NAMES[c.day_of_week]} kuni "
            f"{c.group.start_time:%H:%M}–{c.group.end_time:%H:%M} da \"{c.group.name}\" guruhi bilan band"
            for c in conflicts
        ]
        raise ValidationError({'detail': "Xona band: " + "; ".join(lines) + "."})
