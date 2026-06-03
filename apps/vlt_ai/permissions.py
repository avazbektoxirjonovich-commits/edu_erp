"""
VLT AI — Permission helpers
============================
Permissions live in CODE, never in the LLM prompt.
user_can() is the single source of truth for VLT AI access control.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.accounts.models import User

# Maps role → set of VLT AI permission codes
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "developer": {
        "attendance.view_any",
        "attendance.view_own",
        "attendance.view_self",
        "students.view_any",
        "students.view_self",
        "groups.view_any",
        "groups.view_own",
        "teachers.view_any",
        "payments.view_any",
        "reports.view",
    },
    "admin": {
        "attendance.view_any",
        "attendance.view_own",
        "students.view_any",
        "groups.view_any",
        "groups.view_own",
        "teachers.view_any",
        "payments.view_any",
        "reports.view",
    },
    "teacher": {
        "attendance.view_own",
        "groups.view_own",
    },
    "student": {
        "attendance.view_self",
        "students.view_self",
    },
    "parent": {
        "students.view_self",
    },
}


def user_can(user: User, permission_code: str) -> bool:
    """Return True if the user holds the given VLT AI permission code.

    Developer / superuser always passes. All other roles are checked against
    ROLE_PERMISSIONS — never against the LLM prompt.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    role: str = getattr(user, "role", "") or ""
    if role == "developer":
        return True
    return permission_code in ROLE_PERMISSIONS.get(role, set())
