"""SQLAlchemy ORM models for RecoverPay AI.

Canonical location per AGENTS.md. Session / engine helpers stay in
``backend/database.py``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Transaction(Base):
    """Failed / in-recovery payment tracked by RecoverPay AI."""

    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    merchant_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    customer_email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    failure_code: Mapped[str] = mapped_column(String(100), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recovery_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PENDING", index=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    audit_logs: Mapped[list[AuditLog]] = relationship(
        "AuditLog",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )


class AuditLog(Base):
    """Immutable step-by-step execution history for a recovery flow."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    transaction_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("transactions.id"), nullable=True, index=True
    )
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    step_status: Mapped[str] = mapped_column(String(20), nullable=False)
    llm_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    guardrail_evaluation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    transaction: Mapped[Transaction | None] = relationship(
        "Transaction", back_populates="audit_logs"
    )


class OptOutRegistry(Base):
    """Compliance stop-list. Presence of a phone number blocks all outreach."""

    __tablename__ = "opt_out_registry"

    phone_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    opt_out_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
