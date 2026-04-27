import uuid
from datetime import timedelta

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .exceptions import InvalidPayoutTransition


class Merchant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class BankAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="bank_accounts")
    account_holder_name = models.CharField(max_length=160)
    bank_name = models.CharField(max_length=120)
    masked_account_number = models.CharField(max_length=32)
    ifsc = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bank_name} {self.masked_account_number}"


class Payout(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="payouts")
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name="payouts")
    amount_paise = models.BigIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def transition_to(self, new_status, failure_reason=""):
        allowed = {
            self.Status.PENDING: {self.Status.PROCESSING},
            self.Status.PROCESSING: {self.Status.COMPLETED, self.Status.FAILED},
            self.Status.COMPLETED: set(),
            self.Status.FAILED: set(),
        }
        if new_status not in allowed[self.status]:
            raise InvalidPayoutTransition(f"Cannot move payout {self.id} from {self.status} to {new_status}")
        self.status = new_status
        self.failure_reason = failure_reason
        if new_status == self.Status.PROCESSING:
            self.processing_started_at = timezone.now()
        self.save(update_fields=["status", "failure_reason", "processing_started_at", "updated_at"])


class LedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        CUSTOMER_PAYMENT = "customer_payment", "Customer payment"
        PAYOUT_HOLD = "payout_hold", "Payout hold"
        PAYOUT_RELEASE = "payout_release", "Payout release"
        PAYOUT_DEBIT = "payout_debit", "Payout debit"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="ledger_entries")
    payout = models.ForeignKey(Payout, on_delete=models.PROTECT, null=True, blank=True, related_name="ledger_entries")
    entry_type = models.CharField(max_length=32, choices=EntryType.choices)
    available_delta_paise = models.BigIntegerField()
    held_delta_paise = models.BigIntegerField(default=0)
    description = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["merchant", "-created_at"]),
            models.Index(fields=["payout", "entry_type"]),
        ]


class IdempotencyRecord(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="idempotency_records")
    key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "key"], name="unique_idempotency_key_per_merchant")
        ]
        indexes = [models.Index(fields=["merchant", "key"])]

    @classmethod
    def expiry_time(cls):
        return timezone.now() + timedelta(hours=24)
