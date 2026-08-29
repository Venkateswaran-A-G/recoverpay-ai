"""FastAPI webhook, guardrails, metrics, and simulator tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("TEST_MODE", "true")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "demo_secret_12345")

from backend.database import get_db
from backend.main import app
from backend.models import Base, OptOutRegistry, Transaction
from backend.schemas import RecoveryStatus


SECRET = "demo_secret_12345"


def _sign(body: bytes) -> str:
    return hmac.new(SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, future=True)

    def _override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as test_client:
        yield test_client, SessionLocal
    app.dependency_overrides.clear()


def _webhook_body(**overrides) -> dict:
    entity = {
        "id": "pay_test_abc",
        "entity": "payment",
        "amount": 149900,
        "currency": "INR",
        "status": "failed",
        "email": "rahul@example.com",
        "contact": "+919876543210",
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "Issuer timed out",
        "error_reason": "payment_timed_out",
        "notes": {
            "merchant_id": "KetoKrafts D2C",
            "customer_name": "Rahul",
            "customer_state": "Karnataka",
        },
    }
    entity.update(overrides.pop("entity_overrides", {}))
    notes = entity.get("notes", {})
    notes.update(overrides.pop("notes", {}))
    entity["notes"] = notes
    return {
        "entity": "event",
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {"payment": {"entity": entity}},
    }


def test_dashboard_served_at_root(client):
    test_client, _ = client
    response = test_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "RazorpayX | RecoverPay AI Engine" in response.text
    assert "Simulate 20 Failed Payments" in response.text
    assert "Inspect Audit" in response.text
    assert "#080a0f" in response.text
    assert "Net Outreach ROI" in response.text
    assert "Amber Shield" in response.text


def test_webhook_rejects_invalid_hmac(client):
    test_client, _ = client
    body = json.dumps(_webhook_body()).encode()
    response = test_client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "deadbeef"},
    )
    assert response.status_code == 401


def test_webhook_accepts_valid_hmac_and_dispatches_under_threshold(client):
    test_client, SessionLocal = client
    payload = _webhook_body()
    body = json.dumps(payload).encode()
    response = test_client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(body)},
    )
    assert response.status_code == 202
    data = response.json()
    assert data["recovery_status"] == RecoveryStatus.RECOVERY_DISPATCHED.value
    assert data["requires_human_approval"] is False
    assert data["language_register"] == "kannada_english"

    db = SessionLocal()
    try:
        txn = db.get(Transaction, data["transaction_id"])
        assert txn is not None
        assert txn.customer_state == "Karnataka"
        steps = {log.step_name for log in txn.audit_logs}
        assert "INGESTION" in steps
        assert "GUARDRAIL_CHECK" in steps
        assert "DISPATCH" in steps
    finally:
        db.close()


def test_high_value_webhook_is_flagged_not_dispatched(client):
    test_client, _ = client
    payload = _webhook_body(entity_overrides={"id": "pay_high", "amount": 750000})
    body = json.dumps(payload).encode()
    response = test_client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(body)},
    )
    assert response.status_code == 202
    data = response.json()
    assert data["requires_human_approval"] is True
    assert data["recovery_status"] == RecoveryStatus.FLAGGED_FOR_APPROVAL.value

    approve = test_client.post(f"/api/v1/guardrails/approve/{data['transaction_id']}")
    assert approve.status_code == 200
    assert approve.json()["recovery_status"] == RecoveryStatus.RECOVERY_DISPATCHED.value


def test_opted_out_webhook_stops(client):
    test_client, SessionLocal = client
    db = SessionLocal()
    try:
        db.add(OptOutRegistry(phone_number="+919876543210", opt_out_source="SMS_STOP"))
        db.commit()
    finally:
        db.close()

    payload = _webhook_body(entity_overrides={"id": "pay_optout"})
    body = json.dumps(payload).encode()
    response = test_client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(body)},
    )
    assert response.json()["recovery_status"] == RecoveryStatus.OPTED_OUT.value


def test_transactions_mask_pii(client):
    test_client, _ = client
    payload = _webhook_body(entity_overrides={"id": "pay_pii"})
    body = json.dumps(payload).encode()
    test_client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(body)},
    )
    listed = test_client.get("/api/v1/transactions").json()
    assert listed
    assert listed[0]["customer_phone"] == "+91 98*****3210"
    assert listed[0]["customer_email"] == "r***@example.com"


def test_audit_logs_detail_and_metrics_and_batch(client):
    test_client, _ = client
    batch = test_client.post("/api/v1/simulator/run-batch?count=10")
    assert batch.status_code == 200
    body = batch.json()
    assert body["processed"] == 10
    assert set(body["states"]) == {
        "Karnataka",
        "Tamil Nadu",
        "Telangana",
        "Maharashtra",
        "Delhi",
    }
    assert body["flagged_for_approval"] >= 1

    metrics = test_client.get("/api/v1/dashboard/metrics").json()
    assert metrics["total_transactions"] >= 10
    assert float(metrics["total_failed_volume"]) > 0

    txns = test_client.get("/api/v1/transactions").json()
    detail = test_client.get(f"/api/v1/audit-logs/{txns[0]['id']}")
    assert detail.status_code == 200
    graph = detail.json()["execution_graph"]
    assert graph
    assert graph[0]["step_name"] == "INGESTION"
