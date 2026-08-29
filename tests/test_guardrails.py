"""Guardrail state-machine tests (in-memory SQLite, no LLM)."""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.guardrails import evaluate_guardrails
from backend.models import Base, OptOutRegistry, Transaction
from backend.schemas import RecoveryStatus


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_txn(
    db: Session,
    *,
    amount: str,
    phone: str = "+919876543210",
    retry_count: int = 0,
) -> Transaction:
    txn = Transaction(
        merchant_id="merch_keto",
        customer_name="Rahul",
        customer_phone=phone,
        customer_email="rahul@example.com",
        amount=Decimal(amount),
        failure_code="BAD_REQUEST_PAYMENT_TIMED_OUT",
        retry_count=retry_count,
    )
    db.add(txn)
    db.flush()
    return txn


def test_standard_amount_under_threshold_passes(db: Session):
    txn = _make_txn(db, amount="1499.00", retry_count=0)

    result = evaluate_guardrails(txn, db)

    assert result.passed is True
    assert result.requires_human_approval is False
    assert result.blocked is False
    assert result.recovery_status == RecoveryStatus.PENDING
    assert txn.recovery_status == RecoveryStatus.PENDING.value


def test_high_value_amount_flagged_for_human_approval(db: Session):
    txn = _make_txn(db, amount="7500.00", retry_count=0)

    result = evaluate_guardrails(txn, db)

    assert result.passed is False
    assert result.requires_human_approval is True
    assert result.blocked is False
    assert result.recovery_status == RecoveryStatus.FLAGGED_FOR_APPROVAL
    assert txn.recovery_status == RecoveryStatus.FLAGGED_FOR_APPROVAL.value


def test_retry_limit_reached_hard_stops(db: Session):
    txn = _make_txn(db, amount="1499.00", retry_count=2)

    result = evaluate_guardrails(txn, db)

    assert result.passed is False
    assert result.blocked is True
    assert result.requires_human_approval is False
    assert result.recovery_status == RecoveryStatus.MAX_RETRIES_REACHED
    assert txn.recovery_status == RecoveryStatus.MAX_RETRIES_REACHED.value


def test_opted_out_phone_blocks_outreach(db: Session):
    phone = "+919876543210"
    db.add(OptOutRegistry(phone_number=phone, opt_out_source="SMS_STOP"))
    db.flush()
    txn = _make_txn(db, amount="1499.00", phone=phone, retry_count=0)

    result = evaluate_guardrails(txn, db)

    assert result.passed is False
    assert result.blocked is True
    assert result.opted_out is True
    assert result.recovery_status == RecoveryStatus.OPTED_OUT
    assert txn.recovery_status == RecoveryStatus.OPTED_OUT.value
