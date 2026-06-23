"""
WorkHub Core Models
All application models: User, Department, Project, Task,
Event, Meeting, Message, Notification, SystemSettings
"""
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
import uuid


# ──────────────────────────────────────────────
# Department  (defined before User to allow FK)
# ──────────────────────────────────────────────
class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    # lead_manager FK references User via string to avoid circular import
    lead_manager = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='led_departments'
    )
    headcount = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# ──────────────────────────────────────────────
# Custom User Manager
# ──────────────────────────────────────────────
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_first_login', False)
        return self.create_user(email, password, **extra_fields)


# ──────────────────────────────────────────────
# Custom User Model
# ──────────────────────────────────────────────
class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('employee', 'Employee'),
    ]
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('On Leave', 'On Leave'),
    ]

    full_name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members'
    )
    team_lead = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_members'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    avatar_url = models.URLField(blank=True, default='')
    is_first_login = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    objects = CustomUserManager()

    class Meta:
        ordering = ['full_name']

    def __str__(self):
        return f"{self.full_name} ({self.email})"

    def get_avatar_url(self):
        """Return avatar URL, falling back to ui-avatars.com if not set."""
        if self.avatar_url:
            return self.avatar_url
        name = (self.full_name or self.email.split('@')[0]).replace(' ', '+')
        return f"https://ui-avatars.com/api/?name={name}&background=6366f1&color=fff"


# ──────────────────────────────────────────────
# Project
# ──────────────────────────────────────────────
class Project(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
    ]

    name = models.CharField(max_length=200)
    lead_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_projects'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='projects'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    progress = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


# ──────────────────────────────────────────────
# Task
# ──────────────────────────────────────────────
class Task(models.Model):
    PRIORITY_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    STATUS_CHOICES = [
        ('todo', 'To Do'),
        ('progress', 'In Progress'),
        ('review', 'In Review'),
        ('done', 'Completed'),
    ]

    title = models.CharField(max_length=300)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tasks'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='todo')
    assignee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks'
    )
    report = models.TextField(blank=True, default='')
    proceed_flag = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


# ──────────────────────────────────────────────
# Event (Calendar)
# ──────────────────────────────────────────────
class Event(models.Model):
    CATEGORY_CHOICES = [
        ('sprint', 'Sprint Meeting'),
        ('client', 'Client Sync'),
        ('review', 'Code Review'),
        ('social', 'Team Social'),
    ]

    title = models.CharField(max_length=200)
    date = models.DateField()
    time = models.TimeField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='sprint')
    description = models.TextField(blank=True, default='')
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_events'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'time']

    def __str__(self):
        return f"{self.title} ({self.date})"


# ──────────────────────────────────────────────
# Meeting
# ──────────────────────────────────────────────
# class Meeting(models.Model):
#     PLATFORM_CHOICES = [
#         ('Zoom', 'Zoom'),
#         ('MS Teams', 'MS Teams'),
#         ('Google Meet', 'Google Meet'),
#     ]
#     STATUS_CHOICES = [
#         ('upcoming', 'Upcoming'),
#         ('live', 'Live'),
#         ('ended', 'Ended'),
#     ]

#     title = models.CharField(max_length=200)
#     date = models.DateField()
#     time = models.TimeField()
#     duration = models.PositiveIntegerField(help_text='Duration in minutes', default=30)
#     platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='Zoom')
#     agenda = models.TextField(blank=True, default='')
#     status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='upcoming')
#     creator = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='created_meetings'
#     )
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         ordering = ['date', 'time']

#     def __str__(self):
#         return f"{self.title} ({self.date})"

# ──────────────────────────────────────────────
# Meeting
# ──────────────────────────────────────────────
import uuid

class Meeting(models.Model):
    PLATFORM_CHOICES = [
        ('Jitsi', 'Jitsi Meet'),
    ]
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('live', 'Live'),
        ('ended', 'Ended'),
        ('cancelled', 'Cancelled'),
    ]

    title = models.CharField(max_length=200)
    date = models.DateField()
    time = models.TimeField()
    duration = models.PositiveIntegerField(help_text='Duration in minutes', default=30)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='Jitsi')
    room_name = models.CharField(max_length=120, unique=True, editable=False, blank=True)
    agenda = models.TextField(blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='upcoming')

    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meetings'
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_meetings'
    )
    participants = models.ManyToManyField(
        User,
        related_name='meetings_invited',
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'time']

    def save(self, *args, **kwargs):
        if not self.room_name:
            self.room_name = f'workhub-{uuid.uuid4().hex[:12]}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.date})"
    

# ──────────────────────────────────────────────
# Message (Chat)
# ──────────────────────────────────────────────
class Message(models.Model):
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    receiver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_messages'
    )
    room = models.CharField(max_length=100, blank=True, default='general')
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender.full_name}: {self.text[:50]}"


# ──────────────────────────────────────────────
# Notification
# ──────────────────────────────────────────────
class Notification(models.Model):
    COLOR_CHOICES = [
        ('primary', 'Primary'),
        ('success', 'Success'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('danger', 'Danger'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    title = models.CharField(max_length=200, default='Notification')
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    icon = models.CharField(max_length=50, default='fa-bell')
    color = models.CharField(max_length=10, choices=COLOR_CHOICES, default='primary')

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.user.full_name}] {self.title}"


# ──────────────────────────────────────────────
# SystemSettings (Singleton)
# ──────────────────────────────────────────────
class SystemSettings(models.Model):
    workspace_title = models.CharField(max_length=100, default='WorkHub')
    accent_color = models.CharField(max_length=20, default='#6366f1')
    scale_ratio = models.FloatField(default=1.0)
    allow_guest_registration = models.BooleanField(default=False)
    employees_can_create_tasks = models.BooleanField(default=False)
    require_mfa = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'

    def save(self, *args, **kwargs):
        self.pk = 1  # Ensure only one row (singleton pattern)
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"System Settings — {self.workspace_title}"
