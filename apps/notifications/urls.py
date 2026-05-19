from django.urls import path
from .views import NotificationListView, MarkReadView, UnreadCountView, SupportMessageView

urlpatterns = [
    path('',           NotificationListView.as_view(), name='notification-list'),
    path('unread/',    UnreadCountView.as_view(),       name='notification-unread'),
    path('mark-read/', MarkReadView.as_view(),          name='notification-mark-read'),
    path('support/',   SupportMessageView.as_view(),    name='notification-support'),
]
