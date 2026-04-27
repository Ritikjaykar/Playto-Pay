# Code Walkthrough

Use this file to understand and explain the project. You do not need to memorize every Django setup file. The important payout logic is in five files.

## The Short Version

This project lets merchants withdraw their balance.

Money moves like this:

```text
Customer payment
  -> ledger credit increases available balance

Payout request
  -> lock merchant row
  -> check available balance
  -> create payout
  -> move money from available to held

Background worker success
  -> remove money from held forever

Background worker failure
  -> move money from held back to available
```

## Files You Must Understand

```text
backend/payouts/models.py
```

Defines the database tables:

- `Merchant`: business receiving payouts.
- `BankAccount`: merchant bank account.
- `Payout`: payout request and status.
- `LedgerEntry`: append-only money movements.
- `IdempotencyRecord`: remembers API requests by idempotency key.

```text
backend/payouts/selectors.py
```

Calculates balance using SQL `SUM`.

```text
backend/payouts/services.py
```

Contains the main business logic:

- create payout
- prevent overdraft
- enforce idempotency
- complete or fail payout

```text
backend/payouts/tasks.py
```

Celery background jobs:

- pick pending payouts
- simulate bank success/failure/hang
- retry stuck payouts

```text
backend/payouts/tests.py
```

Proves:

- same idempotency key does not create duplicate payout
- two concurrent payouts cannot overdraw balance

## The Ledger

The project does not store a mutable `merchant.balance` field.

Instead, every money movement is a row in `LedgerEntry`.

Important fields:

```python
available_delta_paise
held_delta_paise
```

Example:

```text
Customer pays Rs 5000
available_delta_paise = +500000
held_delta_paise = 0
```

Payout request for Rs 1000:

```text
available_delta_paise = -100000
held_delta_paise = +100000
```

Payout succeeds:

```text
available_delta_paise = 0
held_delta_paise = -100000
```

Payout fails:

```text
available_delta_paise = +100000
held_delta_paise = -100000
```

Balance is calculated in `selectors.py`:

```python
LedgerEntry.objects.filter(merchant=merchant).aggregate(
    available=Coalesce(Sum("available_delta_paise"), Value(0), output_field=BigIntegerField()),
    held=Coalesce(Sum("held_delta_paise"), Value(0), output_field=BigIntegerField()),
)
```

Interview answer:

> I used an append-only ledger because payment systems should preserve money history. The displayed balance is derived from ledger sums, so the invariant is easy to check: credits minus debits equals displayed balance.

## The Lock

The most important line is in `services.py`:

```python
locked_merchant = Merchant.objects.select_for_update().get(id=merchant.id)
```

This tells PostgreSQL:

> Lock this merchant row until the transaction finishes.

Why it matters:

If merchant has Rs 100 and sends two Rs 60 payout requests at the same time:

- request 1 locks merchant
- request 2 waits
- request 1 holds Rs 60
- request 2 then sees only Rs 40 available
- request 2 fails cleanly

Interview answer:

> The lock relies on PostgreSQL row-level locking via `SELECT FOR UPDATE`. I lock the merchant row before calculating balance and inserting the hold entry, so check-and-hold is serialized per merchant.

## Idempotency

The frontend/API sends:

```http
Idempotency-Key: some-uuid
```

The backend stores that key in `IdempotencyRecord`.

The unique rule is:

```text
one merchant + one key = one saved response
```

If the same key is used again with the same request body, the backend returns the saved response.

If the same key is used with a different amount or bank account, it returns conflict.

Interview answer:

> I store `(merchant, key)` with a request hash and response body. The database unique constraint prevents duplicates. On retry, I return the saved response instead of creating a second payout.

## State Machine

Legal payout states:

```text
pending -> processing -> completed
pending -> processing -> failed
```

Blocked transitions:

```text
completed -> pending
failed -> completed
anything backwards
```

The check is in `Payout.transition_to` in `models.py`.

Interview answer:

> I keep allowed transitions in one method. `FAILED` and `COMPLETED` have no outgoing transitions, so failed-to-completed is rejected before saving.

## Background Worker

Celery runs two scheduled jobs.

`process_pending_payouts`:

- finds pending payouts
- marks them processing
- simulates bank result
- 70 percent completed
- 20 percent failed
- 10 percent left processing

`retry_stuck_payouts`:

- finds payouts stuck in processing for more than 30 seconds
- retries with exponential backoff
- after 3 attempts, marks failed and releases held funds

Interview answer:

> I did not process payouts synchronously inside the API. The API only creates the payout and holds funds. Celery later processes settlement, which is closer to how real payment systems work.

## What To Say About The Folder Count

If asked why there are many files:

> Django has standard setup files for settings, URLs, migrations, and app config. The actual payout logic is intentionally small and concentrated in `payouts/models.py`, `payouts/services.py`, `payouts/selectors.py`, `payouts/tasks.py`, and `payouts/tests.py`.

## Manual Test Checklist

Run:

```powershell
docker compose up --build
```

Open:

```text
http://localhost:5173
```

Check:

- dashboard loads
- merchant dropdown works
- balance appears
- payout request creates a row
- huge payout fails with insufficient balance
- completed payout removes held money
- failed payout returns held money

Run automated tests:

```powershell
docker compose exec backend python manage.py test payouts
```

Expected:

```text
OK
```

## 45-Second Explanation

> I built a small payout engine using Django, DRF, PostgreSQL, Celery, and React. The core design is an append-only ledger, where available and held balances are calculated using SQL sums over ledger entries. When a merchant requests a payout, I use an idempotency key to prevent duplicate requests, then lock the merchant row with `select_for_update`, calculate available balance, and insert a ledger hold entry inside the same transaction. A Celery worker processes pending payouts asynchronously. On success, held funds are debited permanently. On failure or timeout, held funds are released atomically. The tests cover idempotency and concurrent payout requests.

## Things You Should Admit Honestly

You can say:

> I used AI to speed up implementation, but I focused my review on the dangerous parts: locking, idempotency, ledger aggregation, and state transitions.

You should not say:

> I wrote every line from memory.

That sounds less believable and is not required by the challenge.
