# Interview Notes

These are short answers you can practice.

## What Does This Project Do?

It lets a merchant see balance, request payouts, and track payout status.

The difficult part is keeping money correct when requests are retried or happen at the same time.

## Why Store Money In Paise?

Money is stored as integer paise using `BigIntegerField`.

I did not use floats because floats can introduce rounding bugs.

## Why Use A Ledger?

A ledger keeps history. Instead of updating a single balance number, every credit and debit is recorded.

Balance is calculated from the ledger:

```text
available = sum(available_delta_paise)
held = sum(held_delta_paise)
```

## How Do You Prevent Two Payouts From Overdrawing?

I lock the merchant row:

```python
Merchant.objects.select_for_update().get(id=merchant.id)
```

Then I calculate balance and create the hold entry inside the same transaction.

## What Happens If User Clicks Twice?

The API uses `Idempotency-Key`.

Same merchant and same key returns the same saved response.

So duplicate network retries do not create duplicate payouts.

## What Happens On Payout Failure?

Failure creates a ledger release entry:

```text
available + amount
held - amount
```

That returns the money to the merchant.

## Why Celery?

Bank settlement should not run inside the API request. The API creates the payout and holds funds quickly. Celery processes settlement in the background.

## What Would You Improve With More Time?

- Real authentication instead of `X-Merchant-Id`.
- Better admin/audit screens.
- More tests around stuck payout retries.
- Webhooks for payout status changes.
- Deployment hardening with production secrets and monitoring.

## One Honest AI Audit Example

AI first suggested:

```python
available = ledger_balances(merchant)["available"]
if available >= amount:
    LedgerEntry.objects.create(...)
```

That is wrong because two requests can both read the same available balance.

I replaced it with:

```python
locked_merchant = Merchant.objects.select_for_update().get(id=merchant.id)
balances = ledger_balances(locked_merchant)
```

Now concurrent payout requests are serialized per merchant.
