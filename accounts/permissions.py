from rest_framework.permissions import BasePermission


class IsVerified(BasePermission):
    message = 'A verified account is required.'

    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.verified)


class IsManager(IsVerified):
    message = 'HR or Admin access is required.'

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.can_manage_candidates
