"""
WorkHub Core URL Configuration
Router-based ViewSets + custom auth endpoints
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register(r'employees',        views.EmployeeViewSet,    basename='employee')
router.register(r'departments',      views.DepartmentViewSet,  basename='department')
router.register(r'projects',         views.ProjectViewSet,     basename='project')
router.register(r'tasks',            views.TaskViewSet,        basename='task')
router.register(r'calendar/events',  views.EventViewSet,       basename='event')
router.register(r'meetings',         views.MeetingViewSet,     basename='meeting')
router.register(r'chat/messages',    views.MessageViewSet,     basename='message')
router.register(r'notifications',    views.NotificationViewSet, basename='notification')

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────
    path('auth/login/',           views.CustomTokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('auth/token/refresh/',   TokenRefreshView.as_view(),                name='token-refresh'),
    path('auth/register/',        views.RegisterEmployeeView.as_view(),      name='register'),
    path('auth/logout/',          views.LogoutView.as_view(),                name='logout'),
    path('auth/change-password/', views.ChangePasswordView.as_view(),        name='change-password'),
    path('auth/password-otp/request/', views.PasswordOtpRequestView.as_view(), name='password-otp-request'),
    path('auth/password-otp/confirm/', views.PasswordOtpConfirmView.as_view(), name='password-otp-confirm'),

    # ── Current User ───────────────────────────────────────────────
    path('users/me/', views.MeView.as_view(), name='me'),
    path('users/me/avatar/', views.UserAvatarUploadView.as_view(), name='user-avatar-upload'),

    # ── Dashboard ─────────────────────────────────────────────────
    path('dashboard/stats/', views.DashboardStatsView.as_view(), name='dashboard-stats'),

    # ── Settings ──────────────────────────────────────────────────
    path('settings/', views.SystemSettingsView.as_view(), name='settings'),

    # ── All ViewSet Routes ────────────────────────────────────────
    path('', include(router.urls)),
]
