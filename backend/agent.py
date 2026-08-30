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

import ipaddress
from urllib.parse import urlparse

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

# ── Dialect-aware greeting and possessive ─────────────────────────────────────
_GREETINGS: dict[LanguageRegister, str] = {
    LanguageRegister.KANNADA_ENGLISH: "Namaskara",
    LanguageRegister.TANGLISH: "Vanakkam",
    LanguageRegister.TELUGU_ENGLISH: "Namaskaram",
    LanguageRegister.MARATHI_HINGLISH: "Namaskar",
    LanguageRegister.HINGLISH: "Namaste",
    LanguageRegister.ENGLISH: "Hello",
}

_POSSESSIVES: dict[LanguageRegister, str] = {
    LanguageRegister.KANNADA_ENGLISH: "Nimma",
    LanguageRegister.TANGLISH: "Ungoda",
    LanguageRegister.TELUGU_ENGLISH: "Meeru",
    LanguageRegister.MARATHI_HINGLISH: "Tumcha",
    LanguageRegister.HINGLISH: "Aapka",
    LanguageRegister.ENGLISH: "Your",
}

# ── Plain human-readable failure cause per category × dialect ─────────────────
_CAUSE_PHRASES: dict[str, dict[LanguageRegister, str]] = {
    "TEMPORARY_OUTAGE": {
        LanguageRegister.KANNADA_ENGLISH: "bank server timeout karanadinda agilla",
        LanguageRegister.TANGLISH: "bank server timeout aagidhuchu",
        LanguageRegister.TELUGU_ENGLISH: "bank server timeout valla fail ayyindi",
        LanguageRegister.MARATHI_HINGLISH: "bank server timeout mule fail zala",
        LanguageRegister.HINGLISH: "bank server timeout ki wajah se fail ho gaya",
        LanguageRegister.ENGLISH: "failed due to a bank server timeout",
    },
    "INSUFFICIENT_FUNDS": {
        LanguageRegister.KANNADA_ENGLISH: "account balance saala illa anta fail aaytu",
        LanguageRegister.TANGLISH: "account balance podumaiyilla aagiduchu",
        LanguageRegister.TELUGU_ENGLISH: "account balance chaalaledu antu fail ayyindi",
        LanguageRegister.MARATHI_HINGLISH: "account balance kami asel mule fail zala",
        LanguageRegister.HINGLISH: "account mein balance kam hone se fail ho gaya",
        LanguageRegister.ENGLISH: "failed due to insufficient account balance",
    },
    "EXPIRED_CARD": {
        LanguageRegister.KANNADA_ENGLISH: "card expire aagide anta fail aaytu",
        LanguageRegister.TANGLISH: "card expire aagidhuchu",
        LanguageRegister.TELUGU_ENGLISH: "card expire ayyindi",
        LanguageRegister.MARATHI_HINGLISH: "card expire zala",
        LanguageRegister.HINGLISH: "card expire ho gayi hai",
        LanguageRegister.ENGLISH: "failed because your card has expired",
    },
    "AUTHENTICATION_FAILED": {
        LanguageRegister.KANNADA_ENGLISH: "OTP/UPI PIN authenticate agilla anta fail aaytu",
        LanguageRegister.TANGLISH: "OTP/UPI PIN authentication fail aagidhuchu",
        LanguageRegister.TELUGU_ENGLISH: "OTP/UPI PIN authentication fail ayyindi",
        LanguageRegister.MARATHI_HINGLISH: "OTP/UPI PIN authentication fail zala",
        LanguageRegister.HINGLISH: "OTP/UPI PIN authentication fail ho gaya",
        LanguageRegister.ENGLISH: "failed at OTP / UPI PIN authentication",
    },
    "USER_DROPOFF": {
        LanguageRegister.KANNADA_ENGLISH: "complete agalilla",
        LanguageRegister.TANGLISH: "complete pandavillai",
        LanguageRegister.TELUGU_ENGLISH: "complete kaaledu",
        LanguageRegister.MARATHI_HINGLISH: "complete zale nahi",
        LanguageRegister.HINGLISH: "complete nahi hua",
        LanguageRegister.ENGLISH: "was not completed",
    },
}

# ── Actionable fix tips per failure category (English, understood universally) ─
_ACTION_TIPS: dict[str, str] = {
    "TEMPORARY_OUTAGE": (
        "Select GPay or PhonePe UPI directly at checkout for instant authorization."
    ),
    "INSUFFICIENT_FUNDS": (
        "Add the required amount to your account and tap the link to retry."
    ),
    "EXPIRED_CARD": (
        "Update your card details in your banking app, then tap the payment link."
    ),
    "AUTHENTICATION_FAILED": (
        "Keep your UPI PIN or OTP ready before tapping the payment link."
    ),
    "USER_DROPOFF": (
        "Your order is saved — complete your payment before the link expires!"
    ),
}

# ── Deterministic templates: {name} {amount} {merchant} {link} ────────────────
# (kept as legacy fallback; build_rich_whatsapp_message is preferred)
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


_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def is_whatsapp_linkifiable(url: str) -> bool:
    """WhatsApp only auto-linkifies public http(s) hosts — never localhost or LAN IPs."""
    if not url or not str(url).strip():
        return False
    parsed = urlparse(str(url).strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        return False
    if host in _LOCAL_HOSTS or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    except ValueError:
        pass
    return True


def first_public_http_url(text: str) -> str | None:
    for match in re.findall(r"https?://[^\s<>\"']+", text or ""):
        cleaned = match.rstrip(").,;]")
        if is_whatsapp_linkifiable(cleaned):
            return cleaned
    return None


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


def build_rich_whatsapp_message(
    request: RecoveryCopyRequest,
    register: LanguageRegister,
    *,
    bank_outage_note: str | None = None,
) -> str:
    """Build the structured 3-line WhatsApp message sent via Green API.

    Format::

        {Greeting} {name}! {Poss} {merchant} order (₹{amount}) payment {cause}.
        💡 Tip: {actionable tip}
        🔗 Tap the 1-click payment link below:
        {link}
        ℹ️ Note: {bank outage note}   ← only if bank is degraded

    All four elements — regional greeting, plain failure cause, actionable tip,
    and Razorpay payment link — are always present regardless of failure type.
    """
    name = sanitize_text(request.customer_first_name, fallback="there")
    merchant = sanitize_text(request.merchant_name, max_len=60, fallback="the merchant")
    amount = Decimal(request.order_amount).quantize(Decimal("0.01"))

    failure_cat = classify_failure_code(request.failure_code, request.failure_description)

    greeting = _GREETINGS.get(register, "Hello")
    possessive = _POSSESSIVES.get(register, "Your")
    cause_map = _CAUSE_PHRASES.get(failure_cat, _CAUSE_PHRASES["USER_DROPOFF"])
    cause = cause_map.get(register, cause_map[LanguageRegister.ENGLISH])
    tip = _ACTION_TIPS.get(failure_cat, _ACTION_TIPS["USER_DROPOFF"])

    message = (
        f"{greeting} {name}! {possessive} {merchant} order (₹{amount}) payment {cause}.\n"
        f"💡 Tip: {tip}\n"
        f"🔗 Tap the 1-click payment link below:\n"
        f"{request.payment_link}"
    )
    if bank_outage_note:
        message += f"\nℹ️ Note: {bank_outage_note}"
    return message


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


def send_green_api_message(
    to_phone: str,
    message_text: str,
    *,
    link_url: str | None = None,
) -> bool:
    """Send a WhatsApp message via Green API (https://green-api.com).

    Prefers an interactive URL button so the customer gets a tappable Pay now
    control. Falls back to sendMessage with linkPreview so public https URLs
    render as blue hyperlinks (localhost URLs never will).
    """
    import sys

    if _test_mode_enabled():
        print("[GreenAPI] TEST_MODE=true → skipping live send.", file=sys.stderr)
        return False

    instance_id = os.getenv("GREEN_API_INSTANCE_ID", "").strip()
    token = os.getenv("GREEN_API_TOKEN", "").strip()
    if not instance_id or not token:
        print("[GreenAPI] GREEN_API_INSTANCE_ID / GREEN_API_TOKEN not set; skipping.", file=sys.stderr)
        return False

    # Normalise phone: strip whatsapp:/+/spaces, keep digits only
    clean = re.sub(r"\D", "", to_phone.replace("whatsapp:", ""))
    if not clean:
        print("[GreenAPI] Empty phone number; skipping.", file=sys.stderr)
        return False

    chat_id = f"{clean}@c.us"
    clickable = (link_url or "").strip() or first_public_http_url(message_text)
    if clickable and not is_whatsapp_linkifiable(clickable):
        clickable = None
    base = f"https://api.green-api.com/waInstance{instance_id}"

    try:
        import requests as _requests  # type: ignore[import-untyped]

        if clickable:
            button_resp = _requests.post(
                f"{base}/sendInteractiveButtons/{token}",
                json={
                    "chatId": chat_id,
                    "header": "RecoverPay AI",
                    "body": message_text,
                    "footer": "Secure 1-click UPI",
                    "buttons": [
                        {
                            "type": "url",
                            "buttonId": "1",
                            "buttonText": "Pay now",
                            "url": clickable,
                        }
                    ],
                },
                timeout=10,
            )
            if button_resp.status_code == 200:
                data = button_resp.json()
                print(
                    f"[GreenAPI] URL button sent → idMessage={data.get('idMessage', '?')} to={chat_id}",
                    file=sys.stderr,
                )
                return True
            print(
                f"[GreenAPI] URL button unavailable ({button_resp.status_code}); falling back to text link.",
                file=sys.stderr,
            )

        # Do not enable linkPreview: WhatsApp/Green API crawlers would GET the
        # recover URL and mark RECOVERED before the customer taps.
        payload: dict[str, Any] = {
            "chatId": chat_id,
            "message": message_text,
            "linkPreview": False,
        }
        resp = _requests.post(
            f"{base}/sendMessage/{token}",
            json=payload,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"[GreenAPI] Sent → idMessage={data.get('idMessage','?')} to={chat_id}", file=sys.stderr)
            return True
        print(f"[GreenAPI] Send failed: HTTP {resp.status_code} {resp.text[:120]}", file=sys.stderr)
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"[GreenAPI] Exception: {type(exc).__name__}: {exc}", file=sys.stderr)
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
