from rest_framework.permissions import BasePermission, SAFE_METHODS


def _is_teacher_or_staff(user):
    if not (user and user.is_authenticated):
        return False
    return user.role == 'teacher' or user.is_staff_level


class IsTeacherOrStaff(BasePermission):
    """Faqat o'qituvchi yoki admin/developer kira oladi."""

    def has_permission(self, request, view):
        return _is_teacher_or_staff(request.user)


# ZUKKO manbada IsTeacherOrAssistant deb nomlangan edi — ERP'da 'assistant' roli
# yo'q, shu sababli nom saqlanadi (urls/views moslik uchun) lekin mantiqi
# IsTeacherOrStaff bilan bir xil.
IsTeacherOrAssistant = IsTeacherOrStaff


class IsTeacherOrReadOnly(BasePermission):
    """Hamma o'qiy oladi, faqat o'qituvchi yoki staff yoza oladi."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return _is_teacher_or_staff(user)
