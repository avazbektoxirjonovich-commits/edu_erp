from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .export_views import (
    ExportAssetsView,
    ExportDebtsView,
    ExportExpensesView,
    ExportMonthlySummaryView,
    ExportSalariesView,
)
from .pdf_views import TransactionReceiptPDFView
from .views import (
    AssetSummaryView,
    AssetViewSet,
    DebtorsListView,
    ExpenseSummaryView,
    ExpenseViewSet,
    FinanceDashboardView,
    PaymentTransactionListView,
    RecordPaymentView,
    StudentFinanceSummaryView,
    TransactionDetailView,
)

router = SimpleRouter()
router.register('expenses', ExpenseViewSet, basename='finance-expense')
router.register('assets',   AssetViewSet,   basename='finance-asset')

urlpatterns = [
    path('dashboard/',           FinanceDashboardView.as_view(),       name='finance-dashboard'),
    path('transactions/',        PaymentTransactionListView.as_view(), name='finance-transactions'),
    path('transactions/record/', RecordPaymentView.as_view(),          name='finance-record-payment'),
    path('transactions/<uuid:pk>/', TransactionDetailView.as_view(),   name='finance-transaction-detail'),
    path('transactions/<uuid:pk>/receipt-pdf/', TransactionReceiptPDFView.as_view(),
         name='finance-transaction-receipt-pdf'),
    path('debts/',           DebtorsListView.as_view(),             name='finance-debts'),
    path('expenses/summary/', ExpenseSummaryView.as_view(),         name='finance-expense-summary'),
    path('assets/summary/',   AssetSummaryView.as_view(),           name='finance-asset-summary'),
    path('students/<uuid:pk>/summary/', StudentFinanceSummaryView.as_view(), name='finance-student-summary'),
    path('exports/debts/',    ExportDebtsView.as_view(),            name='finance-export-debts'),
    path('exports/salaries/', ExportSalariesView.as_view(),         name='finance-export-salaries'),
    path('exports/expenses/', ExportExpensesView.as_view(),         name='finance-export-expenses'),
    path('exports/assets/',   ExportAssetsView.as_view(),           name='finance-export-assets'),
    path('exports/summary/',  ExportMonthlySummaryView.as_view(),   name='finance-export-summary'),
    path('', include(router.urls)),
]
