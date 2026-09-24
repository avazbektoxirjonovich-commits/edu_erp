from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import ApplicationViewSet

router = SimpleRouter()
router.register('', ApplicationViewSet, basename='application')

urlpatterns = [path('', include(router.urls))]
