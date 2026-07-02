from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('categories', views.ChallengeCategoryViewSet, basename='category')
router.register('bugfind', views.BugFindChallengeViewSet, basename='bugfind')
router.register('coding', views.CodingChallengeViewSet, basename='coding')
router.register('sessions', views.ChallengeSessionViewSet, basename='session')

urlpatterns = [
    path('', include(router.urls)),
    path('available/', views.AvailableSessionsView.as_view(), name='available-sessions'),
    path('start/<str:share_link>/', views.StartSessionView.as_view()),
    path('submit/', views.SubmitChallengeView.as_view()),
    path('anticheat/log/', views.AntiCheatLogView.as_view()),
    path('progress/', views.StudentProgressView.as_view()),
    path('report/<uuid:user_id>/', views.MonthlyReportView.as_view()),
    path('similarity/<uuid:session_id>/', views.SimilarityCheckView.as_view()),
]
