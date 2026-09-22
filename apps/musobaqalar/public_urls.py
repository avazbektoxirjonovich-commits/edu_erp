from django.urls import path

from .public import CurrentCompetitionView, LatestResultsView, RegisterView, ResultsView

urlpatterns = [
    path('musobaqa/joriy/', CurrentCompetitionView.as_view(), name='public-competition-current'),
    path('musobaqa/royxat/', RegisterView.as_view(), name='public-competition-register'),
    path('musobaqa/natijalar/oxirgi/', LatestResultsView.as_view(), name='public-competition-results-latest'),
    path('musobaqa/natijalar/<uuid:pk>/', ResultsView.as_view(), name='public-competition-results'),
]
