from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StudentViewSet, StudentMeView

router = DefaultRouter()
router.register('', StudentViewSet, basename='student')

urlpatterns = [
    path('me/', StudentMeView.as_view(), name='student-me'),
    path('', include(router.urls)),
]
