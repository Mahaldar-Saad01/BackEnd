"""
WorkHub Core Views
All API endpoints: Auth, Employees, Departments, Projects, Tasks,
Events, Meetings, Chat, Notifications, Dashboard, Settings.
"""
from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    Department, Project, Task, Event, Meeting,
    Message, Notification, SystemSettings
)
from .serializers import (
    CustomTokenObtainPairSerializer,
    DepartmentSerializer,
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    ProjectSerializer, TaskSerializer, EventSerializer,
    MeetingSerializer, MessageSerializer, NotificationSerializer,
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
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PUT /api/users/me/ — current authenticated user profile"""
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = UserUpdateSerializer(instance, data=request.data, partial=partial)
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
            return Response({'detail': 'Password changed successfully.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
        # Employees may only update their own task's status
        if user.role == 'employee':
            if instance.assignee != user:
                return Response(
                    {'detail': 'You can only update your own tasks.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            allowed = {'status'}
            if not set(request.data.keys()).issubset(allowed):
                return Response(
                    {'detail': 'Employees may only update task status.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        # Managers may only update tasks in their projects
        if user.role == 'manager' and instance.project:
            if instance.project.lead_manager != user:
                return Response(
                    {'detail': 'You can only update tasks in your projects.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        return super().partial_update(request, *args, **kwargs)


# ──────────────────────────────────────────────
# Event (Calendar) ViewSet
# ──────────────────────────────────────────────
class EventViewSet(viewsets.ModelViewSet):
    """GET/POST /api/calendar/events/"""
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Event.objects.select_related('creator').all()

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
class MeetingViewSet(viewsets.ModelViewSet):
    """GET/POST /api/meetings/"""
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Meeting.objects.select_related('creator').all()

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)


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
        return Message.objects.filter(room=room).select_related('sender', 'receiver')

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)


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
