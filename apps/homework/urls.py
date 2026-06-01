from django.urls import path
from . import views

app_name = 'homework'

urlpatterns = [
    path('assignments/',                   views.AssignmentListCreateView.as_view(), name='assignment-list'),
    path('assignments/<uuid:pk>/',         views.AssignmentDetailView.as_view(),     name='assignment-detail'),
    path('assignments/<uuid:pk>/submit/',  views.SubmitAssignmentView.as_view(),     name='submit'),
    path('submissions/',                   views.SubmissionListView.as_view(),        name='submission-list'),
    path('submissions/<uuid:pk>/grade/',   views.GradeSubmissionView.as_view(),      name='grade'),
    path('submissions/<uuid:pk>/file/',    views.SubmissionFileView.as_view(),        name='submission-file'),
    path('my/',                            views.MyAssignmentsView.as_view(),         name='my-assignments'),
]
