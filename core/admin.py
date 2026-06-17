"""
WorkHub Django Admin Configuration
Registers all core models in the Django Admin interface.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Department, Project, Task,
    Event, Meeting, Message, Notification, SystemSettings
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'full_name', 'role', 'department', 'status', 'is_first_login', 'is_active')
    list_filter = ('role', 'status', 'department', 'is_active')
    search_fields = ('email', 'full_name')
    ordering = ('full_name',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'avatar_url')}),
        ('Role & Department', {'fields': ('role', 'department', 'status')}),
        ('Flags', {'fields': ('is_first_login', 'is_active', 'is_staff', 'is_superuser')}),
        ('Permissions', {'fields': ('groups', 'user_permissions')}),
        ('Dates', {'fields': ('date_joined', 'last_login')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'role', 'department', 'password1', 'password2'),
        }),
    )
    readonly_fields = ('date_joined', 'last_login')


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'lead_manager', 'headcount')
    search_fields = ('name',)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'lead_manager', 'department', 'status', 'progress')
    list_filter = ('status', 'department')
    search_fields = ('name',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'department', 'priority', 'status', 'assignee')
    list_filter = ('priority', 'status', 'department')
    search_fields = ('title',)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'time', 'category', 'creator')
    list_filter = ('category',)


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'time', 'platform', 'status', 'creator')
    list_filter = ('platform', 'status')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'room', 'timestamp', 'is_read')
    list_filter = ('room', 'is_read')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'timestamp', 'is_read', 'color')
    list_filter = ('is_read', 'color')


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('workspace_title', 'accent_color', 'allow_guest_registration')

    def has_add_permission(self, request):
        # Only one settings row allowed
        return not SystemSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
