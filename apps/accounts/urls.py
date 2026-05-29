"""
ACCOUNTS URL patterns
/api/v1/auth/...
"""
from django.urls import path
from .views import (
    LoginView, LogoutView, MeView,
    ChangePasswordView, UserListCreateView, UserDetailView,
    UserToggleActiveView,
)

urlpatterns = [
    # Auth
    path('login/',           LoginView.as_view(),          name='auth-login'),
    path('logout/',          LogoutView.as_view(),          name='auth-logout'),
    path('me/',              MeView.as_view(),              name='auth-me'),
    path('change-password/', ChangePasswordView.as_view(), name='auth-change-password'),

    # Foydalanuvchilar (admin)
    path('users/',                             UserListCreateView.as_view(),  name='user-list'),
    path('users/<uuid:pk>/',                   UserDetailView.as_view(),      name='user-detail'),
    path('users/<uuid:pk>/toggle-active/',     UserToggleActiveView.as_view(),name='user-toggle-active'),
]
