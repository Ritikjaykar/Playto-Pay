from django.core.management.base import BaseCommand

from payouts.tasks import process_pending_payouts, retry_stuck_payouts


class Command(BaseCommand):
    help = "Run payout processing jobs once. Useful for cron-style hosted workers."

    def handle(self, *args, **options):
        process_pending_payouts.run()
        retry_stuck_payouts.run()
        self.stdout.write(self.style.SUCCESS("Processed payout jobs."))