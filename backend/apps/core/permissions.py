from rest_framework.permissions import BasePermission


class IsResearcher(BasePermission):
    """Researchers are staff users who can view responses and apply ratings."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)
