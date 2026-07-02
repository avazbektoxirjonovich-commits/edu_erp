from django.urls import path
from . import views

urlpatterns = [
    # Enrollment
    path('enroll/',        views.FaceEnrollView.as_view(),    name='face-enroll'),
    path('enroll/delete/', views.FaceDeleteView.as_view(),    name='face-delete'),
    path('status/',        views.FaceStatusView.as_view(),    name='face-status'),

    # Login second factor
    path('verify-login/',  views.FaceVerifyLoginView.as_view(), name='face-verify-login'),

    # OTP fallback
    path('otp-request/',   views.FaceOTPRequestView.as_view(),  name='face-otp-request'),
    path('otp-verify/',    views.FaceOTPVerifyView.as_view(),    name='face-otp-verify'),
]
