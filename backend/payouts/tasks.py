from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Payout
from .services import PayoutProcessor


@shared_task
def process_pending_payouts():
    payout_ids = list(
        Payout.objects.filter(status=Payout.Status.PENDING, next_attempt_at__lte=timezone.now())
        .order_by("created_at")
        .values_list("id", flat=True)[:50]
    )
    for payout_id in payout_ids:
        PayoutProcessor.process_one(payout_id)


@shared_task
def retry_stuck_payouts():
    cutoff = timezone.now() - timedelta(seconds=30)
    stuck = Payout.objects.filter(status=Payout.Status.PROCESSING, processing_started_at__lt=cutoff)
    for payout in stuck:
        if payout.attempts >= 3:
            PayoutProcessor.fail(payout.id, "Payout timed out after 3 attempts")
            continue
        with transaction.atomic():
            locked = Payout.objects.select_for_update().get(id=payout.id)
            if locked.status != Payout.Status.PROCESSING:
                continue
            delay_seconds = 2 ** locked.attempts
            locked.status = Payout.Status.PENDING
            locked.next_attempt_at = timezone.now() + timedelta(seconds=delay_seconds)
            locked.processing_started_at = None
            locked.save(update_fields=["status", "next_attempt_at", "processing_started_at", "updated_at"])
