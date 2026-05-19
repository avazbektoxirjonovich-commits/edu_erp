"""
ACCOUNTS — Ruxsat tizimi (Permissions)
=========================================
Rollar matritsasi:
  developer : Hammasiga ruxsat (texnik xodim)
  admin     : Tizim boshqaruvi (foydalanuvchi, to'lov, guruh CRUD)
  teacher   : O'z guruhlari: davomat, vazifa yaratish, baholash
  student   : Faqat o'z ma'lumotlari, vazifa topshirish
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS


# ── Asosiy yordamchilar ────────────────────────────────────────
def _is_staff(user):
    return user and user.is_authenticated and user.is_staff_level


# ── 1. Faqat developer + admin ────────────────────────────────
class IsStaffLevel(BasePermission):
    """Developer yoki Admin — tizim boshqaruvi"""
    message = "Bu amal uchun administrator yoki dasturchi huquqi kerak"

    def has_permission(self, request, view):
        return _is_staff(request.user)


# ── 2. Faqat admin ────────────────────────────────────────────
class IsAdmin(BasePermission):
    """Faqat administrator"""
    message = "Bu amal uchun administrator huquqi kerak"

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_admin or request.user.is_developer)
        )


# ── 3. Faqat o'qituvchi ───────────────────────────────────────
class IsTeacher(BasePermission):
    """Faqat o'qituvchi"""
    message = "Bu amal uchun o'qituvchi huquqi kerak"

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_teacher
        )


# ── 4. Faqat o'quvchi ────────────────────────────────────────
class IsStudent(BasePermission):
    """Faqat o'quvchi"""
    message = "Bu amal uchun o'quvchi huquqi kerak"

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_student
        )


# ── 5. Admin yoki o'qituvchi ─────────────────────────────────
class IsAdminOrTeacher(BasePermission):
    """Admin, Developer yoki O'qituvchi"""
    message = "Bu amal uchun admin yoki o'qituvchi huquqi kerak"

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_admin or
             request.user.is_teacher or
             request.user.is_developer)
        )


# ── 6. Admin yozadi, boshqalar o'qiydi ───────────────────────
class IsAdminOrReadOnly(BasePermission):
    """GET — barcha login qilganlar; POST/PUT/DELETE — faqat admin/developer"""
    message = "O'zgartirish uchun administrator huquqi kerak"

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_admin or request.user.is_developer


# ── 7. Admin yozadi, teacher o'qiydi ─────────────────────────
class IsAdminWriteTeacherRead(BasePermission):
    """GET — admin+teacher; POST/PUT/DELETE — faqat admin/developer"""
    message = "O'zgartirish uchun administrator huquqi kerak"

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return (request.user.is_admin or
                    request.user.is_teacher or
                    request.user.is_developer)
        return request.user.is_admin or request.user.is_developer


# ── 8. O'zining ob'ekti yoki admin ───────────────────────────
class IsOwnerOrAdmin(BasePermission):
    """Faqat o'z ma'lumoti yoki admin/developer"""

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff_level:
            return True
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return obj == request.user


# ── 9. Davomat — teacher faqat o'z guruhi ────────────────────
class IsAdminOrTeacherOwn(BasePermission):
    """
    Admin/Developer — har qanday guruh.
    Teacher — faqat o'z guruhlari.
    """
    message = "Siz faqat o'z guruhingiz davomatini boshqara olasiz"

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_admin or
             request.user.is_teacher or
             request.user.is_developer)
        )

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff_level:
            return True
        if request.user.is_teacher:
            teacher = getattr(request.user, 'teacher_profile', None)
            if not teacher:
                return False
            group = getattr(obj, 'group', None) or getattr(obj, 'assignment', None)
            if hasattr(group, 'teacher'):
                return group.teacher == teacher
        return False