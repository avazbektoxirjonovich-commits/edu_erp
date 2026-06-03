from django.urls import path

from apps.vlt_ai.api.views import ChatView, ConversationDetailView, ConversationListView

app_name = "vlt_ai"

urlpatterns = [
    path("chat/",                    ChatView.as_view(),               name="chat"),
    path("conversations/",           ConversationListView.as_view(),   name="conversation-list"),
    path("conversations/<uuid:pk>/", ConversationDetailView.as_view(), name="conversation-detail"),
]
