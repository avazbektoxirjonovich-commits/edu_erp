from django.urls import path

from .public import ArizaCreateView

urlpatterns = [
    path('ariza/', ArizaCreateView.as_view(), name='public-ariza-create'),
]
