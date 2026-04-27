class PayoutError(Exception):
    status_code = 400
    code = "payout_error"


class InsufficientFunds(PayoutError):
    code = "insufficient_funds"


class InvalidIdempotencyKey(PayoutError):
    code = "invalid_idempotency_key"


class IdempotencyConflict(PayoutError):
    status_code = 409
    code = "idempotency_conflict"


class InvalidPayoutTransition(PayoutError):
    code = "invalid_payout_transition"
