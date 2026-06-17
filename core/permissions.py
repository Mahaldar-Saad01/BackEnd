"""
Custom permission classes for role-based access control.
Roles: admin > manager > employee
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdmin(BasePermission):
    """Only admin users have access."""
    message = 'Admin access required.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'admin')


class IsAdminOrManager(BasePermission):
    """Admin and Manager users have access."""
    message = 'Admin or Manager access required.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['admin', 'manager']
        )


class IsAdminOrManagerOrReadOnly(BasePermission):
    """Admin/Manager for write ops; any authenticated user for read ops."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['admin', 'manager']
        )


class IsOwnerOrAdmin(BasePermission):
    """Object-level: owner or admin only."""
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        # Support User objects and objects with a .user FK
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return obj == request.user
