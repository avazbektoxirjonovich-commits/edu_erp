from rest_framework.permissions import BasePermission


class IsDeveloperRole(BasePermission):
    """Error Monitor is a Developer Panel feature — developer role or
    superuser only. Not admin, not finance, not teacher."""
    message = "Bu bo'lim faqat dasturchi uchun"

    def has_permission(self, request, view):
        u = request.user
        return bool(
            u and u.is_authenticated and
            (getattr(u, 'is_developer', False) or u.is_superuser)
        )
