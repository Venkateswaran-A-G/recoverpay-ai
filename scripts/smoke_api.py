"""Live uvicorn smoke checks (not part of pytest)."""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx

BASE = "http://127.0.0.1:8000"
API_KEY = "demo_dashboard_key"
AUTH_HEADERS = {"X-API-KEY": API_KEY}


def main() -> None:
    health = httpx.get(f"{BASE}/health", timeout=10)
    print("health", health.status_code, health.json())

    batch = httpx.post(f"{BASE}/api/v1/simulator/run-batch", params={"count": 10}, headers=AUTH_HEADERS, timeout=30)
    data = batch.json()
    print(
        "batch",
        batch.status_code,
        {k: data[k] for k in ("processed", "flagged_for_approval", "dispatched", "recovered", "opted_out", "states")},
    )

    metrics = httpx.get(f"{BASE}/api/v1/dashboard/metrics", headers=AUTH_HEADERS, timeout=10)
    print("metrics", metrics.status_code, metrics.json())

    bad = httpx.post(
        f"{BASE}/api/v1/webhooks/razorpay",
        content=b"{}",
        headers={"X-Razorpay-Signature": "nope", "Content-Type": "application/json"},
        timeout=10,
    )
    print("bad_hmac", bad.status_code)

    body = json.dumps(
        {
            "entity": "event",
            "event": "payment.failed",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_live_uvicorn",
                        "entity": "payment",
                        "amount": 249900,
                        "currency": "INR",
                        "status": "failed",
                        "email": "meena@example.com",
                        "contact": "+919811122233",
                        "error_code": "INSUFFICIENT_FUNDS",
                        "error_description": "Low balance",
                        "notes": {
                            "merchant_id": "KetoKrafts D2C",
                            "customer_name": "Meena",
                            "customer_state": "Tamil Nadu",
                        },
                    }
                }
            },
        }
    ).encode()
    sig = hmac.new(b"demo_secret_12345", body, hashlib.sha256).hexdigest()
    ok = httpx.post(
        f"{BASE}/api/v1/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
        timeout=10,
    )
    print("good_hmac", ok.status_code, ok.json())

    txns = httpx.get(f"{BASE}/api/v1/transactions", headers=AUTH_HEADERS, timeout=10)
    print("txns", txns.status_code, "count", len(txns.json()), "phone", txns.json()[0]["customer_phone"])

    detail = httpx.get(f"{BASE}/api/v1/audit-logs/{ok.json()['transaction_id']}", headers=AUTH_HEADERS, timeout=10)
    print("audit", detail.status_code, [n["step_name"] for n in detail.json()["execution_graph"]])
    print("OK")


if __name__ == "__main__":
    main()
