from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import PayoutError
from .models import BankAccount, LedgerEntry, Merchant, Payout
from .selectors import ledger_balances
from .serializers import (
    BankAccountSerializer,
    CreatePayoutSerializer,
    LedgerEntrySerializer,
    MerchantSerializer,
    PayoutSerializer,
)
from .services import PayoutService


def merchant_from_request(request):
    merchant_id = request.headers.get("X-Merchant-Id")
    if merchant_id:
        return get_object_or_404(Merchant, id=merchant_id)
    return Merchant.objects.order_by("created_at").first()


class ApiErrorMixin:
    def handle_exception(self, exc):
        if isinstance(exc, PayoutError):
            return Response({"code": exc.code, "detail": str(exc)}, status=exc.status_code)
        return super().handle_exception(exc)


class MerchantListView(APIView):
    def get(self, request):
        merchants = Merchant.objects.order_by("created_at")
        return Response(MerchantSerializer(merchants, many=True).data)


class SummaryView(APIView):
    def get(self, request):
        merchant = merchant_from_request(request)
        balances = ledger_balances(merchant)
        ledger = LedgerEntry.objects.filter(merchant=merchant).order_by("-created_at")[:20]
        payouts = Payout.objects.filter(merchant=merchant).select_related("bank_account").order_by("-created_at")[:20]
        accounts = BankAccount.objects.filter(merchant=merchant).order_by("created_at")

        return Response({
            "merchant": MerchantSerializer(merchant).data,
            "balances": balances,
            "bank_accounts": BankAccountSerializer(accounts, many=True).data,
            "ledger_entries": LedgerEntrySerializer(ledger, many=True).data,
            "payouts": PayoutSerializer(payouts, many=True).data,
        })


class PayoutListCreateView(ApiErrorMixin, APIView):
    def get(self, request):
        merchant = merchant_from_request(request)
        payouts = Payout.objects.filter(merchant=merchant).select_related("bank_account").order_by("-created_at")
        return Response(PayoutSerializer(payouts, many=True).data)

    def post(self, request):
        merchant = merchant_from_request(request)
        serializer = CreatePayoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body, response_status = PayoutService.create_payout(
            merchant=merchant,
            amount_paise=serializer.validated_data["amount_paise"],
            bank_account_id=serializer.validated_data["bank_account_id"],
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        return Response(body, status=response_status)
