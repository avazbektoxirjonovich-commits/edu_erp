from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import GroupViewSet, RoomViewSet

rooms = SimpleRouter()
rooms.register('rooms', RoomViewSet, basename='room')

router = SimpleRouter()
router.register('', GroupViewSet, basename='group')

# rooms/ birinchi — aks holda guruh detail yo'li ('<pk>/') uni ushlab qoladi
urlpatterns = [path('', include(rooms.urls)), path('', include(router.urls))]
