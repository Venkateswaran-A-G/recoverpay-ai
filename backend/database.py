"""Engine, session factory, and table-init helpers.

ORM models live in ``backend/models.py`` (AGENTS.md). This module is
re-exported so ``from backend.database import init_db`` still works.
"""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from backend.models import AuditLog, Base, OptOutRegistry, Transaction
import backend.env  # noqa: F401 — process env + .env.example placeholders only

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

__all__ = [
    "AuditLog",
    "Base",
    "DATABASE_URL",
    "OptOutRegistry",
    "SessionLocal",
    "Transaction",
    "engine",
    "get_db",
    "init_db",
]


def get_db() -> Generator:
    """FastAPI dependency that yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_sqlite_columns() -> None:
    """Add columns introduced after the first create_all (SQLite has no migrations)."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "transactions" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("transactions")}
    if "customer_state" not in existing:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN customer_state VARCHAR(50)"))


def init_db() -> None:
    """Create all tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


if __name__ == "__main__":
    init_db()
    print("DB Created")
