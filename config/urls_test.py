"""
Minimal URL configuration for tests.
Only wires routes actually needed by tests that make real HTTP calls
(see apps/finance Phase 3 note in project memory — this file is
hand-maintained, not auto-derived from config/urls.py).
"""
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

urlpatterns = [
    path('admin/',       admin.site.urls),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/face-auth/', include('apps.face_auth.api.urls')),
    path('api/v1/students/', include('apps.students.urls')),
    path('api/v1/teachers/', include('apps.teachers.urls')),
    path('api/v1/groups/',   include('apps.groups.urls')),
    path('api/v1/attendance/', include('apps.attendance.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/finance/',  include('apps.finance.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/dashboard/', include('apps.dashboard.urls')),
    path('api/v1/store/',    include('apps.store.urls')),
    path('api/v1/homework/', include('apps.homework.urls')),
    path('api/v1/challenges/', include('apps.zukko.urls')),
    path('api/v1/vlt-ai/',   include('apps.vlt_ai.api.urls')),
    path('api/v1/error-monitor/', include('apps.error_monitor.urls')),
    path('api/v1/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/token/verify/',  TokenVerifyView.as_view(),  name='token_verify'),
]
