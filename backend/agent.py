"""LLM diagnostic agent: failure categorization + regional WhatsApp copy.

Uses OpenAI GPT-4o-mini with structured JSON. Every completion is validated
against ``LLMDiagnosticOutput`` and the Razorpay payment link is checked
deterministically. Missing keys, API errors, schema failures, link drift, or
low confidence fall back to pre-written regional templates.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from backend.schemas import (
    MIN_LLM_CONFIDENCE,
    LLMDiagnosticOutput,
    LanguageRegister,
    RecoveryCopyRequest,
)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

OPENAI_MODEL = "gpt-4o-mini"
PLACEHOLDER_KEY_MARKERS = ("sk-proj-...", "your-key", "changeme", "xxx")

# State / city aliases → WhatsApp language register
_STATE_ALIASES: dict[str, LanguageRegister] = {
    "karnataka": LanguageRegister.KANNADA_ENGLISH,
    "ka": LanguageRegister.KANNADA_ENGLISH,
    "bengaluru": LanguageRegister.KANNADA_ENGLISH,
    "bangalore": LanguageRegister.KANNADA_ENGLISH,
    "tamil nadu": LanguageRegister.TANGLISH,
    "tamilnadu": LanguageRegister.TANGLISH,
    "tn": LanguageRegister.TANGLISH,
    "chennai": LanguageRegister.TANGLISH,
    "telangana": LanguageRegister.TELUGU_ENGLISH,
    "ts": LanguageRegister.TELUGU_ENGLISH,
    "hyderabad": LanguageRegister.TELUGU_ENGLISH,
    "andhra pradesh": LanguageRegister.TELUGU_ENGLISH,
    "andhra": LanguageRegister.TELUGU_ENGLISH,
    "ap": LanguageRegister.TELUGU_ENGLISH,
    "maharashtra": LanguageRegister.MARATHI_HINGLISH,
    "mh": LanguageRegister.MARATHI_HINGLISH,
    "mumbai": LanguageRegister.MARATHI_HINGLISH,
    "pune": LanguageRegister.MARATHI_HINGLISH,
    "delhi": LanguageRegister.HINGLISH,
    "new delhi": LanguageRegister.HINGLISH,
    "ncr": LanguageRegister.HINGLISH,
    "north": LanguageRegister.HINGLISH,
    "haryana": LanguageRegister.HINGLISH,
    "punjab": LanguageRegister.HINGLISH,
    "uttar pradesh": LanguageRegister.HINGLISH,
    "up": LanguageRegister.HINGLISH,
    "rajasthan": LanguageRegister.HINGLISH,
}

_LOCALE_STYLE: dict[LanguageRegister, str] = {
    LanguageRegister.KANNADA_ENGLISH: (
        "Conversational Kannada-English mix in Latin script "
        "(e.g. 'Nimma payment timeout aaytu, complete maadi')."
    ),
    LanguageRegister.TANGLISH: (
        "Tanglish / Tamil-English mix in Latin script "
        "(e.g. 'Unoda payment timeout aagiduchu, complete pannunga')."
    ),
    LanguageRegister.TELUGU_ENGLISH: (
        "Telugu-English mix in Latin script "
        "(e.g. 'Mee payment timeout ayyindi, complete cheyyandi')."
    ),
    LanguageRegister.MARATHI_HINGLISH: (
        "Marathi-Hinglish mix in Latin script "
        "(e.g. 'Tumcha payment timeout zala, complete kara')."
    ),
    LanguageRegister.HINGLISH: (
        "North-Indian Hinglish "
        "(e.g. 'Aapka payment timeout ho gaya, yahan complete karein')."
    ),
    LanguageRegister.ENGLISH: "Simple, polite Indian English. No slang.",
}

# Deterministic templates: {name} {amount} {merchant} {link}
_FALLBACK_TEMPLATES: dict[LanguageRegister, str] = {
    LanguageRegister.KANNADA_ENGLISH: (
        "Hey {name}! Nimma ₹{amount} payment timeout aaytu {merchant} ge. "
        "Order complete maadi: {link}"
    ),
    LanguageRegister.TANGLISH: (
        "Hey {name}! Unoda ₹{amount} payment timeout aagiduchu {merchant} ku. "
        "Order complete pannunga: {link}"
    ),
    LanguageRegister.TELUGU_ENGLISH: (
        "Hey {name}! Mee ₹{amount} payment timeout ayyindi {merchant} ki. "
        "Order complete cheyyandi: {link}"
    ),
    LanguageRegister.MARATHI_HINGLISH: (
        "Hey {name}! Tumcha ₹{amount} payment timeout zala {merchant} sathi. "
        "Order complete kara: {link}"
    ),
    LanguageRegister.HINGLISH: (
        "Hey {name}! Aapka ₹{amount} payment timeout ho gaya {merchant} ke liye. "
        "Order yahan complete karein: {link}"
    ),
    LanguageRegister.ENGLISH: (
        "Hey {name}! Your payment of ₹{amount} for {merchant} timed out. "
        "Complete your order here: {link}"
    ),
}

_INJECTION_PATTERNS = (
    "ignore previous",
    "ignore all instructions",
    "system prompt",
    "you are now",
    "forget your instructions",
)

CompleteFn = Callable[[str, str], dict[str, Any]]


def _is_placeholder_key(api_key: str | None) -> bool:
    if not api_key or not api_key.strip():
        return True
    lowered = api_key.strip().lower()
    return any(marker in lowered for marker in PLACEHOLDER_KEY_MARKERS)


def _test_mode_enabled() -> bool:
    return os.getenv("TEST_MODE", "false").strip().lower() in {"1", "true", "yes"}


def sanitize_text(value: str, *, max_len: int = 80, fallback: str = "Customer") -> str:
    """Strip control chars and block obvious prompt-injection names."""
    cleaned = " ".join(value.replace("\n", " ").replace("\r", " ").split())
    if any(token in cleaned.lower() for token in _INJECTION_PATTERNS):
        return fallback
    return cleaned[:max_len] or fallback


def resolve_language_register(
    customer_state: str | None,
    language_preference: str | None = None,
) -> LanguageRegister:
    """Map state / explicit preference to a WhatsApp language register."""
    pref = (language_preference or "").strip().lower()
    if pref in {"english", "en", "simple english", "default"}:
        return LanguageRegister.ENGLISH
    if pref in {item.value for item in LanguageRegister}:
        return LanguageRegister(pref)

    key = re.sub(r"[^a-z]+", " ", (customer_state or "").strip().lower()).strip()
    if key in _STATE_ALIASES:
        return _STATE_ALIASES[key]
    return LanguageRegister.ENGLISH


def classify_failure_code(failure_code: str, description: str | None = None) -> str:
    blob = f"{failure_code} {description or ''}".upper()
    if any(token in blob for token in ("INSUFFICIENT", "LOW_BALANCE", "FUNDS")):
        return "INSUFFICIENT_FUNDS"
    if any(token in blob for token in ("EXPIRED", "CARD_EXPIRED")):
        return "EXPIRED_CARD"
    if any(token in blob for token in ("AUTH", "3DS", "OTP", "PIN")):
        return "AUTHENTICATION_FAILED"
    if any(token in blob for token in ("TIMEOUT", "TIMED_OUT", "ISSUER_DOWN", "GATEWAY")):
        return "TEMPORARY_OUTAGE"
    return "USER_DROPOFF"


def message_preserves_payment_link(message: str, payment_link: str) -> bool:
    """Require the exact, unaltered Razorpay link in the generated copy."""
    return bool(payment_link) and payment_link in message


def render_fallback_message(
    request: RecoveryCopyRequest,
    register: LanguageRegister,
) -> str:
    name = sanitize_text(request.customer_first_name, fallback="there")
    merchant = sanitize_text(request.merchant_name, max_len=60, fallback="the merchant")
    amount = Decimal(request.order_amount).quantize(Decimal("0.01"))
    template = _FALLBACK_TEMPLATES[register]
    return template.format(
        name=name,
        amount=amount,
        merchant=merchant,
        link=request.payment_link,
    )


def fallback_diagnostic(
    request: RecoveryCopyRequest,
    *,
    reason: str = "LLM unavailable; using regional template",
    register: LanguageRegister | None = None,
) -> LLMDiagnosticOutput:
    locale = register or resolve_language_register(
        request.customer_state, request.language_preference
    )
    message = render_fallback_message(request, locale)
    category = classify_failure_code(request.failure_code, request.failure_description)
    return LLMDiagnosticOutput(
        failure_category=category,  # type: ignore[arg-type]
        diagnostic_summary=reason[:500],
        hinglish_message=message,
        confidence_score=1.0,
        contains_payment_link=True,
        used_fallback=True,
        language_register=locale,
    )


def _build_messages(request: RecoveryCopyRequest, register: LanguageRegister) -> tuple[str, str]:
    name = sanitize_text(request.customer_first_name, fallback="there")
    merchant = sanitize_text(request.merchant_name, max_len=60, fallback="the merchant")
    style = _LOCALE_STYLE[register]
    system = (
        "You are RecoverPay AI, a payment recovery assistant for an Indian merchant. "
        "Diagnose the failure and write one short WhatsApp recovery message. "
        "Reply with a single JSON object only. Never invent discounts, refunds, or new URLs. "
        "Copy the payment_link character-for-character into hinglish_message."
    )
    user_payload = {
        "language_register": register.value,
        "style_guide": style,
        "input_context": {
            "merchant_name": merchant,
            "customer_first_name": name,
            "order_amount": float(request.order_amount),
            "currency": request.currency,
            "failure_code": request.failure_code,
            "failure_description": request.failure_description,
            "payment_link": request.payment_link,
            "retry_attempt": request.retry_attempt,
            "customer_state": request.customer_state,
        },
        "output_schema": {
            "failure_category": (
                "TEMPORARY_OUTAGE | USER_DROPOFF | EXPIRED_CARD | "
                "INSUFFICIENT_FUNDS | AUTHENTICATION_FAILED"
            ),
            "diagnostic_summary": "string, 5-500 chars",
            "hinglish_message": "string, 10-300 chars, must include payment_link exactly",
            "confidence_score": "float 0.0-1.0",
            "contains_payment_link": "boolean true",
            "language_register": register.value,
            "used_fallback": False,
        },
    }
    return system, json.dumps(user_payload, ensure_ascii=False)


def _call_openai(system: str, user: str, api_key: str) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.3,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = completion.choices[0].message.content or ""
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("LLM JSON was not an object")
    return parsed


def _accept_or_fallback(
    request: RecoveryCopyRequest,
    register: LanguageRegister,
    raw: dict[str, Any],
) -> LLMDiagnosticOutput:
    raw.setdefault("language_register", register.value)
    raw["used_fallback"] = False
    output = LLMDiagnosticOutput.model_validate(raw)
    if output.confidence_score < MIN_LLM_CONFIDENCE:
        return fallback_diagnostic(
            request,
            reason="LLM confidence below 0.75; using regional template",
            register=register,
        )
    if not message_preserves_payment_link(output.hinglish_message, request.payment_link):
        return fallback_diagnostic(
            request,
            reason="LLM altered or dropped the Razorpay payment link; using template",
            register=register,
        )
    return output.model_copy(update={"contains_payment_link": True, "language_register": register})


def diagnose_failure(
    request: RecoveryCopyRequest,
    *,
    complete_fn: CompleteFn | None = None,
) -> LLMDiagnosticOutput:
    """Diagnose a payment failure and return schema-valid regional copy.

    ``complete_fn(system, user) -> dict`` is an injectable LLM for tests.
    Production calls GPT-4o-mini unless ``TEST_MODE`` is on or the API key
    is missing / a placeholder.
    """
    register = resolve_language_register(request.customer_state, request.language_preference)
    api_key = os.getenv("OPENAI_API_KEY")

    if complete_fn is None and (_test_mode_enabled() or _is_placeholder_key(api_key)):
        reason = (
            "TEST_MODE enabled; using regional template"
            if _test_mode_enabled()
            else "OPENAI_API_KEY missing or placeholder; using regional template"
        )
        return fallback_diagnostic(request, reason=reason, register=register)

    system, user = _build_messages(request, register)
    try:
        raw = complete_fn(system, user) if complete_fn is not None else _call_openai(
            system, user, api_key or ""
        )
        return _accept_or_fallback(request, register, raw)
    except Exception as exc:
        return fallback_diagnostic(
            request,
            reason=f"LLM_FALLBACK_TRIGGERED: {type(exc).__name__}: {exc}"[:500],
            register=register,
        )


_TWILIO_PLACEHOLDER_MARKERS = ("ACxxxxxxxx", "your_twilio", "changeme", "xxx")


def _is_placeholder_twilio(value: str | None) -> bool:
    if not value or not value.strip():
        return True
    lowered = value.strip().lower()
    return any(m in lowered for m in _TWILIO_PLACEHOLDER_MARKERS)


def send_whapi_whatsapp(phone: str, message_text: str) -> bool:
    """Send a free-form WhatsApp message via Whapi Cloud.

    Environment variables required:
        WHAPI_TOKEN – Bearer token from gate.whapi.cloud
        WHAPI_URL   – Base URL (default: https://gate.whapi.cloud/)
    """
    import sys

    token = os.getenv("WHAPI_TOKEN", "").strip()
    base_url = os.getenv("WHAPI_URL", "https://gate.whapi.cloud/").rstrip("/")
    if not token or token in ("your_whapi_token", "changeme"):
        print("[Whapi] WHAPI_TOKEN not configured; skipping.", file=sys.stderr)
        return False

    # Normalise: strip whatsapp: prefix and +, keep digits only with country code
    clean_phone = phone.replace("whatsapp:", "").lstrip("+")
    try:
        import requests as _requests  # type: ignore[import-untyped]

        resp = _requests.post(
            f"{base_url}/messages/text",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"},
            json={"to": clean_phone, "body": message_text},
            timeout=5,
        )
        data = resp.json() if resp.content else {}
        if resp.status_code == 200 and data.get("sent"):
            msg_id = data.get("message", {}).get("id", "?")
            print(f"[Whapi] Sent → id={msg_id} to={clean_phone}", file=sys.stderr)
            return True
        if resp.status_code == 402:
            print("[Whapi] Trial message limit reached — upgrade at whapi.cloud to send more.", file=sys.stderr)
            return False
        print(f"[Whapi] Send failed: HTTP {resp.status_code} {resp.text[:120]}", file=sys.stderr)
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"[Whapi] Exception: {type(exc).__name__}: {exc}", file=sys.stderr)
        return False


def send_callmebot_whatsapp(phone: str, message_text: str) -> bool:
    """Send a free-form WhatsApp message via CallMeBot (free, no templates needed).

    One-time setup: WhatsApp "I allow callmebot to send me messages" to +34 644 50 47 20.
    You'll receive a CALLMEBOT_API_KEY in reply.

    Environment variables required:
        CALLMEBOT_API_KEY  – numeric key received from CallMeBot setup
        MY_PERSONAL_WHATSAPP – phone number in E.164 format e.g. +919148001667
    """
    import sys
    import urllib.parse
    import urllib.request

    api_key = os.getenv("CALLMEBOT_API_KEY", "").strip()
    if not api_key or api_key in ("your_callmebot_key", "changeme"):
        print("[CallMeBot] CALLMEBOT_API_KEY not configured; skipping.", file=sys.stderr)
        return False

    # Strip whatsapp: prefix and leading +
    clean_phone = phone.replace("whatsapp:", "").lstrip("+")
    encoded_msg = urllib.parse.quote(message_text)
    url = f"https://api.callmebot.com/whatsapp.php?phone={clean_phone}&text={encoded_msg}&apikey={api_key}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(f"[CallMeBot] Sent to {clean_phone} → {body[:80]}", file=sys.stderr)
            return True
    except Exception as exc:  # noqa: BLE001
        print(f"[CallMeBot] Send failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return False


def send_live_whatsapp_message(to_phone: str, message_text: str) -> bool:
    """Send ``message_text`` via CallMeBot (preferred, free-form) with Twilio as fallback.

    CallMeBot is tried first when CALLMEBOT_API_KEY is set — it supports any text
    without ContentSid restrictions. Falls back to Twilio ContentSid template if
    CallMeBot is not configured.

    Returns ``True`` on success, ``False`` otherwise. Never raises.
    """
    import sys

    if _test_mode_enabled():
        print(f"[WhatsApp] TEST_MODE=true → skipping live send to {to_phone}", file=sys.stderr)
        return False

    # ── Whapi Cloud (best: free-form, no templates) ───────────────────────
    whapi_token = os.getenv("WHAPI_TOKEN", "").strip()
    if whapi_token and whapi_token not in ("your_whapi_token", "changeme"):
        return send_whapi_whatsapp(to_phone, message_text)

    # ── CallMeBot (free-form, no template required) ───────────────────────
    callmebot_key = os.getenv("CALLMEBOT_API_KEY", "").strip()
    if callmebot_key and callmebot_key not in ("your_callmebot_key", "changeme"):
        return send_callmebot_whatsapp(to_phone, message_text)

    # ── Twilio fallback ───────────────────────────────────────────────────
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+17372212163")

    if _is_placeholder_twilio(account_sid) or _is_placeholder_twilio(auth_token):
        print("[Twilio] Credentials not configured; skipping send.", file=sys.stderr)
        return False

    destination = to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:{to_phone}"
    content_sid = os.getenv("TWILIO_CONTENT_SID", "").strip()

    try:
        import json as _json
        from twilio.rest import Client as TwilioClient  # type: ignore[import-untyped]

        client = TwilioClient(account_sid, auth_token)
        if content_sid:
            msg = client.messages.create(
                from_=from_number,
                to=destination,
                content_sid=content_sid,
                content_variables=_json.dumps({"1": message_text[:1600]}),
            )
        else:
            msg = client.messages.create(body=message_text, from_=from_number, to=destination)
        print(f"[Twilio] Message sent → SID={msg.sid} status={msg.status}", file=sys.stderr)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[Twilio] Send failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return False


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    demo = RecoveryCopyRequest(
        merchant_name="KetoKrafts D2C",
        customer_first_name="Rahul",
        order_amount=Decimal("1499.00"),
        failure_code="BAD_REQUEST_PAYMENT_TIMED_OUT",
        failure_description="Issuer SBI bank gateway did not respond within 30 seconds",
        payment_link="https://rzp.io/l/x8y9z21",
        customer_state="Karnataka",
    )
    result = diagnose_failure(demo)
    print(result.model_dump_json(indent=2))
    print("link_ok", message_preserves_payment_link(result.hinglish_message, demo.payment_link))
