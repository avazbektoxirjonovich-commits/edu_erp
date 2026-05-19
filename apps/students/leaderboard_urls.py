from django.urls import path
from .leaderboard_views import LeaderboardView

urlpatterns = [
    path('', LeaderboardView.as_view(), name='leaderboard'),
]