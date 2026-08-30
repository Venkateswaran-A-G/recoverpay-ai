"""RecoverPay AI FastAPI service: webhooks, guardrails, metrics, simulator."""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from backend.agent import diagnose_failure, send_live_whatsapp_message
from backend.database import get_db, init_db
from backend.guardrails import evaluate_guardrails
from backend.models import AuditLog, OptOutRegistry, Transaction
from backend.razorpay_client import (
    generate_payment_link,
    is_test_mode,
    verify_webhook_signature,
    webhook_secret,
)
from backend.schemas import (
    OUTREACH_COST_PER_MESSAGE_INR,
    ApproveResponse,
    AuditLogRead,
    AuditStepName,
    AuditStepStatus,
    BatchSimulatorResponse,
    DashboardMetrics,
    ExecutionGraphNode,
    RazorpayFailurePayload,
    RecoveryCopyRequest,
    RecoveryStatus,
    TransactionAuditDetail,
    TransactionPublic,
    WebhookIngestResponse,
    mask_email,
    mask_phone,
)

SIM_STATES = ("Karnataka", "Tamil Nadu", "Telangana", "Maharashtra", "Delhi")
SIM_FAILURES = (
    "BAD_REQUEST_PAYMENT_TIMED_OUT",
    "INSUFFICIENT_FUNDS",
    "AUTHENTICATION_FAILED",
    "EXPIRED_CARD",
    "GATEWAY_ERROR",
)
SIM_NAMES = {
    "Karnataka": ("Ananya", "Ravi"),
    "Tamil Nadu": ("Karthik", "Meena"),
    "Telangana": ("Sravani", "Arjun"),
    "Maharashtra": ("Rohan", "Sneha"),
    "Delhi": ("Priya", "Aman"),
}
OPT_OUT_SIM_PHONE = "+919800000001"
FRONTEND_INDEX = Path(__file__).resolve().parent.parent / "frontend" / "index.html"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="RecoverPay AI",
    description="Event-driven payment recovery engine with financial guardrails.",
    version="0.5.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _dashboard_authorized(x_api_key: str | None) -> None:
    if is_test_mode():
        return
    expected = os.getenv("DASHBOARD_API_KEY", "").strip()
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-KEY")


def write_audit(
    db: Session,
    *,
    transaction_id: str | None,
    step_name: str,
    step_status: str,
    llm_prompt: str | None = None,
    llm_response: str | None = None,
    guardrail_evaluation: dict | None = None,
    raw_payload: dict | None = None,
    execution_time_ms: int | None = None,
) -> AuditLog:
    log = AuditLog(
        transaction_id=transaction_id,
        step_name=step_name,
        step_status=step_status,
        llm_prompt=llm_prompt,
        llm_response=llm_response,
        guardrail_evaluation=guardrail_evaluation,
        raw_payload=raw_payload,
        execution_time_ms=execution_time_ms,
    )
    db.add(log)
    db.flush()
    return log


def extract_customer_state(notes: dict[str, Any] | None) -> str | None:
    if not notes:
        return None
    for key in ("customer_state", "state", "location", "region"):
        value = notes.get(key)
        if value:
            return str(value)
    return None


def _mask_payload(value: Any) -> Any:
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, inner in value.items():
            lowered = key.lower()
            if lowered in {"contact", "customer_phone", "phone", "phone_number"} and inner:
                masked[key] = mask_phone(str(inner))
            elif lowered in {"email", "customer_email"} and inner:
                masked[key] = mask_email(str(inner))
            else:
                masked[key] = _mask_payload(inner)
        return masked
    if isinstance(value, list):
        return [_mask_payload(item) for item in value]
    return value


def public_transaction(txn: Transaction) -> TransactionPublic:
    return TransactionPublic.model_validate(txn)


def public_audit(log: AuditLog) -> AuditLogRead:
    data = AuditLogRead.model_validate(log).model_dump()
    data["raw_payload"] = _mask_payload(data.get("raw_payload"))
    return AuditLogRead.model_validate(data)


def compute_metrics(db: Session) -> DashboardMetrics:
    txns = db.query(Transaction).all()
    total = len(txns)
    failed_volume = sum((Decimal(t.amount) for t in txns), Decimal("0.00"))
    recovered = [t for t in txns if t.recovery_status == RecoveryStatus.RECOVERED.value]
    recovered_revenue = sum((Decimal(t.amount) for t in recovered), Decimal("0.00"))
    dispatch_count = (
        db.query(AuditLog)
        .filter(
            AuditLog.step_name == AuditStepName.DISPATCH.value,
            AuditLog.step_status == AuditStepStatus.SUCCESS.value,
        )
        .count()
    )
    outreach_cost = (OUTREACH_COST_PER_MESSAGE_INR * dispatch_count).quantize(Decimal("0.01"))
    rate = float((recovered_revenue / failed_volume * 100) if failed_volume else 0)
    roi = float((recovered_revenue / outreach_cost) if outreach_cost else 0)
    return DashboardMetrics(
        total_failed_volume=failed_volume.quantize(Decimal("0.01")),
        recovered_revenue=recovered_revenue.quantize(Decimal("0.01")),
        recovery_rate_percent=round(rate, 2),
        outreach_cost=outreach_cost,
        net_roi=round(roi, 2),
        total_transactions=total,
        recovered_count=len(recovered),
        flagged_for_approval_count=sum(
            1 for t in txns if t.recovery_status == RecoveryStatus.FLAGGED_FOR_APPROVAL.value
        ),
        opted_out_count=sum(1 for t in txns if t.recovery_status == RecoveryStatus.OPTED_OUT.value),
        max_retries_reached_count=sum(
            1 for t in txns if t.recovery_status == RecoveryStatus.MAX_RETRIES_REACHED.value
        ),
    )


def dispatch_recovery(db: Session, txn: Transaction) -> tuple[str | None, bool]:
    """Generate link, run regional agent, log dispatch. Never called for blocked txns."""
    started = time.perf_counter()
    link = generate_payment_link(
        amount=Decimal(txn.amount),
        txn_id=txn.id,
        customer_phone=txn.customer_phone,
    )
    write_audit(
        db,
        transaction_id=txn.id,
        step_name=AuditStepName.PAYMENT_LINK_GEN.value,
        step_status=AuditStepStatus.SUCCESS.value,
        raw_payload={"payment_link": link},
        execution_time_ms=int((time.perf_counter() - started) * 1000),
    )

    first_name = (txn.customer_name or "there").split()[0]
    request = RecoveryCopyRequest(
        merchant_name=txn.merchant_id,
        customer_first_name=first_name,
        order_amount=Decimal(txn.amount),
        currency=txn.currency,
        failure_code=txn.failure_code,
        failure_description=txn.failure_reason,
        payment_link=link,
        retry_attempt=int(txn.retry_count) + 1,
        customer_state=txn.customer_state,
    )
    started = time.perf_counter()
    diagnostic = diagnose_failure(request)
    elapsed = int((time.perf_counter() - started) * 1000)
    step = (
        AuditStepName.LLM_FALLBACK_TRIGGERED.value
        if diagnostic.used_fallback
        else AuditStepName.LLM_DIAGNOSIS.value
    )
    write_audit(
        db,
        transaction_id=txn.id,
        step_name=step,
        step_status=AuditStepStatus.SUCCESS.value,
        llm_prompt=request.model_dump_json(),
        llm_response=diagnostic.model_dump_json(),
        execution_time_ms=elapsed,
    )

    txn.retry_count = int(txn.retry_count) + 1
    txn.recovery_status = RecoveryStatus.RECOVERY_DISPATCHED.value
    write_audit(
        db,
        transaction_id=txn.id,
        step_name=AuditStepName.DISPATCH.value,
        step_status=AuditStepStatus.SUCCESS.value,
        llm_response=diagnostic.hinglish_message,
        raw_payload={
            "channel": "whatsapp_sandbox",
            "test_mode": is_test_mode(),
            "language_register": diagnostic.language_register.value,
        },
    )

    # ── Live WhatsApp via Twilio Sandbox ──────────────────────────────────────
    # Always attempts the customer's own phone first; falls back to the
    # operator's personal number (MY_PERSONAL_WHATSAPP) when the customer
    # phone is unavailable.  Both calls are fire-and-forget — failures are
    # logged to stderr but never raise so the pipeline is never blocked.
    personal_wa = os.getenv("MY_PERSONAL_WHATSAPP", "")
    target_phones: list[str] = []
    if txn.customer_phone and txn.customer_phone.strip():
        target_phones.append(txn.customer_phone.strip())
    if personal_wa and personal_wa.strip():
        target_phones.append(personal_wa.strip())

    for phone in target_phones:
        send_live_whatsapp_message(phone, diagnostic.hinglish_message)
    # ─────────────────────────────────────────────────────────────────────────

    return diagnostic.language_register.value, diagnostic.used_fallback


def process_failure_event(
    db: Session,
    *,
    razorpay_payment_id: str | None,
    merchant_id: str,
    customer_name: str | None,
    customer_phone: str,
    customer_email: str | None,
    amount: Decimal,
    currency: str,
    failure_code: str,
    failure_reason: str | None,
    customer_state: str | None,
    retry_count: int = 0,
    raw_payload: dict | None = None,
) -> WebhookIngestResponse:
    if razorpay_payment_id:
        existing = (
            db.query(Transaction)
            .filter(Transaction.razorpay_payment_id == razorpay_payment_id)
            .first()
        )
        if existing:
            return WebhookIngestResponse(
                accepted=True,
                transaction_id=existing.id,
                recovery_status=existing.recovery_status,
                requires_human_approval=existing.recovery_status
                == RecoveryStatus.FLAGGED_FOR_APPROVAL.value,
                already_processed=True,
            )

    txn = Transaction(
        merchant_id=merchant_id[:50],
        razorpay_payment_id=razorpay_payment_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email,
        amount=amount,
        currency=currency or "INR",
        failure_code=failure_code,
        failure_reason=failure_reason,
        customer_state=customer_state,
        retry_count=retry_count,
        recovery_status=RecoveryStatus.PENDING.value,
    )
    db.add(txn)
    db.flush()

    write_audit(
        db,
        transaction_id=txn.id,
        step_name=AuditStepName.INGESTION.value,
        step_status=AuditStepStatus.SUCCESS.value,
        raw_payload=raw_payload,
    )

    started = time.perf_counter()
    guardrail = evaluate_guardrails(txn, db, persist=True)
    write_audit(
        db,
        transaction_id=txn.id,
        step_name=AuditStepName.GUARDRAIL_CHECK.value,
        step_status=(
            AuditStepStatus.SUCCESS.value if guardrail.passed else AuditStepStatus.WARNING.value
        ),
        guardrail_evaluation=guardrail.model_dump(mode="json"),
        execution_time_ms=int((time.perf_counter() - started) * 1000),
    )

    language_register: str | None = None
    if guardrail.blocked:
        db.commit()
        return WebhookIngestResponse(
            accepted=True,
            transaction_id=txn.id,
            recovery_status=txn.recovery_status,
            requires_human_approval=False,
        )

    if guardrail.requires_human_approval:
        db.commit()
        return WebhookIngestResponse(
            accepted=True,
            transaction_id=txn.id,
            recovery_status=txn.recovery_status,
            requires_human_approval=True,
        )

    language_register, _ = dispatch_recovery(db, txn)
    db.commit()
    return WebhookIngestResponse(
        accepted=True,
        transaction_id=txn.id,
        recovery_status=txn.recovery_status,
        requires_human_approval=False,
        language_register=language_register,
    )


def _maybe_simulate_recovery(db: Session, txn: Transaction, recover: bool) -> None:
    if not recover or not is_test_mode():
        return
    if txn.recovery_status != RecoveryStatus.RECOVERY_DISPATCHED.value:
        return
    txn.recovery_status = RecoveryStatus.RECOVERED.value
    write_audit(
        db,
        transaction_id=txn.id,
        step_name="SIMULATED_RECOVERY",
        step_status=AuditStepStatus.SUCCESS.value,
        raw_payload={"test_mode": True},
    )


@app.get("/", include_in_schema=False)
def serve_dashboard():
    if not FRONTEND_INDEX.is_file():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    html_content = FRONTEND_INDEX.read_text(encoding="utf-8")
    return HTMLResponse(
        content=html_content,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "recoverpay-ai", "test_mode": is_test_mode()}


@app.post("/api/v1/webhooks/razorpay", response_model=WebhookIngestResponse, status_code=202)
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)) -> WebhookIngestResponse:
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    if not verify_webhook_signature(body, signature, webhook_secret()):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        event = json.loads(body.decode("utf-8"))
        payload = RazorpayFailurePayload.model_validate(event)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook payload: {exc}") from exc

    payment = payload.payment
    notes = payment.notes or {}
    return process_failure_event(
        db,
        razorpay_payment_id=payment.id,
        merchant_id=str(notes.get("merchant_id") or notes.get("merchant_name") or "demo_merchant"),
        customer_name=str(notes.get("customer_name") or notes.get("name") or "Customer"),
        customer_phone=payment.contact,
        customer_email=str(payment.email) if payment.email else None,
        amount=payload.amount_inr,
        currency=payment.currency,
        failure_code=payment.error_code or payment.error_reason or "PAYMENT_FAILED",
        failure_reason=payment.error_description,
        customer_state=extract_customer_state(notes),
        raw_payload=event,
    )


@app.get("/api/v1/dashboard/metrics", response_model=DashboardMetrics)
def dashboard_metrics(
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-KEY"),
) -> DashboardMetrics:
    _dashboard_authorized(x_api_key)
    return compute_metrics(db)


@app.get("/api/v1/transactions", response_model=list[TransactionPublic])
def list_transactions(
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-KEY"),
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[TransactionPublic]:
    _dashboard_authorized(x_api_key)
    query = db.query(Transaction).order_by(Transaction.created_at.desc())
    if status:
        query = query.filter(Transaction.recovery_status == status)
    return [public_transaction(txn) for txn in query.offset(offset).limit(limit).all()]


@app.get("/api/v1/audit-logs", response_model=list[AuditLogRead])
def list_audit_logs(
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-KEY"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AuditLogRead]:
    _dashboard_authorized(x_api_key)
    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [public_audit(row) for row in rows]


@app.get("/api/v1/audit-logs/{record_id}", response_model=TransactionAuditDetail)
def get_audit_detail(
    record_id: str,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-KEY"),
) -> TransactionAuditDetail:
    _dashboard_authorized(x_api_key)
    txn = db.get(Transaction, record_id)
    if txn is None:
        log = db.get(AuditLog, record_id)
        if log is None or not log.transaction_id:
            raise HTTPException(status_code=404, detail="Audit record not found")
        txn = db.get(Transaction, log.transaction_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    logs = (
        db.query(AuditLog)
        .filter(AuditLog.transaction_id == txn.id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    graph = [
        ExecutionGraphNode(
            step_name=item.step_name,
            step_status=item.step_status,
            execution_time_ms=item.execution_time_ms,
        )
        for item in logs
    ]
    return TransactionAuditDetail(
        transaction=public_transaction(txn),
        audit_logs=[public_audit(item) for item in logs],
        execution_graph=graph,
    )


@app.post("/api/v1/guardrails/approve/{transaction_id}", response_model=ApproveResponse)
def approve_high_value(
    transaction_id: str,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-KEY"),
) -> ApproveResponse:
    _dashboard_authorized(x_api_key)
    txn = db.get(Transaction, transaction_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if txn.recovery_status != RecoveryStatus.FLAGGED_FOR_APPROVAL.value:
        raise HTTPException(
            status_code=409,
            detail=f"Transaction is {txn.recovery_status}, not FLAGGED_FOR_APPROVAL",
        )

    language_register, _ = dispatch_recovery(db, txn)
    db.commit()
    return ApproveResponse(
        transaction_id=txn.id,
        recovery_status=txn.recovery_status,
        requires_human_approval=False,
        language_register=language_register,
        message="High-value recovery approved and dispatched",
    )


@app.post("/api/v1/simulator/run-batch", response_model=BatchSimulatorResponse)
def run_batch_simulator(
    count: int = Query(default=20, ge=1, le=100),
    simulate_recoveries: bool = Query(default=True),
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-KEY"),
) -> BatchSimulatorResponse:
    _dashboard_authorized(x_api_key)
    if db.get(OptOutRegistry, OPT_OUT_SIM_PHONE) is None:
        db.add(OptOutRegistry(phone_number=OPT_OUT_SIM_PHONE, opt_out_source="SMS_STOP"))
        db.flush()

    flagged = opted = dispatched = recovered = max_retries = 0
    for index in range(count):
        state = SIM_STATES[index % len(SIM_STATES)]
        names = SIM_NAMES[state]
        name = names[index % len(names)]
        amount = Decimal("1499.00")
        retry_count = 0
        phone = f"+9198{index:08d}"
        if index % 7 == 0:
            amount = Decimal("7500.00")
        elif index % 11 == 0:
            amount = Decimal("12000.00")
        elif index % 5 == 0:
            retry_count = 2
        if index % 13 == 0:
            phone = OPT_OUT_SIM_PHONE

        result = process_failure_event(
            db,
            razorpay_payment_id=f"pay_sim_{uuid.uuid4().hex[:14]}",
            merchant_id="KetoKrafts D2C",
            customer_name=name,
            customer_phone=phone,
            customer_email=f"{name.lower()}@example.com",
            amount=amount,
            currency="INR",
            failure_code=SIM_FAILURES[index % len(SIM_FAILURES)],
            failure_reason=f"Simulated {SIM_FAILURES[index % len(SIM_FAILURES)]} from {state}",
            customer_state=state,
            retry_count=retry_count,
            raw_payload={"simulator": True, "state": state, "index": index},
        )
        txn = db.get(Transaction, result.transaction_id)
        if txn is None:
            continue
        if txn.recovery_status == RecoveryStatus.FLAGGED_FOR_APPROVAL.value:
            flagged += 1
        elif txn.recovery_status == RecoveryStatus.OPTED_OUT.value:
            opted += 1
        elif txn.recovery_status == RecoveryStatus.MAX_RETRIES_REACHED.value:
            max_retries += 1
        elif txn.recovery_status == RecoveryStatus.RECOVERY_DISPATCHED.value:
            dispatched += 1
            should_recover = simulate_recoveries and (index % 3 != 0)
            _maybe_simulate_recovery(db, txn, should_recover)
            if txn.recovery_status == RecoveryStatus.RECOVERED.value:
                recovered += 1
                db.commit()

    return BatchSimulatorResponse(
        count=count,
        processed=count,
        flagged_for_approval=flagged,
        opted_out=opted,
        dispatched=dispatched,
        recovered=recovered,
        max_retries_reached=max_retries,
        states=list(SIM_STATES),
        metrics=compute_metrics(db),
    )
