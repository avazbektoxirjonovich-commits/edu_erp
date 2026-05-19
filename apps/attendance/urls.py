from django.urls import path
from .views import AttendanceListCreateView, AttendanceDetailView, BulkAttendanceView, MyAttendanceView

urlpatterns = [
    path('',            AttendanceListCreateView.as_view(), name='attendance-list'),
    path('my/',         MyAttendanceView.as_view(),         name='attendance-my'),
    path('bulk-create/', BulkAttendanceView.as_view(),      name='attendance-bulk'),
    path('bulk/',        BulkAttendanceView.as_view(),       name='attendance-bulk-alt'),
    path('<uuid:pk>/',  AttendanceDetailView.as_view(),     name='attendance-detail'),
]
