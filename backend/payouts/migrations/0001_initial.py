# Generated for the Playto payout challenge.

import uuid

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Merchant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="BankAccount",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("account_holder_name", models.CharField(max_length=160)),
                ("bank_name", models.CharField(max_length=120)),
                ("masked_account_number", models.CharField(max_length=32)),
                ("ifsc", models.CharField(max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bank_accounts", to="payouts.merchant")),
            ],
        ),
        migrations.CreateModel(
            name="Payout",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount_paise", models.BigIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("status", models.CharField(choices=[("pending", "Pending"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed")], default="pending", max_length=20)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField()),
                ("processing_started_at", models.DateTimeField(blank=True, null=True)),
                ("failure_reason", models.CharField(blank=True, max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("bank_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payouts", to="payouts.bankaccount")),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payouts", to="payouts.merchant")),
            ],
        ),
        migrations.CreateModel(
            name="IdempotencyRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.UUIDField()),
                ("request_hash", models.CharField(max_length=64)),
                ("status", models.CharField(choices=[("processing", "Processing"), ("completed", "Completed")], default="processing", max_length=20)),
                ("response_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("response_body", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="idempotency_records", to="payouts.merchant")),
            ],
        ),
        migrations.CreateModel(
            name="LedgerEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("entry_type", models.CharField(choices=[("customer_payment", "Customer payment"), ("payout_hold", "Payout hold"), ("payout_release", "Payout release"), ("payout_debit", "Payout debit")], max_length=32)),
                ("available_delta_paise", models.BigIntegerField()),
                ("held_delta_paise", models.BigIntegerField(default=0)),
                ("description", models.CharField(max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ledger_entries", to="payouts.merchant")),
                ("payout", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ledger_entries", to="payouts.payout")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["merchant", "-created_at"], name="payouts_led_merchan_221f87_idx"),
                    models.Index(fields=["payout", "entry_type"], name="payouts_led_payout__215b20_idx"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="idempotencyrecord",
            constraint=models.UniqueConstraint(fields=("merchant", "key"), name="unique_idempotency_key_per_merchant"),
        ),
        migrations.AddIndex(
            model_name="idempotencyrecord",
            index=models.Index(fields=["merchant", "key"], name="payouts_ide_merchan_a08ed6_idx"),
        ),
    ]
