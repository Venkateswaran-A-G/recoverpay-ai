"""Engine, session factory, and table-init helpers.

ORM models live in ``backend/models.py`` (AGENTS.md). This module is
re-exported so ``from backend.database import init_db`` still works.
"""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import AuditLog, Base, OptOutRegistry, Transaction

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


def init_db() -> None:
    """Create all tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("DB Created")
