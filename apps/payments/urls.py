from django.urls import path

from apps.students.export_views import ExportPaymentsView

from .views import (
    GenerateInvoicesView,
    MonthlySummaryView,
    MyPaymentsView,
    PaymentDetailView,
    PaymentHistoryView,
    PaymentViewSet,
    UnpaidStudentsView,
)

urlpatterns = [
    path('',         PaymentViewSet.as_view(),    name='payment-list'),
    path('generate/', GenerateInvoicesView.as_view(), name='payment-generate'),
    path('my/',      MyPaymentsView.as_view(),    name='payment-my'),
    path('unpaid/',  UnpaidStudentsView.as_view(), name='payment-unpaid'),
    path('summary/', MonthlySummaryView.as_view(), name='payment-summary'),
    path('export/',  ExportPaymentsView.as_view(), name='payment-export'),
    path('<uuid:pk>/', PaymentDetailView.as_view(), name='payment-detail'),
    path('<uuid:pk>/history/', PaymentHistoryView.as_view(), name='payment-history'),
]
