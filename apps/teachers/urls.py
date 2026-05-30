from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import TeacherViewSet, TeacherSalaryListCreateView, TeacherSalaryDetailView

router = SimpleRouter()
router.register('', TeacherViewSet, basename='teacher')
urlpatterns = [
    path('', include(router.urls)),
    path('salaries/',        TeacherSalaryListCreateView.as_view(), name='teacher-salary-list'),
    path('salaries/<uuid:pk>/', TeacherSalaryDetailView.as_view(),  name='teacher-salary-detail'),
]
