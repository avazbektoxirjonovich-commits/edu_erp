"""
Namuna ma'lumotlar yaratish skripti.
Ishlatish: python manage.py shell < scripts/create_sample_data.py
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.utils import timezone
from apps.accounts.models import User
from apps.teachers.models import Teacher
from apps.groups.models import Group, LessonSchedule
from apps.students.models import Student
from apps.attendance.models import Attendance
from apps.payments.models import Payment
from datetime import date, timedelta
import random

print("🌱 Namuna ma'lumotlar yaratilmoqda...")

# O'qituvchilar
teachers_data = [
    ('Jasur Xolmatov',    '+998901110001', 'Python dasturlash', 2000000),
    ('Nilufar Rashidova', '+998901110002', 'Web Design & UI/UX', 1800000),
    ('Kamol Tursunov',    '+998901110003', 'Ingliz tili',         1500000),
]
teachers = []
for name, phone, subject, salary in teachers_data:
    user, created = User.objects.get_or_create(
        phone=phone,
        defaults={'full_name': name, 'role': User.Role.TEACHER, 'is_staff': False}
    )
    if created:
        user.set_password('erp12345')
        user.save()
    t, _ = Teacher.objects.get_or_create(
        user=user,
        defaults={'phone': phone, 'subject': subject, 'salary': salary}
    )
    teachers.append(t)
    print(f"  ✅ O'qituvchi: {name}")

# Guruhlar
groups_data = [
    ('Python — A1', teachers[0], [1, 3, 5], '14:00', '16:00', 500000),
    ('Python — A2', teachers[0], [1, 3, 5], '16:00', '18:00', 600000),
    ('Web Design',  teachers[1], [2, 4],    '10:00', '12:00', 450000),
    ('English B1',  teachers[2], [1, 2, 3, 4, 5], '18:00', '20:00', 350000),
]
groups = []
for name, teacher, days, start, end, fee in groups_data:
    g, created = Group.objects.get_or_create(
        name=name,
        defaults={
            'teacher':     teacher,
            'monthly_fee': fee,
            'start_date':  date(2025, 1, 1),
            'start_time':  start,
            'end_time':    end,
        }
    )
    if created:
        for d in days:
            LessonSchedule.objects.get_or_create(group=g, day_of_week=d)
    groups.append(g)
    print(f"  ✅ Guruh: {name}")

# O'quvchilar
students_data = [
    ('Asilbek Mirzayev',  '+998900000001', '+998901111001', groups[0]),
    ('Zulfiya Karimova',  '+998900000002', '+998901111002', groups[2]),
    ('Rustam Toshmatov',  '+998900000003', '+998901111003', groups[3]),
    ('Bobur Normatov',    '+998900000004', '+998901111004', groups[0]),
    ('Malika Umarova',    '+998900000005', '+998901111005', groups[2]),
    ('Sherzod Yusupov',   '+998900000006', '+998901111006', groups[1]),
    ('Dilorom Hasanova',  '+998900000007', '+998901111007', groups[3]),
    ('Nodir Rahimov',     '+998900000008', '+998901111008', groups[1]),
]
students = []
for full_name, phone, parent_phone, group in students_data:
    user, created = User.objects.get_or_create(
        phone=phone,
        defaults={'full_name': full_name, 'role': User.Role.STUDENT}
    )
    if created:
        user.set_password('erp12345')
        user.save()
    s, _ = Student.objects.get_or_create(
        user=user,
        defaults={'phone': phone, 'parent_phone': parent_phone, 'group': group}
    )
    students.append(s)
    print(f"  ✅ O'quvchi: {full_name}")

# Davomat (so'nggi 20 kun)
admin_user = User.objects.filter(is_superuser=True).first()
statuses   = ['present', 'present', 'present', 'absent', 'late']
for student in students:
    for i in range(20):
        d = date.today() - timedelta(days=i)
        Attendance.objects.get_or_create(
            student=student,
            group=student.group,
            date=d,
            defaults={
                'status':    random.choice(statuses),
                'marked_by': admin_user
            }
        )

# To'lovlar (so'nggi 3 oy)
today = date.today()
for student in students:
    for i in range(3):
        m = today.month - i if today.month - i > 0 else today.month - i + 12
        y = today.year if today.month - i > 0 else today.year - 1
        fee = student.group.monthly_fee if student.group else 500000
        paid = random.choice([fee, fee // 2, 0])
        Payment.objects.get_or_create(
            student=student,
            group=student.group,
            month=m,
            year=y,
            defaults={
                'amount':     fee,
                'paid_amount': paid,
            }
        )

print("\n✅ Namuna ma'lumotlar yaratildi!")
print("🔑 Barcha parollar: erp12345")
