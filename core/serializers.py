"""
WorkHub Core Serializers
Covers all models with appropriate read/write handling.
"""
import secrets
import string
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.response import Response
from rest_framework import status
from .models import (
    Department, Project, Task, Event, Meeting,
    Message, Notification, SystemSettings
)

User = get_user_model()

PDF_CONTENT_TYPE = 'application/pdf'


class DepartmentCustomField(serializers.PrimaryKeyRelatedField):
    def to_internal_value(self, data):
        if data is None or data == '':
            return None
        
        # If numeric, treat it as primary key
        if isinstance(data, int) or (isinstance(data, str) and data.isdigit()):
            try:
                return self.get_queryset().get(pk=int(data))
            except (Department.DoesNotExist, ValueError, TypeError):
                raise serializers.ValidationError(f"Department with ID {data} does not exist.")
        
        # If it's a string name, get or create department by name
        if isinstance(data, str):
            dept, _ = Department.objects.get_or_create(name=data)
            return dept
            
        raise serializers.ValidationError("Invalid department input.")


# ──────────────────────────────────────────────
# Auth: Custom Token Pair (includes user object in response)
# ──────────────────────────────────────────────
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Returns access/refresh tokens + full user details."""

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data['user'] = {
            'id': user.id,
            'email': user.email,
            'full_name': user.full_name,
            'role': user.role,
            'status': user.status,
            'is_first_login': user.is_first_login,
            'avatar_url': user.get_avatar_url(),
            'department': user.department.name if user.department else '',
            'department_id': user.department.id if user.department else None,
        }
        return data


# ──────────────────────────────────────────────
# Department
# ──────────────────────────────────────────────
class DepartmentSerializer(serializers.ModelSerializer):
    lead_manager_name = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ['id', 'name', 'lead_manager', 'lead_manager_name', 'headcount', 'member_count']

    def get_lead_manager_name(self, obj):
        return obj.lead_manager.full_name if obj.lead_manager else ''

    def get_member_count(self, obj):
        return obj.members.count()


# ──────────────────────────────────────────────
# User / Employee
# ──────────────────────────────────────────────
class UserSerializer(serializers.ModelSerializer):
    department = DepartmentCustomField(queryset=Department.objects.all(), required=False, allow_null=True)
    department_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    team_lead_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'role', 'department',
            'department_name', 'team_lead', 'team_lead_name',
            'status', 'avatar_url', 'is_first_login', 'date_joined'
        ]
        read_only_fields = ['is_first_login', 'date_joined']

    def get_department_name(self, obj):
        return obj.department.name if obj.department else ''

    def get_avatar_url(self, obj):
        return obj.get_avatar_url()

    def get_team_lead_name(self, obj):
        return obj.team_lead.full_name if obj.team_lead else ''


class UserCreateSerializer(serializers.ModelSerializer):
    """Admin-only: create employee with auto-generated password sent via email."""
    department = DepartmentCustomField(queryset=Department.objects.all(), required=False, allow_null=True)
    team_lead = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['full_name', 'email', 'role', 'department', 'team_lead', 'status']

    def create(self, validated_data):
        # Generate a secure random 12-char temporary password
        alphabet = string.ascii_letters + string.digits + '!@#$'
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))

        role = validated_data.get('role', 'employee')
        team_lead = validated_data.get('team_lead')
        
        # If the user is a manager, default their team_lead to the admin (ID 1)
        if role == 'manager':
            try:
                team_lead = User.objects.get(pk=1)
            except User.DoesNotExist:
                team_lead = User.objects.filter(role='admin').first()

        user = User.objects.create_user(
            email=validated_data['email'],
            password=temp_password,
            full_name=validated_data['full_name'],
            role=role,
            department=validated_data.get('department'),
            team_lead=team_lead,
            status=validated_data.get('status', 'Active'),
            is_first_login=True,
        )

        # Email the temporary password to the employee's inbox.
        try:
            send_mail(
                subject='Welcome to WorkHub - Your Account Credentials',
                message=(
                    f"Hello {user.full_name},\n\n"
                    f"Your WorkHub account has been created by your administrator.\n\n"
                    f"Login URL: http://localhost:5500/FrontEnd/login.html\n"
                    f"Email: {user.email}\n"
                    f"Temporary Password: {temp_password}\n\n"
                    f"IMPORTANT: You will be asked to set a new password on first login.\n\n"
                    f"Best regards,\nWorkHub System"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            return Response({
                "message": "Employee created and credentials emailed successfully"
            }, status=201)
        except Exception as e:
            return Response({
                "error": "Employee created but email failed",
                "details": str(e)
            }, status=500)


class UserUpdateSerializer(serializers.ModelSerializer):
    department = DepartmentCustomField(queryset=Department.objects.all(), required=False, allow_null=True)
    team_lead = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['full_name', 'email', 'role', 'department', 'team_lead', 'status', 'avatar_url']


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['full_name', 'email']


# ──────────────────────────────────────────────
# Project
# ──────────────────────────────────────────────
class ProjectSerializer(serializers.ModelSerializer):
    lead_manager_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    original_document_url = serializers.SerializerMethodField()
    original_document_name = serializers.SerializerMethodField()
    preview_document_url = serializers.SerializerMethodField()
    preview_document_name = serializers.SerializerMethodField()
    project_document = serializers.FileField(
        source='original_document',
        required=False,
        allow_null=True,
        write_only=True
    )
    project_document_url = serializers.SerializerMethodField()
    project_document_name = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'lead_manager', 'lead_manager_name',
            'department', 'department_name', 'status', 'progress',
            'original_document', 'original_document_url', 'original_document_name',
            'preview_document', 'preview_document_url', 'preview_document_name',
            'project_document', 'project_document_url', 'project_document_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['preview_document']

    def get_lead_manager_name(self, obj):
        return obj.lead_manager.full_name if obj.lead_manager else ''

    def get_department_name(self, obj):
        return obj.department.name if obj.department else ''

    def _absolute_file_url(self, file_field):
        if not file_field:
            return ''
        request = self.context.get('request')
        url = file_field.url
        return request.build_absolute_uri(url) if request else url

    def _file_name(self, file_field):
        if not file_field:
            return ''
        return file_field.name.split('/')[-1]

    def get_original_document_url(self, obj):
        return self._absolute_file_url(obj.original_document)

    def get_original_document_name(self, obj):
        return self._file_name(obj.original_document)

    def get_preview_document_url(self, obj):
        return self.get_original_document_url(obj)

    def get_preview_document_name(self, obj):
        return self.get_original_document_name(obj)

    def get_project_document_url(self, obj):
        return self.get_original_document_url(obj)

    def get_project_document_name(self, obj):
        return self.get_original_document_name(obj)

    def validate_original_document(self, value):
        if value:
            ext = Path(value.name or '').suffix.lower()
            content_type = getattr(value, 'content_type', '')
            if ext != '.pdf':
                raise serializers.ValidationError('Only PDF files are allowed.')
            if content_type != PDF_CONTENT_TYPE:
                raise serializers.ValidationError('Only application/pdf files are allowed.')
        return value

    def validate(self, attrs):
        document = attrs.get('original_document')
        if document:
            self.validate_original_document(document)
        return attrs

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)

# # ──────────────────────────────────────────────
# # Task
# # ──────────────────────────────────────────────
class TaskSerializer(serializers.ModelSerializer):
    assignee_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    assignee_avatar = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'project', 'project_name', 'department',
            'department_name', 'priority', 'status',
            'assignee', 'assignee_name', 'assignee_avatar',
            'report', 'proceed_flag',
            'created_at', 'updated_at'
        ]

    def get_assignee_name(self, obj):
        return obj.assignee.full_name if obj.assignee else 'Unassigned'

    def get_assignee_avatar(self, obj):
        return obj.assignee.get_avatar_url() if obj.assignee else ''

    def get_project_name(self, obj):
        return obj.project.name if obj.project else ''

    def get_department_name(self, obj):
        return obj.department.name if obj.department else ''




# ──────────────────────────────────────────────
# Event (Calendar)
# ──────────────────────────────────────────────
class EventSerializer(serializers.ModelSerializer):
    creator_name = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'date', 'time', 'category',
            'description', 'creator', 'creator_name', 'created_at'
        ]
        read_only_fields = ['creator', 'created_at']

    def get_creator_name(self, obj):
        return obj.creator.full_name if obj.creator else ''

    def create(self, validated_data):
        validated_data['creator'] = self.context['request'].user
        return super().create(validated_data)


# ──────────────────────────────────────────────
# Meeting
# ──────────────────────────────────────────────
# class MeetingSerializer(serializers.ModelSerializer):
#     creator_name = serializers.SerializerMethodField()

#     class Meta:
#         model = Meeting
#         fields = [
#             'id', 'title', 'date', 'time', 'duration',
#             'platform', 'agenda', 'status', 'creator', 'creator_name', 'created_at'
#         ]
#         read_only_fields = ['creator', 'created_at']

#     def get_creator_name(self, obj):
#         return obj.creator.full_name if obj.creator else ''

#     def create(self, validated_data):
#         validated_data['creator'] = self.context['request'].user
#         return super().create(validated_data)
# ──────────────────────────────────────────────
# Meeting
# ──────────────────────────────────────────────
class MeetingSerializer(serializers.ModelSerializer):
    creator_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()
    participant_names = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'date', 'time', 'duration', 'platform',
            'room_name', 'agenda', 'status',
            'project', 'project_name',
            'creator', 'creator_name',
            'participants', 'participant_names',
            'created_at'
        ]
        read_only_fields = ['creator', 'room_name', 'created_at']

    def get_creator_name(self, obj):
        return obj.creator.full_name if obj.creator else ''

    def get_project_name(self, obj):
        return obj.project.name if obj.project else ''

    def get_participant_names(self, obj):
        return [p.full_name for p in obj.participants.all()]

    def create(self, validated_data):
        validated_data['creator'] = self.context['request'].user
        return super().create(validated_data)


class MeetingJoinSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meeting
        fields = ['id', 'title', 'room_name', 'status']

# ──────────────────────────────────────────────
# Message (Chat)
# ──────────────────────────────────────────────
class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    sender_avatar = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'sender_name', 'sender_avatar',
            'receiver', 'room', 'text', 'timestamp', 'is_read'
        ]
        read_only_fields = ['sender', 'timestamp']

    def get_sender_name(self, obj):
        return obj.sender.full_name

    def get_sender_avatar(self, obj):
        return obj.sender.get_avatar_url()

    def create(self, validated_data):
        validated_data['sender'] = self.context['request'].user
        return super().create(validated_data)


# ──────────────────────────────────────────────
# Notification
# ──────────────────────────────────────────────
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'text', 'timestamp', 'is_read', 'icon', 'color']
        read_only_fields = ['timestamp']


# ──────────────────────────────────────────────
# System Settings
# ──────────────────────────────────────────────
class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        fields = [
            'workspace_title', 'accent_color', 'scale_ratio',
            'allow_guest_registration', 'employees_can_create_tasks', 'require_mfa'
        ]


# ──────────────────────────────────────────────
# Change Password
# ──────────────────────────────────────────────
class ChangePasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(min_length=6, write_only=True)
    confirm_password = serializers.CharField(min_length=6, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': 'Passwords do not match.'}
            )
        return attrs
