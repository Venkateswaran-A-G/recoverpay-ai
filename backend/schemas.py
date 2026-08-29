"""Pydantic v2 request / response schemas for RecoverPay AI.

ORM models stay in ``backend/database.py``; this module is the typed API
and LLM-output contract layer (ConfigDict(from_attributes=True)).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# --- Guardrail constants (deterministic, non-LLM) ---
FINANCIAL_THRESHOLD_INR = Decimal("5000.00")
MAX_RETRY_COUNT = 2


class RecoveryStatus(str, Enum):
    PENDING = "PENDING"
    RECOVERY_DISPATCHED = "RECOVERY_DISPATCHED"
    RECOVERED = "RECOVERED"
    FLAGGED_FOR_APPROVAL = "FLAGGED_FOR_APPROVAL"
    FAILED_GUARDRAIL = "FAILED_GUARDRAIL"
    OPTED_OUT = "OPTED_OUT"
    MAX_RETRIES_REACHED = "MAX_RETRIES_REACHED"
    PENDING_RETRY = "PENDING_RETRY"


class AuditStepName(str, Enum):
    INGESTION = "INGESTION"
    LLM_DIAGNOSIS = "LLM_DIAGNOSIS"
    LLM_FALLBACK_TRIGGERED = "LLM_FALLBACK_TRIGGERED"
    GUARDRAIL_CHECK = "GUARDRAIL_CHECK"
    PAYMENT_LINK_GEN = "PAYMENT_LINK_GEN"
    DISPATCH = "DISPATCH"


class AuditStepStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    WARNING = "WARNING"
    BYPASSED = "BYPASSED"


class OptOutSource(str, Enum):
    WHATSAPP_REPLY = "WHATSAPP_REPLY"
    MANUAL_MERCHANT = "MANUAL_MERCHANT"
    SMS_STOP = "SMS_STOP"


class FailureCategory(str, Enum):
    TEMPORARY_OUTAGE = "TEMPORARY_OUTAGE"
    USER_DROPOFF = "USER_DROPOFF"
    EXPIRED_CARD = "EXPIRED_CARD"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"


# ---------------------------------------------------------------------------
# PII helpers (frontend / audit display)
# ---------------------------------------------------------------------------


def mask_phone(phone: str) -> str:
    """Mask a phone number as ``+91 98*****1234``."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) >= 10:
        local = digits[-10:]
        return f"+91 {local[:2]}*****{local[-4:]}"
    return "****"


def mask_email(email: Optional[str]) -> Optional[str]:
    """Mask an email as ``r***@domain.com``."""
    if not email or "@" not in email:
        return email
    local, _, domain = email.partition("@")
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


# ---------------------------------------------------------------------------
# Razorpay webhook payload
# ---------------------------------------------------------------------------


class RazorpayPaymentEntity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    entity: str = "payment"
    amount: int = Field(..., description="Amount in paise (Razorpay native unit)")
    currency: str = "INR"
    status: str
    order_id: Optional[str] = None
    method: Optional[str] = None
    email: Optional[EmailStr] = None
    contact: str
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    error_reason: Optional[str] = None
    notes: dict[str, Any] = Field(default_factory=dict)


class RazorpayPaymentWrapper(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entity: RazorpayPaymentEntity


class RazorpayWebhookInnerPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    payment: RazorpayPaymentWrapper


class RazorpayFailurePayload(BaseModel):
    """Incoming Razorpay ``payment.failed`` / ``subscription.halted`` webhook body."""

    model_config = ConfigDict(extra="ignore")

    entity: str = "event"
    account_id: Optional[str] = None
    event: str
    contains: list[str] = Field(default_factory=list)
    payload: RazorpayWebhookInnerPayload

    @property
    def payment(self) -> RazorpayPaymentEntity:
        return self.payload.payment.entity

    @property
    def amount_inr(self) -> Decimal:
        return (Decimal(self.payment.amount) / Decimal("100")).quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# LLM structured output
# ---------------------------------------------------------------------------


class LLMDiagnosticOutput(BaseModel):
    """Typed JSON contract for GPT-4o-mini diagnostic + Hinglish copy."""

    model_config = ConfigDict(extra="ignore")

    failure_category: Literal[
        "TEMPORARY_OUTAGE",
        "USER_DROPOFF",
        "EXPIRED_CARD",
        "INSUFFICIENT_FUNDS",
        "AUTHENTICATION_FAILED",
    ]
    diagnostic_summary: str = Field(..., min_length=5, max_length=500)
    hinglish_message: str = Field(..., min_length=10, max_length=300)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    contains_payment_link: bool
    used_fallback: bool = False

    @field_validator("hinglish_message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        return value.strip()


# ---------------------------------------------------------------------------
# Guardrails engine result
# ---------------------------------------------------------------------------


class GuardrailEvaluationResult(BaseModel):
    """Deterministic safety state-machine output (never produced by the LLM)."""

    model_config = ConfigDict(extra="ignore")

    passed: bool
    requires_human_approval: bool = False
    blocked: bool = False
    recovery_status: RecoveryStatus
    reasons: list[str] = Field(default_factory=list)
    retry_count: int = Field(default=0, ge=0)
    amount: Decimal
    opted_out: bool = False


# ---------------------------------------------------------------------------
# Dashboard metrics
# ---------------------------------------------------------------------------


class DashboardMetrics(BaseModel):
    total_failed_volume: Decimal = Decimal("0.00")
    recovered_revenue: Decimal = Decimal("0.00")
    recovery_rate_percent: float = 0.0
    outreach_cost: Decimal = Decimal("0.00")
    net_roi: float = 0.0
    total_transactions: int = 0
    recovered_count: int = 0
    flagged_for_approval_count: int = 0
    opted_out_count: int = 0
    max_retries_reached_count: int = 0


# ---------------------------------------------------------------------------
# ORM-backed API schemas
# ---------------------------------------------------------------------------


class TransactionCreate(BaseModel):
    razorpay_payment_id: Optional[str] = None
    merchant_id: str
    customer_name: Optional[str] = None
    customer_phone: str
    customer_email: Optional[EmailStr] = None
    amount: Decimal = Field(..., gt=0)
    currency: str = "INR"
    failure_code: str
    failure_reason: Optional[str] = None
    recovery_status: RecoveryStatus = RecoveryStatus.PENDING
    retry_count: int = Field(default=0, ge=0)


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    razorpay_payment_id: Optional[str] = None
    merchant_id: str
    customer_name: Optional[str] = None
    customer_phone: str
    customer_email: Optional[str] = None
    amount: Decimal
    currency: str
    failure_code: str
    failure_reason: Optional[str] = None
    recovery_status: str
    retry_count: int
    created_at: datetime
    updated_at: datetime


class TransactionPublic(TransactionRead):
    """Same as TransactionRead with PII masked for dashboard / logs."""

    @field_validator("customer_phone", mode="before")
    @classmethod
    def _mask_phone(cls, value: str) -> str:
        return mask_phone(str(value)) if value else value

    @field_validator("customer_email", mode="before")
    @classmethod
    def _mask_email(cls, value: Optional[str]) -> Optional[str]:
        return mask_email(value)


class AuditLogCreate(BaseModel):
    transaction_id: Optional[str] = None
    step_name: str
    step_status: AuditStepStatus
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None
    guardrail_evaluation: Optional[dict[str, Any]] = None
    raw_payload: Optional[dict[str, Any]] = None
    execution_time_ms: Optional[int] = None


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transaction_id: Optional[str] = None
    step_name: str
    step_status: str
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None
    guardrail_evaluation: Optional[dict[str, Any]] = None
    raw_payload: Optional[dict[str, Any]] = None
    execution_time_ms: Optional[int] = None
    created_at: datetime


class OptOutCreate(BaseModel):
    phone_number: str
    opt_out_source: Optional[OptOutSource] = None


class OptOutRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    phone_number: str
    opt_out_source: Optional[str] = None
    created_at: datetime
