from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import GroupViewSet

router = SimpleRouter()
router.register('', GroupViewSet, basename='group')
urlpatterns = [path('', include(router.urls))]
