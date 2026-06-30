"""
WorkHub Core Views
All API endpoints: Auth, Employees, Departments, Projects, Tasks,
Events, Meetings, Chat, Notifications, Dashboard, Settings.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count, Q
from django.core.files.storage import default_storage
from django.core.mail import send_mail
import random

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    Department, Project, Task, Event, Meeting,
    Message, Notification, SystemSettings
)
# from .serializers import (
#     CustomTokenObtainPairSerializer,
#     DepartmentSerializer,
#     UserSerializer, UserCreateSerializer, UserUpdateSerializer,
#     ProjectSerializer, TaskSerializer, EventSerializer,
#     MeetingSerializer, MessageSerializer, NotificationSerializer,
#     SystemSettingsSerializer, ChangePasswordSerializer
# )
from .serializers import (
    CustomTokenObtainPairSerializer,
    DepartmentSerializer,
    UserSerializer, UserCreateSerializer, UserUpdateSerializer, UserProfileUpdateSerializer,
    ProjectSerializer, TaskSerializer, EventSerializer,
    MeetingSerializer, MeetingJoinSerializer, MessageSerializer, NotificationSerializer,
    SystemSettingsSerializer, ChangePasswordSerializer
)
from .permissions import IsAdmin, IsAdminOrManager

User = get_user_model()


# ──────────────────────────────────────────────
# Auth Views
# ──────────────────────────────────────────────
class CustomTokenObtainPairView(TokenObtainPairView):
    """POST /api/auth/login/ — returns {access, refresh, user}"""
    serializer_class = CustomTokenObtainPairSerializer


class RegisterEmployeeView(generics.CreateAPIView):
    """POST /api/auth/register/ — Admin only. Auto-generates password & emails it."""
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = UserCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = UserSerializer(user).data
        email_sent = getattr(user, '_credentials_email_sent', False)
        data['credentials_email_sent'] = email_sent
        data['credential_delivery'] = 'email' if email_sent else 'manual'

        if not email_sent:
            data['temporary_password'] = getattr(user, '_temporary_password', '')
            data['detail'] = (
                'User registered, but WorkHub could not send the credentials email. '
                'Share the temporary password manually.'
            )

        return Response(data, status=status.HTTP_201_CREATED)


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PUT /api/users/me/ — current authenticated user profile"""
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = UserProfileUpdateSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data)


class ChangePasswordView(APIView):
    """POST /api/auth/change-password/ — change own password (used on first-login)"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.is_first_login = False
            user.save()
            Notification.objects.create(
                user=user,
                title='Password changed',
                text='Your WorkHub password was changed successfully.',
                icon='fa-lock',
                color='success',
            )
            return Response({'detail': 'Password changed successfully.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordOtpRequestView(APIView):
    """POST /api/auth/password-otp/request/ — send password-change OTP to user's email."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        otp = ''.join(str(random.SystemRandom().randint(0, 9)) for _ in range(6))
        cache.set(f'password_change_otp:{user.id}', otp, timeout=600)

        send_mail(
            subject='WorkHub password change OTP',
            message=(
                f"Hello {user.full_name},\n\n"
                f"Your WorkHub password change OTP is: {otp}\n"
                f"This code expires in 10 minutes.\n\n"
                f"If you did not request this, ignore this email."
            ),
            from_email=None,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response({'detail': 'OTP sent to your registered email.'})


class PasswordOtpConfirmView(APIView):
    """POST /api/auth/password-otp/confirm/ — verify OTP and update password."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        otp = str(request.data.get('otp', '')).strip()
        new_password = request.data.get('new_password', '')
        confirm_password = request.data.get('confirm_password', '')

        serializer = ChangePasswordSerializer(data={
            'new_password': new_password,
            'confirm_password': confirm_password,
        })
        serializer.is_valid(raise_exception=True)

        if not otp:
            return Response({'otp': 'OTP is required.'}, status=status.HTTP_400_BAD_REQUEST)

        cache_key = f'password_change_otp:{request.user.id}'
        saved_otp = cache.get(cache_key)
        if not saved_otp:
            return Response({'otp': 'OTP expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)
        if otp != saved_otp:
            return Response({'otp': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.is_first_login = False
        user.save()
        cache.delete(cache_key)
        Notification.objects.create(
            user=user,
            title='Password changed',
            text='Your WorkHub password was changed successfully after OTP verification.',
            icon='fa-lock',
            color='success',
        )

        return Response({'detail': 'Password changed successfully.'})


class LogoutView(APIView):
    """POST /api/auth/logout/ — blacklist refresh token"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'detail': 'Logged out successfully.'})
        except Exception:
            return Response(
                {'detail': 'Token is invalid or already expired.'},
                status=status.HTTP_400_BAD_REQUEST
            )


# ──────────────────────────────────────────────
# Employee ViewSet
# ──────────────────────────────────────────────
class EmployeeViewSet(viewsets.ModelViewSet):
    """
    GET    /api/employees/       — list (role-scoped)
    POST   /api/employees/       — create (admin only, use /api/auth/register/ instead)
    GET    /api/employees/<id>/  — retrieve
    PUT    /api/employees/<id>/  — update (admin/manager)
    DELETE /api/employees/<id>/  — destroy (admin only)
    """
    serializer_class = UserSerializer

    def get_queryset(self):
        user = self.request.user
        qs = User.objects.select_related('department')
        if user.role == 'admin':
            return qs.all()
        elif user.role == 'manager':
            return qs.filter(department=user.department)
        else:
            return qs.filter(id=user.id)

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated(), IsAdmin()]
        if self.action in ['create', 'update', 'partial_update']:
            return [IsAuthenticated(), IsAdminOrManager()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['patch'], url_path='toggle-status')
    def toggle_status(self, request, pk=None):
        """PATCH /api/employees/<id>/toggle-status/"""
        emp = self.get_object()
        emp.status = 'On Leave' if emp.status == 'Active' else 'Active'
        emp.save()
        return Response(UserSerializer(emp).data)

    @action(detail=False, methods=['get'], url_path='chat-list')
    def chat_list(self, request):
        """GET /api/employees/chat-list/"""
        users = User.objects.filter(is_active=True).select_related('department').order_by('full_name')
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


# ──────────────────────────────────────────────
# Department ViewSet
# ──────────────────────────────────────────────
class DepartmentViewSet(viewsets.ModelViewSet):
    """
    GET    /api/departments/       — list all
    POST   /api/departments/       — create (admin only)
    GET    /api/departments/<id>/  — retrieve
    PUT    /api/departments/<id>/  — update (admin only)
    DELETE /api/departments/<id>/  — destroy (admin only)
    """
    queryset = Department.objects.select_related('lead_manager').all()
    serializer_class = DepartmentSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated()]


# ──────────────────────────────────────────────
# Project ViewSet
# ──────────────────────────────────────────────
class ProjectViewSet(viewsets.ModelViewSet):
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    """
    GET    /api/projects/       — list (role-scoped)
    POST   /api/projects/       — create (admin/manager)
    PUT    /api/projects/<id>/  — update
    DELETE /api/projects/<id>/  — destroy (admin/manager)
    """
    serializer_class = ProjectSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Project.objects.select_related('lead_manager', 'department')
        if user.role == 'admin':
            return qs.all()
        elif user.role == 'manager':
            return qs.filter(lead_manager=user)
        else:
            # Employees see projects of their assigned tasks
            task_project_ids = Task.objects.filter(
                assignee=user
            ).values_list('project_id', flat=True).distinct()
            return qs.filter(id__in=task_project_ids)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminOrManager()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == 'manager':
            # Force status to Pending for manager-created projects, progress to 0
            project = serializer.save(lead_manager=user, status='Pending', progress=0)
            
            # Create a notification for admins
            admins = User.objects.filter(role='admin')
            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    title="Project Approval Requested",
                    text=f"Manager {user.full_name} has requested approval for project '{project.name}'.",
                    icon="fa-folder-open",
                    color="warning"
                )
        else:
            serializer.save()

    def perform_update(self, serializer):
        old_instance = self.get_object()
        old_status = old_instance.status
        user = self.request.user
        
        # Enforce that managers cannot bypass approval by updating status to Active
        if user.role == 'manager' and old_status == 'Pending':
            if serializer.validated_data.get('status') == 'Active':
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Managers cannot approve projects. Admin approval is required.")

        project = serializer.save()
        
        # If admin approved a Pending project (status changed from Pending to Active)
        if old_status == 'Pending' and project.status == 'Active':
            if project.lead_manager:
                Notification.objects.create(
                    user=project.lead_manager,
                    title="Project Approved",
                    text=f"Your project '{project.name}' has been approved and is now live.",
                    icon="fa-circle-check",
                    color="success"
                )

    def perform_destroy(self, instance):
        if instance.status == 'Pending' and instance.lead_manager:
            Notification.objects.create(
                user=instance.lead_manager,
                title="Project Rejected",
                text=f"Your project '{instance.name}' request has been rejected by the Admin.",
                icon="fa-circle-xmark",
                color="danger"
            )
        instance.delete()


# ──────────────────────────────────────────────
# Task ViewSet
# ──────────────────────────────────────────────
class TaskViewSet(viewsets.ModelViewSet):
    """
    GET    /api/tasks/       — list (role-scoped)
    POST   /api/tasks/       — create (admin/manager)
    PATCH  /api/tasks/<id>/  — partial update (employee: status only)
    DELETE /api/tasks/<id>/  — destroy (admin/manager)
    """
    serializer_class = TaskSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Task.objects.select_related('project', 'department', 'assignee')
        if user.role == 'admin':
            return qs.all()
        elif user.role == 'manager':
            managed_ids = Project.objects.filter(
                lead_manager=user
            ).values_list('id', flat=True)
            return qs.filter(project_id__in=managed_ids)
        else:
            return qs.filter(assignee=user)

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [IsAuthenticated(), IsAdminOrManager()]
        if self.action in ['update', 'partial_update']:
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user
        # Employees may only update their own task's status and report
        if user.role == 'employee':
            if instance.assignee != user:
                return Response(
                    {'detail': 'You can only update your own tasks.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            allowed = {'status', 'report'}
            if not set(request.data.keys()).issubset(allowed):
                return Response(
                    {'detail': 'Employees may only update task status and report.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        # Managers may only update tasks in their projects
        if user.role == 'manager' and instance.project:
            if instance.project.lead_manager != user:
                return Response(
                    {'detail': 'You can only update tasks in your projects.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        old_status = instance.status
        old_proceed = instance.proceed_flag

        response = super().partial_update(request, *args, **kwargs)
        
        instance.refresh_from_db()
        
        # Trigger notifications
        if old_status != 'review' and instance.status == 'review':
            # Identify the manager who assigned the task / project lead manager
            manager = None
            if instance.project and instance.project.lead_manager:
                manager = instance.project.lead_manager
            elif instance.assignee and instance.assignee.team_lead:
                manager = instance.assignee.team_lead
            
            if manager:
                Notification.objects.create(
                    user=manager,
                    title="Task Review Requested",
                    text=f"Employee {user.full_name} submitted task '{instance.title}' for review.",
                    icon="fa-eye",
                    color="warning"
                )

        if not old_proceed and instance.proceed_flag:
            if instance.assignee:
                Notification.objects.create(
                    user=instance.assignee,
                    title="Task Approved",
                    text=f"Manager {user.full_name} raised proceed flag for task '{instance.title}'.",
                    icon="fa-circle-check",
                    color="success"
                )

        return response


# ──────────────────────────────────────────────
# Event (Calendar) ViewSet
# ──────────────────────────────────────────────
class EventViewSet(viewsets.ModelViewSet):
    """GET/POST /api/calendar/events/"""
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Event.objects.select_related('creator').filter(creator=self.request.user)

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Only creator or admin can delete
        if request.user.role != 'admin' and instance.creator != request.user:
            return Response(
                {'detail': 'Only the creator or admin can delete this event.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)


# ──────────────────────────────────────────────
# Meeting ViewSet
# ──────────────────────────────────────────────
# class MeetingViewSet(viewsets.ModelViewSet):
#     """GET/POST /api/meetings/"""
#     serializer_class = MeetingSerializer
#     permission_classes = [IsAuthenticated]

#     def get_queryset(self):
#         return Meeting.objects.select_related('creator').all()

#     def perform_create(self, serializer):
#         serializer.save(creator=self.request.user)
# ──────────────────────────────────────────────
# Meeting ViewSet
# ──────────────────────────────────────────────
class MeetingViewSet(viewsets.ModelViewSet):
    """
    GET    /api/meetings/            — list (role-scoped)
    POST   /api/meetings/            — create (admin/manager only)
    GET    /api/meetings/<id>/       — retrieve
    PUT    /api/meetings/<id>/       — update (creator/admin only)
    DELETE /api/meetings/<id>/       — cancel (creator/admin only)
    GET    /api/meetings/<id>/join/  — get room info to launch Jitsi
    """
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Meeting.objects.select_related('creator', 'project').prefetch_related('participants')
        if user.role == 'admin':
            return qs.all()
        return qs.filter(
            Q(creator=user) | Q(participants=user)
        ).distinct()

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsAdminOrManager()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        meeting = serializer.save(creator=self.request.user)

        # Notify all participants
        participants = meeting.participants.all()
        for participant in participants:
            if participant != self.request.user:
                Notification.objects.create(
                    user=participant,
                    title="Meeting Invitation",
                    text=(
                        f"You have been invited to '{meeting.title}' "
                        f"on {meeting.date} at {meeting.time} "
                        f"by {self.request.user.full_name}."
                    ),
                    icon="fa-video",
                    color="info"
                )
    
    # def perform_update(self, serializer):
    #     meeting = self.get_object()
    #     user = self.request.user
    #     if user.role != 'admin' and meeting.creator != user:
    #         from rest_framework.exceptions import PermissionDenied
    #         raise PermissionDenied("Only the creator or admin can edit this meeting.")
    #     serializer.save()
    def perform_update(self, serializer):
    # Get old participants before save
        old_participant_ids = set(
            self.get_object().participants.values_list('id', flat=True)
        )

        meeting = serializer.save()

        # Find newly added participants
        new_participant_ids = set(
            meeting.participants.values_list('id', flat=True)
        )
        added_ids = new_participant_ids - old_participant_ids

        # Notify only newly added participants
        for participant in meeting.participants.filter(id__in=added_ids):
            if participant != self.request.user:
                Notification.objects.create(
                    user=participant,
                    title="Meeting Invitation",
                    text=(
                        f"You have been added to '{meeting.title}' "
                        f"on {meeting.date} at {meeting.time} "
                        f"by {self.request.user.full_name}."
                    ),
                    icon="fa-video",
                    color="info"
                )

    # def destroy(self, request, *args, **kwargs):
    #     meeting = self.get_object()
    #     if request.user.role != 'admin' and meeting.creator != request.user:
    #         return Response(
    #             {'detail': 'Only the creator or admin can cancel this meeting.'},
    #             status=status.HTTP_403_FORBIDDEN
    #         )
    #     meeting.status = 'cancelled'
    #     meeting.save()
    #     return Response({'detail': 'Meeting cancelled.'})
    def destroy(self, request, *args, **kwargs):
        meeting = self.get_object()

        # Only creator or admin can delete
        if request.user.role != 'admin' and meeting.creator != request.user:
            return Response(
                {'detail': 'Only the creator or admin can delete this meeting.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Notify participants that meeting was cancelled
        for participant in meeting.participants.all():
            if participant != request.user:
                Notification.objects.create(
                    user=participant,
                    title="Meeting Cancelled",
                    text=(
                        f"'{meeting.title}' scheduled on {meeting.date} "
                        f"at {meeting.time} has been cancelled by "
                        f"{request.user.full_name}."
                    ),
                    icon="fa-calendar-xmark",
                    color="danger"
                )

        meeting.delete()
        return Response(
            {'detail': 'Meeting deleted successfully.'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['get'], url_path='join')
    def join(self, request, pk=None):
        meeting = self.get_object()
        user = request.user

        is_participant = meeting.participants.filter(id=user.id).exists()
        is_creator = meeting.creator_id == user.id
        is_admin = user.role == 'admin'

        if not (is_participant or is_creator or is_admin):
            return Response(
                {'detail': 'You are not invited to this meeting.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if meeting.status == 'upcoming':
            meeting.status = 'live'
            meeting.save()

        serializer = MeetingJoinSerializer(meeting)
        return Response({
            **serializer.data,
            'display_name': user.full_name,
            'jitsi_domain': 'meet.jit.si'
        })

# ──────────────────────────────────────────────
# Message (Chat) ViewSet
# ──────────────────────────────────────────────
class MessageViewSet(viewsets.ModelViewSet):
    """GET/POST /api/chat/messages/?room=general"""
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        room = self.request.query_params.get('room', 'general')
        if room.startswith('dm_'):
            try:
                _, first_id, second_id = room.split('_', 2)
                participant_ids = {int(first_id), int(second_id)}
            except (ValueError, TypeError):
                return Message.objects.none()

            if self.request.user.id not in participant_ids:
                return Message.objects.none()

        return Message.objects.filter(room=room).select_related('sender', 'receiver')

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)

    @action(detail=False, methods=['get'], url_path='conversations')
    def conversations(self, request):
        """GET /api/chat/messages/conversations/"""
        user = request.user
        from django.db.models import Q, Count
        
        unread_counts = Message.objects.filter(
            receiver=user,
            is_read=False,
            room__startswith='dm_'
        ).values('sender_id').annotate(count=Count('id'))
        
        unread_map = {item['sender_id']: item['count'] for item in unread_counts}
        
        all_dms = Message.objects.filter(
            Q(sender=user) | Q(receiver=user)
        ).filter(room__startswith='dm_').values_list('sender_id', 'receiver_id')
        
        participant_ids = set()
        for s_id, r_id in all_dms:
            if s_id != user.id:
                participant_ids.add(s_id)
            if r_id and r_id != user.id:
                participant_ids.add(r_id)
                
        result = []
        for p_id in participant_ids:
            result.append({
                'user_id': p_id,
                'unread_count': unread_map.get(p_id, 0)
            })
            
        return Response(result)

    @action(detail=False, methods=['post'], url_path='mark-read')
    def mark_read(self, request):
        """POST /api/chat/messages/mark-read/"""
        room = request.data.get('room')
        if not room:
            return Response({'detail': 'Room is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        updated = Message.objects.filter(
            room=room,
            receiver=request.user,
            is_read=False
        ).update(is_read=True)
        
        return Response({'detail': f'{updated} message(s) marked as read.'})


# ──────────────────────────────────────────────
# Notification ViewSet
# ──────────────────────────────────────────────
class NotificationViewSet(viewsets.ModelViewSet):
    """
    GET   /api/notifications/                 — user's notifications
    PATCH /api/notifications/<id>/            — mark single read
    POST  /api/notifications/mark-all-read/   — mark all read
    DELETE /api/notifications/<id>/           — delete single
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'patch', 'delete', 'post', 'head', 'options']

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """POST /api/notifications/mark-all-read/"""
        updated = Notification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True)
        return Response({'detail': f'{updated} notification(s) marked as read.'})


# ──────────────────────────────────────────────
# Dashboard Stats
# ──────────────────────────────────────────────
class DashboardStatsView(APIView):
    """GET /api/dashboard/stats/ — role-scoped aggregated statistics"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role == 'admin':
            task_stats = Task.objects.aggregate(
                done=Count('id', filter=Q(status='done')),
                progress=Count('id', filter=Q(status='progress')),
                review=Count('id', filter=Q(status='review')),
                todo=Count('id', filter=Q(status='todo')),
            )

            project_stats = Project.objects.aggregate(
                completed=Count('id', filter=Q(status='Completed')),
                active=Count('id', filter=Q(status='Active')),
                pending=Count('id', filter=Q(status='Pending')),
            )

            dept_workload = list(
                Department.objects.annotate(task_count=Count('tasks'))
                .values('name', 'task_count')
            )

            return Response({
                'total_projects': Project.objects.count(),
                'total_tasks': Task.objects.count(),
                'total_departments': Department.objects.count(),
                'total_employees': User.objects.filter(is_active=True).count(),
                'pending_approvals': Project.objects.filter(status='Pending').count(),
                'task_stats': task_stats,
                'project_stats': project_stats,
                'dept_workload': dept_workload,
            })

        elif user.role == 'manager':
            my_projects = Project.objects.filter(lead_manager=user)
            project_ids = my_projects.values_list('id', flat=True)
            team_tasks = Task.objects.filter(project_id__in=project_ids)
            team_size = User.objects.filter(
                department=user.department
            ).exclude(role='admin').count()

            task_stats = team_tasks.aggregate(
                done=Count('id', filter=Q(status='done')),
                progress=Count('id', filter=Q(status='progress')),
                review=Count('id', filter=Q(status='review')),
                todo=Count('id', filter=Q(status='todo')),
            )

            return Response({
                'total_projects': my_projects.count(),
                'total_tasks': team_tasks.count(),
                'team_size': team_size,
                'reviews_pending': task_stats['review'],
                'task_stats': task_stats,
            })

        else:  # employee
            my_tasks = Task.objects.filter(assignee=user)
            my_project_ids = my_tasks.values_list(
                'project_id', flat=True
            ).distinct()

            task_stats = my_tasks.aggregate(
                done=Count('id', filter=Q(status='done')),
                progress=Count('id', filter=Q(status='progress')),
                review=Count('id', filter=Q(status='review')),
                todo=Count('id', filter=Q(status='todo')),
            )

            return Response({
                'total_projects': len(set(my_project_ids)),
                'total_tasks': my_tasks.count(),
                'completed_tasks': task_stats['done'],
                'task_stats': task_stats,
            })


# ──────────────────────────────────────────────
# System Settings
# ──────────────────────────────────────────────
class SystemSettingsView(generics.RetrieveUpdateAPIView):
    """GET/PUT /api/settings/ — admin only"""
    serializer_class = SystemSettingsSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_object(self):
        return SystemSettings.load()


# ──────────────────────────────────────────────
# User Avatar Upload
# ──────────────────────────────────────────────
class UserAvatarUploadView(APIView):
    """POST /api/users/me/avatar/ — upload avatar for current authenticated user"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        if 'avatar' not in request.FILES:
            return Response({'detail': 'No avatar file was submitted.'}, status=status.HTTP_400_BAD_REQUEST)
        
        avatar_file = request.FILES['avatar']
        
        # Save to default storage
        file_path = default_storage.save(f'avatars/{avatar_file.name}', avatar_file)
        
        # Build the absolute URL
        avatar_url = request.build_absolute_uri(default_storage.url(file_path))
        
        # Update user's avatar_url field
        user = request.user
        user.avatar_url = avatar_url
        user.save()
        
        return Response({'avatar_url': avatar_url}, status=status.HTTP_200_OK)
