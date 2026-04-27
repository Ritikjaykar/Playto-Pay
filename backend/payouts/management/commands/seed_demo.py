from django.core.management.base import BaseCommand
from django.db import transaction

from payouts.models import BankAccount, LedgerEntry, Merchant


class Command(BaseCommand):
    help = "Seed demo merchants, bank accounts, and customer payment credits."

    @transaction.atomic
    def handle(self, *args, **options):
        merchants = [
            ("Acme Design Studio", "ops@acmedesign.example", [250000, 175000, 90000]),
            ("Northstar Freelance", "hello@northstar.example", [120000, 80000]),
            ("PixelForge Agency", "finance@pixelforge.example", [500000, 130000, 70000]),
        ]

        for name, email, credits in merchants:
            merchant, _ = Merchant.objects.get_or_create(email=email, defaults={"name": name})
            BankAccount.objects.get_or_create(
                merchant=merchant,
                masked_account_number="XXXXXX4321",
                defaults={
                    "account_holder_name": name,
                    "bank_name": "HDFC Bank",
                    "ifsc": "HDFC0001234",
                },
            )
            if not LedgerEntry.objects.filter(merchant=merchant, entry_type=LedgerEntry.EntryType.CUSTOMER_PAYMENT).exists():
                for index, amount in enumerate(credits, start=1):
                    LedgerEntry.objects.create(
                        merchant=merchant,
                        entry_type=LedgerEntry.EntryType.CUSTOMER_PAYMENT,
                        available_delta_paise=amount,
                        held_delta_paise=0,
                        description=f"Simulated USD collection #{index}",
                    )

        self.stdout.write(self.style.SUCCESS("Seeded demo merchants."))
