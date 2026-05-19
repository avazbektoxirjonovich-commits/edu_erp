from django.urls import path
from .views import PaymentViewSet, PaymentDetailView, UnpaidStudentsView, MonthlySummaryView, MyPaymentsView

urlpatterns = [
    path('',         PaymentViewSet.as_view(),    name='payment-list'),
    path('my/',      MyPaymentsView.as_view(),    name='payment-my'),
    path('unpaid/',  UnpaidStudentsView.as_view(), name='payment-unpaid'),
    path('summary/', MonthlySummaryView.as_view(), name='payment-summary'),
    path('<uuid:pk>/', PaymentDetailView.as_view(), name='payment-detail'),
]
