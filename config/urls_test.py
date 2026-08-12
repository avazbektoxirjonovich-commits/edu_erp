"""
Minimal URL configuration for tests.
Excludes vlt_ai and other apps that require external services or missing packages.
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
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/finance/',  include('apps.finance.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/dashboard/', include('apps.dashboard.urls')),
    path('api/v1/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/token/verify/',  TokenVerifyView.as_view(),  name='token_verify'),
]
