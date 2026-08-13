from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    KumushReportView,
    KumushTransactionListView,
    ManualKumushAdjustmentView,
    PurchaseRequestViewSet,
    StoreItemViewSet,
    StoreSummaryView,
)

router = SimpleRouter()
router.register('items',    StoreItemViewSet,      basename='store-item')
router.register('requests', PurchaseRequestViewSet, basename='store-request')

urlpatterns = [
    path('summary/',            StoreSummaryView.as_view(),             name='store-summary'),
    path('kumush-report/',      KumushReportView.as_view(),             name='kumush-report'),
    path('transactions/',       KumushTransactionListView.as_view(),    name='store-transactions'),
    path('kumush-adjustment/',  ManualKumushAdjustmentView.as_view(),   name='kumush-adjustment'),
    path('', include(router.urls)),
]
