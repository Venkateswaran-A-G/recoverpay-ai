"""Razorpay webhook HMAC + payment-link helpers.

Live SDK calls run only when ``TEST_MODE`` is off and real keys are present.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from decimal import Decimal

import backend.env  # noqa: F401 — process env + .env.example placeholders only

PLACEHOLDER_MARKERS = ("sk-proj-...", "test_secret_...", "rzp_test_...", "changeme", "xxx")


def is_test_mode() -> bool:
    return os.getenv("TEST_MODE", "false").strip().lower() in {"1", "true", "yes"}


def webhook_secret() -> str:
    return (
        os.getenv("RAZORPAY_WEBHOOK_SECRET")
        or os.getenv("WEBHOOK_SECRET")
        or ""
    ).strip()


def _is_placeholder(value: str | None) -> bool:
    if not value or not value.strip():
        return True
    lowered = value.strip().lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def verify_webhook_signature(body: bytes, signature: str | None, secret: str | None = None) -> bool:
    """HMAC-SHA256(webhook_secret, raw_body) compared in constant time."""
    key = (secret if secret is not None else webhook_secret()).encode("utf-8")
    if not signature or not key:
        return False
    expected = hmac.new(key, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def generate_payment_link(
    *,
    amount: Decimal,
    txn_id: str,
    customer_phone: str,
    description: str = "RecoverPay AI recovery payment",
) -> str:
    """Create a Razorpay payment link, or a TEST_MODE ``rzp.io`` stand-in."""
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    if is_test_mode() or _is_placeholder(key_id) or _is_placeholder(key_secret):
        slug = txn_id.replace("-", "")[:12]
        return f"https://rzp.io/l/{slug}"

    import razorpay

    client = razorpay.Client(auth=(key_id, key_secret))
    payload = {
        "amount": int(Decimal(amount) * 100),
        "currency": "INR",
        "description": description,
        "customer": {"contact": customer_phone},
        "notify": {"sms": False, "email": False},
        "reminder_enable": False,
        "reference_id": txn_id[:40],
        "notes": {"recoverpay_txn_id": txn_id},
    }
    created = client.payment_link.create(payload)
    return created.get("short_url") or created.get("url") or f"https://rzp.io/l/{txn_id[:12]}"
