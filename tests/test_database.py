"""Smoke tests for SQLAlchemy models and table creation."""

from decimal import Decimal

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend.models import AuditLog, Base, OptOutRegistry, Transaction


def _memory_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    return engine, Session()


def test_orm_models_live_in_models_module():
    import backend.models as models

    assert models.Transaction.__tablename__ == "transactions"
    assert models.AuditLog.__tablename__ == "audit_logs"
    assert models.OptOutRegistry.__tablename__ == "opt_out_registry"


def test_init_db_creates_expected_tables():
    engine, session = _memory_session()
    try:
        tables = set(inspect(engine).get_table_names())
        assert tables == {"transactions", "audit_logs", "opt_out_registry"}
    finally:
        session.close()


def test_transaction_and_audit_log_roundtrip():
    _, session = _memory_session()
    try:
        txn = Transaction(
            merchant_id="merch_keto",
            customer_name="Rahul",
            customer_phone="+919876543210",
            customer_email="rahul@example.com",
            amount=Decimal("1499.00"),
            failure_code="BAD_REQUEST_PAYMENT_TIMED_OUT",
            failure_reason="Issuer SBI bank gateway did not respond within 30 seconds",
        )
        session.add(txn)
        session.flush()

        log = AuditLog(
            transaction_id=txn.id,
            step_name="INGESTION",
            step_status="SUCCESS",
            raw_payload={"event": "payment.failed"},
        )
        session.add(log)
        session.commit()

        stored = session.get(Transaction, txn.id)
        assert stored is not None
        assert stored.retry_count == 0
        assert stored.recovery_status == "PENDING"
        assert stored.currency == "INR"
        assert len(stored.audit_logs) == 1
        assert stored.audit_logs[0].step_name == "INGESTION"
    finally:
        session.close()


def test_opt_out_registry_primary_key_is_phone():
    _, session = _memory_session()
    try:
        session.add(
            OptOutRegistry(phone_number="+919876543210", opt_out_source="SMS_STOP")
        )
        session.commit()
        row = session.get(OptOutRegistry, "+919876543210")
        assert row is not None
        assert row.opt_out_source == "SMS_STOP"
    finally:
        session.close()
