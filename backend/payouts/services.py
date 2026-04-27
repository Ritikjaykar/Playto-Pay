import hashlib
import json
from random import random

from django.db import IntegrityError, transaction
from django.utils import timezone

from .exceptions import IdempotencyConflict, InsufficientFunds, InvalidIdempotencyKey, PayoutError
from .models import BankAccount, IdempotencyRecord, LedgerEntry, Merchant, Payout
from .selectors import ledger_balances


def request_hash(payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def payout_response(payout):
    return {
        "id": str(payout.id),
        "amount_paise": payout.amount_paise,
        "status": payout.status,
        "bank_account_id": str(payout.bank_account_id),
        "attempts": payout.attempts,
        "created_at": payout.created_at.isoformat().replace("+00:00", "Z"),
        "updated_at": payout.updated_at.isoformat().replace("+00:00", "Z"),
    }


class PayoutService:
    @staticmethod
    def create_payout(*, merchant, amount_paise, bank_account_id, idempotency_key):
        # This method is the main API write path. It first handles idempotency,
        # then calls _create_payout_once only when this key has not been used.
        if not idempotency_key:
            raise InvalidIdempotencyKey("Idempotency-Key header is required")

        body_hash = request_hash({"amount_paise": amount_paise, "bank_account_id": str(bank_account_id)})

        try:
            with transaction.atomic():
                idem = IdempotencyRecord.objects.create(
                    merchant=merchant,
                    key=idempotency_key,
                    request_hash=body_hash,
                    expires_at=IdempotencyRecord.expiry_time(),
                )
                try:
                    response_body, response_status = PayoutService._create_payout_once(
                        merchant=merchant,
                        amount_paise=amount_paise,
                        bank_account_id=bank_account_id,
                    )
                except PayoutError as exc:
                    response_body = {"code": exc.code, "detail": str(exc)}
                    response_status = exc.status_code
                idem.response_body = response_body
                idem.response_status = response_status
                idem.status = IdempotencyRecord.Status.COMPLETED
                idem.save(update_fields=["response_body", "response_status", "status"])
                return response_body, response_status
        except IntegrityError:
            with transaction.atomic():
                idem = IdempotencyRecord.objects.select_for_update().get(merchant=merchant, key=idempotency_key)
                if idem.request_hash != body_hash:
                    raise IdempotencyConflict("Idempotency-Key was already used with a different request body")
                if idem.expires_at < timezone.now():
                    raise IdempotencyConflict("Idempotency-Key has expired")
                if idem.status != IdempotencyRecord.Status.COMPLETED:
                    raise IdempotencyConflict("Original request is still processing")
                return idem.response_body, idem.response_status

    @staticmethod
    def _create_payout_once(*, merchant, amount_paise, bank_account_id):
        # select_for_update is the important concurrency primitive here.
        # It makes payout requests for the same merchant run one after another.
        locked_merchant = Merchant.objects.select_for_update().get(id=merchant.id)
        bank_account = BankAccount.objects.get(id=bank_account_id, merchant=locked_merchant)
        balances = ledger_balances(locked_merchant)
        if balances["available"] < amount_paise:
            raise InsufficientFunds("Available balance is too low for this payout")

        payout = Payout.objects.create(
            merchant=locked_merchant,
            bank_account=bank_account,
            amount_paise=amount_paise,
        )
        LedgerEntry.objects.create(
            merchant=locked_merchant,
            payout=payout,
            entry_type=LedgerEntry.EntryType.PAYOUT_HOLD,
            available_delta_paise=-amount_paise,
            held_delta_paise=amount_paise,
            description=f"Funds held for payout {payout.id}",
        )
        return payout_response(payout), 201


class PayoutProcessor:
    @staticmethod
    def process_one(payout_id):
        with transaction.atomic():
            payout = Payout.objects.select_for_update(skip_locked=True).get(id=payout_id)
            if payout.status != Payout.Status.PENDING or payout.next_attempt_at > timezone.now():
                return
            payout.attempts += 1
            payout.save(update_fields=["attempts", "updated_at"])
            payout.transition_to(Payout.Status.PROCESSING)

        outcome = random()
        if outcome < 0.7:
            PayoutProcessor.complete(payout_id)
        elif outcome < 0.9:
            PayoutProcessor.fail(payout_id, "Bank rejected payout")

    @staticmethod
    def complete(payout_id):
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)
            if payout.status != Payout.Status.PROCESSING:
                return
            LedgerEntry.objects.create(
                merchant=payout.merchant,
                payout=payout,
                entry_type=LedgerEntry.EntryType.PAYOUT_DEBIT,
                available_delta_paise=0,
                held_delta_paise=-payout.amount_paise,
                description=f"Payout {payout.id} completed",
            )
            payout.transition_to(Payout.Status.COMPLETED)

    @staticmethod
    def fail(payout_id, reason):
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)
            if payout.status not in {Payout.Status.PENDING, Payout.Status.PROCESSING}:
                return
            if payout.status == Payout.Status.PENDING:
                payout.transition_to(Payout.Status.PROCESSING)
            LedgerEntry.objects.create(
                merchant=payout.merchant,
                payout=payout,
                entry_type=LedgerEntry.EntryType.PAYOUT_RELEASE,
                available_delta_paise=payout.amount_paise,
                held_delta_paise=-payout.amount_paise,
                description=f"Payout {payout.id} failed and funds were released",
            )
            payout.transition_to(Payout.Status.FAILED, failure_reason=reason)
