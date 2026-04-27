from django.db.models import BigIntegerField, Sum, Value
from django.db.models.functions import Coalesce

from .models import LedgerEntry


def ledger_balances(merchant):
    balances = LedgerEntry.objects.filter(merchant=merchant).aggregate(
        available=Coalesce(Sum("available_delta_paise"), Value(0), output_field=BigIntegerField()),
        held=Coalesce(Sum("held_delta_paise"), Value(0), output_field=BigIntegerField()),
    )
    balances["total"] = balances["available"] + balances["held"]
    return balances
