"""Pydantic v2 request / response schemas for RecoverPay AI.

ORM models stay in ``backend/models.py``; this module is the typed API
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
VOICE_CALL_THRESHOLD_INR = Decimal("20000.00")
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
    BANK_OUTAGE_HOLD = "BANK_OUTAGE_HOLD"
    RETRY_SCHEDULED_POST_BANK_RECOVERY = "RETRY_SCHEDULED_POST_BANK_RECOVERY"
    REQUIRES_VOICE_CALL_PERMISSION = "REQUIRES_VOICE_CALL_PERMISSION"
    VOICE_CALL_DISPATCHED = "VOICE_CALL_DISPATCHED"
    VOICE_CALL_DECLINED = "VOICE_CALL_DECLINED"


class AuditStepName(str, Enum):
    INGESTION = "INGESTION"
    LLM_DIAGNOSIS = "LLM_DIAGNOSIS"
    LLM_FALLBACK_TRIGGERED = "LLM_FALLBACK_TRIGGERED"
    GUARDRAIL_CHECK = "GUARDRAIL_CHECK"
    PAYMENT_LINK_GEN = "PAYMENT_LINK_GEN"
    DISPATCH = "DISPATCH"
    REAL_PHONE_VOICE_CALL_PLACED = "REAL_PHONE_VOICE_CALL_PLACED"
    VOICE_CALL_PERMISSION_REQUIRED = "VOICE_CALL_PERMISSION_REQUIRED"
    VOICE_CALL_DECLINED = "VOICE_CALL_DECLINED"
    PAYMENT_EVIDENCE_CONFIRMED = "PAYMENT_EVIDENCE_CONFIRMED"
    PAYMENT_LINK_DECLINED = "PAYMENT_LINK_DECLINED"
    HIGH_VALUE_VOICE_RECOVERY_CONFIRMED = "HIGH_VALUE_VOICE_RECOVERY_CONFIRMED"


class AuditStepStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    WARNING = "WARNING"
    BYPASSED = "BYPASSED"


class OptOutSource(str, Enum):
    WHATSAPP_REPLY = "WHATSAPP_REPLY"
    MANUAL_MERCHANT = "MANUAL_MERCHANT"
    SMS_STOP = "SMS_STOP"
    PAY_LINK_DECLINE = "PAY_LINK_DECLINE"


class FailureCategory(str, Enum):
    TEMPORARY_OUTAGE = "TEMPORARY_OUTAGE"
    USER_DROPOFF = "USER_DROPOFF"
    EXPIRED_CARD = "EXPIRED_CARD"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"


class LanguageRegister(str, Enum):
    """WhatsApp copy register selected from customer state / preference."""

    KANNADA_ENGLISH = "kannada_english"
    TANGLISH = "tanglish"
    TELUGU_ENGLISH = "telugu_english"
    MARATHI_HINGLISH = "marathi_hinglish"
    HINGLISH = "hinglish"
    ENGLISH = "english"


MIN_LLM_CONFIDENCE = 0.75


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


class RecoveryCopyRequest(BaseModel):
    """Operational context sent to the diagnostic agent (no cardholder data)."""

    model_config = ConfigDict(extra="ignore")

    merchant_name: str = "the merchant"
    customer_first_name: str = "there"
    order_amount: Decimal = Field(..., gt=0)
    currency: str = "INR"
    failure_code: str
    failure_description: Optional[str] = None
    payment_link: str = Field(..., min_length=8)
    retry_attempt: int = Field(default=1, ge=0)
    customer_state: Optional[str] = None
    language_preference: Optional[str] = None


class LLMDiagnosticOutput(BaseModel):
    """Typed JSON contract for GPT-4o-mini diagnostic + regional recovery copy."""

    model_config = ConfigDict(extra="ignore")

    failure_category: Literal[
        "TEMPORARY_OUTAGE",
        "USER_DROPOFF",
        "EXPIRED_CARD",
        "INSUFFICIENT_FUNDS",
        "AUTHENTICATION_FAILED",
    ]
    diagnostic_summary: str = Field(..., min_length=5, max_length=500)
    hinglish_message: str = Field(
        ...,
        min_length=10,
        max_length=1600,
        description="WhatsApp recovery copy: native Indic script + Latin transliteration",
    )
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    contains_payment_link: bool
    used_fallback: bool = False
    language_register: LanguageRegister = LanguageRegister.ENGLISH

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


class RecoveryFunnel(BaseModel):
    failed_ingested: int = 0
    ai_diagnosed: int = 0
    policy_approved: int = 0
    action_executed: int = 0
    payment_verified: int = 0


FAILURE_BREAKDOWN_KEYS = (
    "TEMPORARY_BANK_DEGRADATION",
    "AUTHENTICATION_ISSUE",
    "INSUFFICIENT_FUNDS",
    "EXPIRED_METHOD",
    "CHECKOUT_ABANDONMENT",
)


class DashboardMetrics(BaseModel):
    total_failed_volume: Decimal = Decimal("0.00")
    recovered_revenue: Decimal = Decimal("0.00")
    recovery_rate_percent: float = 0.0
    recovery_rate_percentage: float = 0.0
    outreach_cost: Decimal = Decimal("0.00")
    net_roi: float = 0.0
    total_transactions: int = 0
    recovered_count: int = 0
    flagged_for_approval_count: int = 0
    opted_out_count: int = 0
    max_retries_reached_count: int = 0
    funnel: RecoveryFunnel = Field(default_factory=RecoveryFunnel)
    failed_ingested: int = 0
    ai_diagnosed: int = 0
    policy_approved: int = 0
    action_executed: int = 0
    payment_verified: int = 0
    failure_breakdown: dict[str, int] = Field(default_factory=dict)


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
    customer_state: Optional[str] = None
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
    customer_state: Optional[str] = None
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


class ExecutionGraphNode(BaseModel):
    step_name: str
    step_status: str
    execution_time_ms: Optional[int] = None


class TransactionAuditDetail(BaseModel):
    transaction: TransactionPublic
    audit_logs: list[AuditLogRead]
    execution_graph: list[ExecutionGraphNode]


class WebhookIngestResponse(BaseModel):
    accepted: bool
    transaction_id: str
    recovery_status: str
    requires_human_approval: bool = False
    language_register: Optional[str] = None
    already_processed: bool = False


class ApproveResponse(BaseModel):
    transaction_id: str
    recovery_status: str
    requires_human_approval: bool = False
    language_register: Optional[str] = None
    message: str


class ApproveAllResponse(BaseModel):
    approved: int
    skipped_voice_gate: int = 0
    failed: int = 0
    message: str


class PaidWebhookResponse(BaseModel):
    accepted: bool
    transaction_id: Optional[str] = None
    recovery_status: Optional[str] = None
    already_processed: bool = False
    message: str


class BatchSimulatorResponse(BaseModel):
    count: int
    processed: int
    flagged_for_approval: int
    opted_out: int
    dispatched: int
    recovered: int
    max_retries_reached: int
    states: list[str]
    metrics: DashboardMetrics


OUTREACH_COST_PER_MESSAGE_INR = Decimal("2.10")
