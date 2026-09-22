from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import CompetitionViewSet, ParticipantViewSet

router = SimpleRouter()
router.register('competitions', CompetitionViewSet, basename='competition')
router.register('participants', ParticipantViewSet, basename='participant')

urlpatterns = [path('', include(router.urls))]
