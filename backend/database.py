"""SQLAlchemy ORM models and SQLite / PostgreSQL-ready session helpers.

Tables follow the RecoverPay AI technical design document:
  - transactions
  - audit_logs
  - opt_out_registry
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Generator

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.types import JSON as GENERIC_JSON

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./recoverpay.db")

_connect_args: dict = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

# SQLite stores JSON as TEXT; PostgreSQL uses native JSON/JSONB via the generic type.
JSONType = SQLITE_JSON if DATABASE_URL.startswith("sqlite") else GENERIC_JSON


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
    guardrail_evaluation: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
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


def get_db() -> Generator:
    """FastAPI dependency that yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("DB Created")
