from rest_framework.permissions import BasePermission

from apps.users.roles import is_human_rater


class IsResearcher(BasePermission):
    """Researchers are staff users who can view responses and apply ratings."""

    def has_permission(self, request, _view):
        return bool(request.user and request.user.is_staff)


class IsStudyManager(BasePermission):
    """Staff researcher who is not restricted to blinded human rating."""

    def has_permission(self, request, _view):
        return bool(
            request.user
            and request.user.is_staff
            and not is_human_rater(request.user)
        )
