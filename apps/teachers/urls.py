from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import TeacherSalaryDetailView, TeacherSalaryListCreateView, TeacherViewSet

router = SimpleRouter()
router.register('', TeacherViewSet, basename='teacher')
urlpatterns = [
    path('salaries/',        TeacherSalaryListCreateView.as_view(), name='teacher-salary-list'),
    path('salaries/<uuid:pk>/', TeacherSalaryDetailView.as_view(),  name='teacher-salary-detail'),
    path('', include(router.urls)),
]
