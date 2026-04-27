import threading
import uuid

from django.db import connection, connections
from django.test import TransactionTestCase

from .models import BankAccount, IdempotencyRecord, LedgerEntry, Merchant, Payout
from .selectors import ledger_balances
from .services import PayoutService


class PayoutServiceTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.merchant = Merchant.objects.create(name="Test Merchant", email="test@example.com")
        self.account = BankAccount.objects.create(
            merchant=self.merchant,
            account_holder_name="Test Merchant",
            bank_name="ICICI Bank",
            masked_account_number="XXXX1234",
            ifsc="ICIC0000001",
        )

    def credit(self, amount_paise):
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type=LedgerEntry.EntryType.CUSTOMER_PAYMENT,
            available_delta_paise=amount_paise,
            description="Test credit",
        )

    def test_idempotency_returns_exact_same_response_without_duplicate_payout(self):
        self.credit(10000)
        idem_key = uuid.uuid4()

        first_body, first_status = PayoutService.create_payout(
            merchant=self.merchant,
            amount_paise=6000,
            bank_account_id=self.account.id,
            idempotency_key=idem_key,
        )
        second_body, second_status = PayoutService.create_payout(
            merchant=self.merchant,
            amount_paise=6000,
            bank_account_id=self.account.id,
            idempotency_key=idem_key,
        )

        self.assertEqual(first_status, 201)
        self.assertEqual(second_status, 201)
        self.assertEqual(first_body, second_body)
        self.assertEqual(Payout.objects.count(), 1)
        self.assertEqual(IdempotencyRecord.objects.count(), 1)
        self.assertEqual(ledger_balances(self.merchant)["available"], 4000)
        self.assertEqual(ledger_balances(self.merchant)["held"], 6000)

    def test_concurrent_payouts_cannot_overdraw_available_balance(self):
        if connection.vendor != "postgresql":
            self.skipTest("select_for_update concurrency guarantee is PostgreSQL-specific")

        self.credit(10000)
        barrier = threading.Barrier(2)
        results = []

        def request_payout():
            try:
                barrier.wait()
                body, status_code = PayoutService.create_payout(
                    merchant=self.merchant,
                    amount_paise=6000,
                    bank_account_id=self.account.id,
                    idempotency_key=uuid.uuid4(),
                )
                results.append((status_code, body))
            finally:
                connections.close_all()

        threads = [
            threading.Thread(target=request_payout),
            threading.Thread(target=request_payout),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        self.assertEqual(sorted(status for status, _ in results), [201, 400])
        self.assertEqual(Payout.objects.count(), 1)

        balances = ledger_balances(self.merchant)
        self.assertEqual(balances["available"], 4000)
        self.assertEqual(balances["held"], 6000)
