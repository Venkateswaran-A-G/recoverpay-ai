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

# Force test-safe env before any backend imports so dotenv cannot override these
os.environ["TEST_MODE"] = "true"
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "demo_secret_12345")

from backend.database import get_db
from backend.main import app, whatsapp_payment_link
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
    assert 'darkMode: "class"' in response.text
    assert "themeToggle" in response.text
    assert "recoverpay-theme" in response.text
    assert "☀️ Light" in response.text
    assert "🌙 Dark" in response.text
    assert "searchInput" in response.text
    assert "All Amounts" in response.text
    assert "Under ₹2,000" in response.text
    assert "All Statuses" in response.text
    assert "Flagged" in response.text
    assert "All Regions" in response.text
    assert "Karnataka (Kanglish)" in response.text
    assert "filteredTxns" in response.text
    assert 'if (!res.ok)' in response.text
    assert "Simulation failed" in response.text
    assert "Stage-by-Stage Recovery Conversion Funnel" in response.text
    assert "Failure Reason Breakdown" in response.text
    assert "Human Review Queue" in response.text
    assert "TEMPORARY_BANK_DEGRADATION" in response.text
    assert "bg-gradient-to-r from-rose-600 via-rose-500 to-pink-500" in response.text
    assert "luxury-fill" in response.text
    assert "% yield" in response.text
    assert "mermaid" not in response.text.lower()


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

    approve = test_client.post(f"/api/v1/guardrails/approve/{data['transaction_id']}", headers={"X-API-KEY": "demo_dashboard_key"})
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
    listed = test_client.get("/api/v1/transactions", headers={"X-API-KEY": "demo_dashboard_key"}).json()
    assert listed
    assert listed[0]["customer_phone"] == "+91 98*****3210"
    assert listed[0]["customer_email"] == "r***@example.com"


def test_audit_logs_detail_and_metrics_and_batch(client):
    test_client, _ = client
    batch = test_client.post("/api/v1/simulator/run-batch?count=10", headers={"X-API-KEY": "demo_dashboard_key"})
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

    metrics = test_client.get("/api/v1/dashboard/metrics", headers={"X-API-KEY": "demo_dashboard_key"}).json()
    assert metrics["total_transactions"] >= 10
    assert float(metrics["total_failed_volume"]) > 0
    assert metrics["failed_ingested"] == metrics["total_transactions"]
    assert "funnel" in metrics
    assert metrics["funnel"]["failed_ingested"] == metrics["failed_ingested"]
    assert set(metrics["failure_breakdown"]) == {
        "TEMPORARY_BANK_DEGRADATION",
        "AUTHENTICATION_ISSUE",
        "INSUFFICIENT_FUNDS",
        "EXPIRED_METHOD",
        "CHECKOUT_ABANDONMENT",
    }

    txns = test_client.get("/api/v1/transactions", headers={"X-API-KEY": "demo_dashboard_key"}).json()
    detail = test_client.get(f"/api/v1/audit-logs/{txns[0]['id']}", headers={"X-API-KEY": "demo_dashboard_key"})
    assert detail.status_code == 200
    graph = detail.json()["execution_graph"]
    assert graph
    assert graph[0]["step_name"] == "INGESTION"


def test_voice_approve_and_call_high_value(client):
    test_client, _ = client
    payload = _webhook_body(entity_overrides={"id": "pay_voice", "amount": 2500000})
    body = json.dumps(payload).encode()
    ingest = test_client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(body)},
    )
    assert ingest.status_code == 202
    txn_id = ingest.json()["transaction_id"]
    assert ingest.json()["recovery_status"] == RecoveryStatus.REQUIRES_VOICE_CALL_PERMISSION.value

    too_low = _webhook_body(entity_overrides={"id": "pay_voice_low", "amount": 750000})
    low_body = json.dumps(too_low).encode()
    low_ingest = test_client.post(
        "/api/v1/webhooks/razorpay",
        content=low_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(low_body)},
    )
    low_id = low_ingest.json()["transaction_id"]
    blocked = test_client.post(
        f"/api/v1/voice/approve-and-call/{low_id}",
        headers={"X-API-KEY": "demo_dashboard_key"},
    )
    assert blocked.status_code == 409

    approve = test_client.post(
        f"/api/v1/voice/approve-and-call/{txn_id}",
        headers={"X-API-KEY": "demo_dashboard_key"},
    )
    assert approve.status_code == 200
    data = approve.json()
    assert data["recovery_status"] == RecoveryStatus.RECOVERED.value

    detail = test_client.get(f"/api/v1/audit-logs/{txn_id}", headers={"X-API-KEY": "demo_dashboard_key"})
    steps = {row["step_name"] for row in detail.json()["audit_logs"]}
    assert "REAL_PHONE_VOICE_CALL_PLACED" in steps
    assert "HIGH_VALUE_VOICE_RECOVERY_CONFIRMED" in steps


def test_voice_call_not_auto_dialed_and_can_be_declined(client):
    test_client, _ = client
    payload = _webhook_body(entity_overrides={"id": "pay_voice_decline", "amount": 3500000})
    body = json.dumps(payload).encode()
    ingest = test_client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(body)},
    )
    assert ingest.json()["recovery_status"] == RecoveryStatus.REQUIRES_VOICE_CALL_PERMISSION.value
    decline = test_client.post(
        f"/api/v1/voice/decline/{ingest.json()['transaction_id']}",
        headers={"X-API-KEY": "demo_dashboard_key"},
    )
    assert decline.status_code == 200
    assert decline.json()["recovery_status"] == RecoveryStatus.VOICE_CALL_DECLINED.value


def test_batch_simulator_exactly_one_voice_permission_txn(client):
    test_client, _ = client
    batch = test_client.post(
        "/api/v1/simulator/run-batch?count=20&simulate_recoveries=false",
        headers={"X-API-KEY": "demo_dashboard_key"},
    )
    assert batch.status_code == 200
    txns = test_client.get(
        "/api/v1/transactions?limit=200",
        headers={"X-API-KEY": "demo_dashboard_key"},
    ).json()
    over_20k = [t for t in txns if float(t["amount"]) > 20000]
    under_19k = [t for t in txns if float(t["amount"]) < 19000]
    assert len(over_20k) == 1
    assert len(under_19k) == 19
    assert float(over_20k[0]["amount"]) in {25000.0, 35000.0, 45000.0}
    assert over_20k[0]["recovery_status"] == RecoveryStatus.REQUIRES_VOICE_CALL_PERMISSION.value
    assert all(t["recovery_status"] != RecoveryStatus.VOICE_CALL_DISPATCHED.value for t in txns)


def test_batch_simulator_recovers_about_72_percent_under_5k(client):
    test_client, _ = client
    batch = test_client.post(
        "/api/v1/simulator/run-batch?count=20",
        headers={"X-API-KEY": "demo_dashboard_key"},
    )
    assert batch.status_code == 200
    txns = test_client.get(
        "/api/v1/transactions?limit=200",
        headers={"X-API-KEY": "demo_dashboard_key"},
    ).json()
    under_5k = [t for t in txns if float(t["amount"]) < 5000]
    recovered = [t for t in under_5k if t["recovery_status"] == RecoveryStatus.RECOVERED.value]
    dispatched = [t for t in under_5k if t["recovery_status"] == RecoveryStatus.RECOVERY_DISPATCHED.value]
    convertible = recovered + dispatched
    assert convertible
    share = len(recovered) / len(convertible)
    assert 0.68 <= share <= 0.80
    over_20k = [t for t in txns if float(t["amount"]) > 20000]
    assert len(over_20k) == 1
    assert over_20k[0]["recovery_status"] == RecoveryStatus.REQUIRES_VOICE_CALL_PERMISSION.value
    metrics = test_client.get("/api/v1/dashboard/metrics", headers={"X-API-KEY": "demo_dashboard_key"}).json()
    assert 68.0 <= metrics["recovery_rate_percent"] <= 75.0
    assert metrics["recovery_rate_percentage"] == metrics["recovery_rate_percent"]


def test_whatsapp_payment_link_click_marks_recovered(client):
    test_client, _ = client
    payload = _webhook_body(entity_overrides={"id": "pay_click"})
    body = json.dumps(payload).encode()
    ingest = test_client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(body)},
    )
    txn_id = ingest.json()["transaction_id"]
    assert ingest.json()["recovery_status"] == RecoveryStatus.RECOVERY_DISPATCHED.value
    clicked = test_client.get(f"/api/v1/recovery/pay/{txn_id}")
    assert clicked.status_code == 200
    detail = test_client.get(f"/api/v1/audit-logs/{txn_id}", headers={"X-API-KEY": "demo_dashboard_key"})
    assert detail.json()["transaction"]["recovery_status"] == RecoveryStatus.RECOVERED.value
    steps = {row["step_name"] for row in detail.json()["audit_logs"]}
    assert "PAYMENT_EVIDENCE_CONFIRMED" in steps


def _paid_body(txn_id: str, payment_id: str = "pay_recovered_1") -> dict:
    return {
        "entity": "event",
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink_test",
                    "short_url": f"https://rzp.io/l/{txn_id.replace('-', '')[:12]}",
                    "notes": {"recoverpay_txn_id": txn_id},
                    "reference_id": txn_id,
                }
            },
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 149900,
                    "currency": "INR",
                    "status": "captured",
                }
            },
        },
    }


def test_razorpay_paid_webhook_rejects_invalid_hmac(client):
    test_client, _ = client
    body = json.dumps(_paid_body("missing")).encode()
    response = test_client.post(
        "/api/v1/webhooks/razorpay-paid",
        content=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "deadbeef"},
    )
    assert response.status_code == 401


def test_razorpay_paid_webhook_marks_recovered(client):
    test_client, _ = client
    ingest_payload = _webhook_body(entity_overrides={"id": "pay_to_recover"})
    ingest_body = json.dumps(ingest_payload).encode()
    ingest = test_client.post(
        "/api/v1/webhooks/razorpay",
        content=ingest_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(ingest_body)},
    )
    txn_id = ingest.json()["transaction_id"]
    paid = json.dumps(_paid_body(txn_id)).encode()
    response = test_client.post(
        "/api/v1/webhooks/razorpay-paid",
        content=paid,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(paid)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["recovery_status"] == RecoveryStatus.RECOVERED.value
    detail = test_client.get(f"/api/v1/audit-logs/{txn_id}", headers={"X-API-KEY": "demo_dashboard_key"})
    steps = {row["step_name"] for row in detail.json()["audit_logs"]}
    assert "PAYMENT_EVIDENCE_CONFIRMED" in steps
    metrics = test_client.get("/api/v1/dashboard/metrics", headers={"X-API-KEY": "demo_dashboard_key"}).json()
    assert metrics["payment_verified"] >= 1


def test_approve_all_pending_reviews(client):
    test_client, _ = client
    payload = _webhook_body(entity_overrides={"id": "pay_flag_batch", "amount": 750000})
    body = json.dumps(payload).encode()
    test_client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(body)},
    )
    result = test_client.post(
        "/api/v1/guardrails/approve-all",
        headers={"X-API-KEY": "demo_dashboard_key"},
    )
    assert result.status_code == 200
    assert result.json()["approved"] >= 1


def test_whatsapp_payment_link_never_uses_localhost(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    txn_id = "a5ece3b6-1f02-4200-baf9-0c1b9310c831"
    link = whatsapp_payment_link(txn_id, "https://rzp.io/l/abc123def456")
    assert link.startswith("https://")
    assert "rzp.io" not in link
    assert txn_id in link
    assert "recovery/pay" in link
    from backend.agent import is_whatsapp_linkifiable

    assert is_whatsapp_linkifiable(link) is True


def test_whatsapp_payment_link_uses_public_recover_url(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://demo.recoverpay.test")
    txn_id = "a5ece3b6-1f02-4200-baf9-0c1b9310c831"
    link = whatsapp_payment_link(txn_id, "https://rzp.io/l/should-not-win")
    assert link == f"https://demo.recoverpay.test/api/v1/recovery/pay/{txn_id}"

