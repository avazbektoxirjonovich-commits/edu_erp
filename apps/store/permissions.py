from rest_framework.permissions import SAFE_METHODS, BasePermission


class CanViewStore(BasePermission):
    """Do'konni ko'rish — Student, Teacher, Admin, Developer. Finance/Parent kirmaydi."""
    message = "Bu bo'limni ko'rish uchun ruxsat yo'q"

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (
            u.is_student or u.is_teacher or u.is_admin or u.is_developer
        ))


class IsStoreManager(BasePermission):
    """Do'konni boshqarish (buyum qo'shish/tahrirlash, so'rovlarni tasdiqlash/rad etish) — faqat Admin/Developer."""
    message = "Bu amal uchun administrator yoki dasturchi huquqi kerak"

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_admin or u.is_developer))


class IsStudentOrStoreManager(BasePermission):
    """Xarid so'rovlari/tranzaksiyalar — o'quvchi (faqat o'ziniki) yoki Admin/Developer (hammasi)."""
    message = "Bu bo'limga kirish uchun ruxsat yo'q"

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_student or u.is_admin or u.is_developer))


class StoreItemPermission(BasePermission):
    """GET — CanViewStore (student/teacher/admin/developer); yozish — faqat Admin/Developer."""
    message = "Bu amal uchun administrator yoki dasturchi huquqi kerak"

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return u.is_student or u.is_teacher or u.is_admin or u.is_developer
        return u.is_admin or u.is_developer
