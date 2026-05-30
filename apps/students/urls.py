from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import StudentViewSet, StudentMeView, ParentDashboardView
from .export_views import ExportStudentsView

router = SimpleRouter()
router.register('', StudentViewSet, basename='student')

urlpatterns = [
    path('me/',     StudentMeView.as_view(),       name='student-me'),
    path('parent/', ParentDashboardView.as_view(),  name='parent-dashboard'),
    path('export/', ExportStudentsView.as_view(),   name='student-export'),
    path('', include(router.urls)),
]
