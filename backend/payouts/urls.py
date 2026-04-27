from django.urls import path

from .views import MerchantListView, PayoutListCreateView, ProcessPayoutJobsView, SummaryView

urlpatterns = [
    path("merchants", MerchantListView.as_view(), name="merchant-list"),
    path("summary", SummaryView.as_view(), name="summary"),
    path("payouts", PayoutListCreateView.as_view(), name="payout-list-create"),
    path("jobs/process-payouts", ProcessPayoutJobsView.as_view(), name="process-payout-jobs"),
]