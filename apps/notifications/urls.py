from django.urls import path
from .views import (
    NotificationListView, MarkReadView, UnreadCountView,
    SupportMessageView, SupportReplyView, SupportInboxView,
    SendPaymentRemindersView, ActivityLogListView,
)

urlpatterns = [
    path('',                         NotificationListView.as_view(), name='notification-list'),
    path('unread/',                  UnreadCountView.as_view(),      name='notification-unread'),
    path('mark-read/',               MarkReadView.as_view(),         name='notification-mark-read'),
    path('support/',                 SupportMessageView.as_view(),   name='notification-support'),
    path('support/inbox/',           SupportInboxView.as_view(),     name='notification-support-inbox'),
    path('support/<uuid:pk>/reply/', SupportReplyView.as_view(),     name='notification-support-reply'),
    path('send-reminders/',          SendPaymentRemindersView.as_view(), name='send-reminders'),
    path('activity/',                ActivityLogListView.as_view(),  name='activity-log'),
]