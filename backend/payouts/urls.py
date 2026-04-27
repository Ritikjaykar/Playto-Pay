from django.urls import path

from .views import MerchantListView, PayoutListCreateView, SummaryView

urlpatterns = [
    path("merchants", MerchantListView.as_view(), name="merchant-list"),
    path("summary", SummaryView.as_view(), name="summary"),
    path("payouts", PayoutListCreateView.as_view(), name="payout-list-create"),
]
