from rest_framework import serializers

from .models import BankAccount, LedgerEntry, Merchant, Payout


class MerchantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Merchant
        fields = ["id", "name", "email"]


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = ["id", "account_holder_name", "bank_name", "masked_account_number", "ifsc"]


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = [
            "id",
            "entry_type",
            "available_delta_paise",
            "held_delta_paise",
            "description",
            "created_at",
        ]


class PayoutSerializer(serializers.ModelSerializer):
    bank_account = BankAccountSerializer(read_only=True)

    class Meta:
        model = Payout
        fields = [
            "id",
            "amount_paise",
            "status",
            "attempts",
            "failure_reason",
            "bank_account",
            "created_at",
            "updated_at",
        ]


class CreatePayoutSerializer(serializers.Serializer):
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.UUIDField()
