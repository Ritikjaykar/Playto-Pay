# EXPLAINER

## 1. The Ledger

Balance query:

```python
LedgerEntry.objects.filter(merchant=merchant).aggregate(
    available=Coalesce(Sum("available_delta_paise"), Value(0), output_field=BigIntegerField()),
    held=Coalesce(Sum("held_delta_paise"), Value(0), output_field=BigIntegerField()),
)
```

I modelled the ledger as append-only deltas instead of mutable balances. A customer payment writes `available_delta_paise=+amount`. A payout request writes a hold entry with `available_delta_paise=-amount` and `held_delta_paise=+amount`. A successful payout removes held funds with `held_delta_paise=-amount`; a failed payout releases the hold with `available_delta_paise=+amount` and `held_delta_paise=-amount`.

That gives three useful numbers from SQL sums: available balance, held balance, and total balance. No money amount is stored as a float.

## 2. The Lock

The overdraft prevention lives in `PayoutService.create_payout`:

```python
locked_merchant = Merchant.objects.select_for_update().get(id=merchant.id)
balances = ledger_balances(locked_merchant)
if balances["available"] < amount_paise:
    raise InsufficientFunds()
```

This relies on PostgreSQL row-level locks from `SELECT ... FOR UPDATE`. All payout creation for one merchant serializes on the merchant row, so two concurrent 6000 paise payout requests against a 10000 paise balance cannot both observe the same available balance.

## 3. The Idempotency

Each request inserts an `IdempotencyRecord` with `(merchant, key)` unique. The stored request hash prevents reusing a key with a different body. The stored response body and status code let repeated calls return the same response.

If the first request is still in flight, PostgreSQL makes the second insert wait on the unique constraint. After the first transaction commits, the second request catches the unique conflict, locks the existing idempotency row, and returns the saved response.

## 4. The State Machine

Illegal transitions are blocked in `Payout.transition_to`:

```python
allowed = {
    self.Status.PENDING: {self.Status.PROCESSING},
    self.Status.PROCESSING: {self.Status.COMPLETED, self.Status.FAILED},
    self.Status.COMPLETED: set(),
    self.Status.FAILED: set(),
}
if new_status not in allowed[self.status]:
    raise InvalidPayoutTransition(...)
```

Because `FAILED` has no outgoing states, failed-to-completed is rejected before the row is saved.

## 5. The AI Audit

AI initially suggested this pattern:

```python
available = ledger_balances(merchant)["available"]
if available >= amount:
    LedgerEntry.objects.create(...)
```

That is subtly wrong because two requests can both read the same aggregate before either hold entry is committed. Both pass the check and both insert debits.

I replaced it with a transaction that first locks the merchant row using `select_for_update()`, then runs the SQL aggregate and inserts the hold entry before committing. The aggregate remains database-derived, but the critical section is serialized per merchant.
