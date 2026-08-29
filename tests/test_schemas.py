"""Pydantic schema validation smoke tests."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.schemas import (
    FINANCIAL_THRESHOLD_INR,
    MAX_RETRY_COUNT,
    GuardrailEvaluationResult,
    LLMDiagnosticOutput,
    RazorpayFailurePayload,
    RecoveryStatus,
    TransactionPublic,
    mask_email,
    mask_phone,
)


SAMPLE_WEBHOOK = {
    "entity": "event",
    "account_id": "acc_test",
    "event": "payment.failed",
    "contains": ["payment"],
    "payload": {
        "payment": {
            "entity": {
                "id": "pay_test123",
                "entity": "payment",
                "amount": 149900,
                "currency": "INR",
                "status": "failed",
                "email": "rahul@example.com",
                "contact": "+919876543210",
                "error_code": "BAD_REQUEST_ERROR",
                "error_description": "Issuer SBI bank gateway did not respond",
                "error_reason": "payment_timed_out",
                "notes": {"merchant_id": "merch_keto", "customer_name": "Rahul"},
            }
        }
    },
}


def test_razorpay_failure_payload_parses_and_converts_amount():
    payload = RazorpayFailurePayload.model_validate(SAMPLE_WEBHOOK)
    assert payload.event == "payment.failed"
    assert payload.payment.id == "pay_test123"
    assert payload.amount_inr == Decimal("1499.00")
    assert payload.payment.contact == "+919876543210"


def test_llm_diagnostic_output_accepts_valid_json():
    out = LLMDiagnosticOutput(
        failure_category="TEMPORARY_OUTAGE",
        diagnostic_summary="SBI issuer timed out; retry with a fresh payment link.",
        hinglish_message="Hey Rahul, payment timeout ho gaya. Complete here: https://rzp.io/l/abc",
        confidence_score=0.91,
        contains_payment_link=True,
    )
    assert out.used_fallback is False


def test_llm_diagnostic_output_rejects_invalid_category():
    with pytest.raises(ValidationError):
        LLMDiagnosticOutput(
            failure_category="HALLUCINATED_CATEGORY",
            diagnostic_summary="bad",
            hinglish_message="too short",
            confidence_score=1.5,
            contains_payment_link=True,
        )


def test_guardrail_evaluation_result_high_value_flag():
    result = GuardrailEvaluationResult(
        passed=False,
        requires_human_approval=True,
        blocked=False,
        recovery_status=RecoveryStatus.FLAGGED_FOR_APPROVAL,
        reasons=["amount exceeds ₹5,000 threshold"],
        retry_count=0,
        amount=Decimal("7500.00"),
    )
    assert result.requires_human_approval is True
    assert result.amount > FINANCIAL_THRESHOLD_INR
    assert MAX_RETRY_COUNT == 2


def test_pii_masking_helpers():
    assert mask_phone("+919876543210") == "+91 98*****3210"
    assert mask_email("rahul@example.com") == "r***@example.com"


def test_transaction_public_masks_pii():
    public = TransactionPublic(
        id="txn-1",
        merchant_id="merch_keto",
        customer_name="Rahul",
        customer_phone="+919876543210",
        customer_email="rahul@example.com",
        amount=Decimal("1499.00"),
        currency="INR",
        failure_code="BAD_REQUEST_PAYMENT_TIMED_OUT",
        recovery_status="PENDING",
        retry_count=0,
        created_at="2026-08-29T12:00:00Z",
        updated_at="2026-08-29T12:00:00Z",
    )
    assert public.customer_phone == "+91 98*****3210"
    assert public.customer_email == "r***@example.com"
