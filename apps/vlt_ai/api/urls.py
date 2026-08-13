from django.urls import path

from apps.vlt_ai.api.views import (
    AdminConversationDetailView,
    AdminConversationListView,
    ChatView,
    ConversationDetailView,
    ConversationListView,
)

app_name = "vlt_ai"

urlpatterns = [
    path("chat/",                    ChatView.as_view(),               name="chat"),
    path("conversations/",           ConversationListView.as_view(),   name="conversation-list"),
    path("conversations/<uuid:pk>/", ConversationDetailView.as_view(), name="conversation-detail"),
    path("admin/conversations/",           AdminConversationListView.as_view(),   name="admin-conversation-list"),
    path("admin/conversations/<uuid:pk>/", AdminConversationDetailView.as_view(), name="admin-conversation-detail"),
]
