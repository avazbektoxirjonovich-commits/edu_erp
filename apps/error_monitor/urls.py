from django.urls import path

from .views import (
    ErrorAnalyzeView,
    ErrorEventDetailView,
    ErrorEventListView,
    ErrorEventStatusView,
    ErrorStatsView,
)

app_name = "error_monitor"

urlpatterns = [
    path("stats/",              ErrorStatsView.as_view(),        name="stats"),
    path("errors/",             ErrorEventListView.as_view(),    name="error-list"),
    path("errors/<uuid:pk>/",   ErrorEventDetailView.as_view(),  name="error-detail"),
    path("errors/<uuid:pk>/status/",  ErrorEventStatusView.as_view(),  name="error-status"),
    path("errors/<uuid:pk>/analyze/", ErrorAnalyzeView.as_view(), name="error-analyze"),
]
