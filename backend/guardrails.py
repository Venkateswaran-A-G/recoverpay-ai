"""Deterministic financial guardrails (non-LLM state machine).

Hard rules from AGENTS.md — evaluated in this order:
  1. Opt-out registry  → OPTED_OUT (immediate stop)
  2. Retry cap         → MAX_RETRIES_REACHED if retry_count >= 2
  3. Amount threshold  → FLAGGED_FOR_APPROVAL if amount > ₹5,000
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.models import OptOutRegistry, Transaction
from backend.schemas import (
    FINANCIAL_THRESHOLD_INR,
    MAX_RETRY_COUNT,
    GuardrailEvaluationResult,
    RecoveryStatus,
)


def normalize_phone_digits(phone: str) -> str:
    """Return the last 10 digits of a phone number for registry matching."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def _opt_out_candidates(phone: str) -> set[str]:
    digits = "".join(ch for ch in phone if ch.isdigit())
    candidates = {phone}
    if len(digits) >= 10:
        local = digits[-10:]
        candidates.update({local, f"+91{local}", f"+91 {local}", f"91{local}"})
    return candidates


def is_opted_out(db: Session, phone: str) -> bool:
    """True if the customer phone exists in ``opt_out_registry``."""
    for candidate in _opt_out_candidates(phone):
        if db.get(OptOutRegistry, candidate) is not None:
            return True

    target = normalize_phone_digits(phone)
    if not target:
        return False
    for row in db.query(OptOutRegistry).all():
        if normalize_phone_digits(row.phone_number) == target:
            return True
    return False


def evaluate_guardrails(
    transaction: Transaction,
    db: Session,
    *,
    persist: bool = True,
) -> GuardrailEvaluationResult:
    """Evaluate safety rules and optionally persist ``recovery_status``.

    Never auto-dispatches when amount > ₹5,000. Never messages opted-out
    numbers. Hard-stops after ``MAX_RETRY_COUNT`` outreach attempts.
    """
    amount = Decimal(transaction.amount)
    retry_count = int(transaction.retry_count)
    phone = transaction.customer_phone

    opted_out = is_opted_out(db, phone)
    if opted_out:
        result = GuardrailEvaluationResult(
            passed=False,
            requires_human_approval=False,
            blocked=True,
            recovery_status=RecoveryStatus.OPTED_OUT,
            reasons=["customer phone is registered in opt_out_registry"],
            retry_count=retry_count,
            amount=amount,
            opted_out=True,
        )
        return _apply(transaction, result, persist)

    if retry_count >= MAX_RETRY_COUNT:
        result = GuardrailEvaluationResult(
            passed=False,
            requires_human_approval=False,
            blocked=True,
            recovery_status=RecoveryStatus.MAX_RETRIES_REACHED,
            reasons=[f"retry_count {retry_count} reached cap of {MAX_RETRY_COUNT}"],
            retry_count=retry_count,
            amount=amount,
            opted_out=False,
        )
        return _apply(transaction, result, persist)

    if amount > FINANCIAL_THRESHOLD_INR:
        result = GuardrailEvaluationResult(
            passed=False,
            requires_human_approval=True,
            blocked=False,
            recovery_status=RecoveryStatus.FLAGGED_FOR_APPROVAL,
            reasons=[
                f"amount ₹{amount} exceeds ₹{FINANCIAL_THRESHOLD_INR} auto-dispatch cap"
            ],
            retry_count=retry_count,
            amount=amount,
            opted_out=False,
        )
        return _apply(transaction, result, persist)

    result = GuardrailEvaluationResult(
        passed=True,
        requires_human_approval=False,
        blocked=False,
        recovery_status=RecoveryStatus.PENDING,
        reasons=[],
        retry_count=retry_count,
        amount=amount,
        opted_out=False,
    )
    return _apply(transaction, result, persist)


def _apply(
    transaction: Transaction,
    result: GuardrailEvaluationResult,
    persist: bool,
) -> GuardrailEvaluationResult:
    if persist:
        transaction.recovery_status = result.recovery_status.value
    return result
