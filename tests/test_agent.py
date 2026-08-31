"""Regional LLM agent: locale routing, schema gate, link preservation, fallback."""

from decimal import Decimal

from backend.agent import (
    build_rich_whatsapp_message,
    classify_failure_code,
    contains_native_script,
    diagnose_failure,
    fallback_diagnostic,
    is_whatsapp_linkifiable,
    message_preserves_payment_link,
    resolve_language_register,
)
from backend.schemas import LLMDiagnosticOutput, LanguageRegister, RecoveryCopyRequest

LINK = "https://rzp.io/l/x8y9z21"


def _request(**overrides) -> RecoveryCopyRequest:
    payload = dict(
        merchant_name="KetoKrafts D2C",
        customer_first_name="Rahul",
        order_amount=Decimal("1499.00"),
        failure_code="BAD_REQUEST_PAYMENT_TIMED_OUT",
        failure_description="Issuer SBI bank gateway did not respond within 30 seconds",
        payment_link=LINK,
        retry_attempt=1,
    )
    payload.update(overrides)
    return RecoveryCopyRequest(**payload)


def test_resolve_language_register_by_state():
    assert resolve_language_register("Karnataka") == LanguageRegister.KANNADA_ENGLISH
    assert resolve_language_register("Tamil Nadu") == LanguageRegister.TANGLISH
    assert resolve_language_register("Telangana") == LanguageRegister.TELUGU_ENGLISH
    assert resolve_language_register("Andhra Pradesh") == LanguageRegister.TELUGU_ENGLISH
    assert resolve_language_register("Maharashtra") == LanguageRegister.MARATHI_HINGLISH
    assert resolve_language_register("Delhi") == LanguageRegister.HINGLISH
    assert resolve_language_register("North") == LanguageRegister.HINGLISH
    assert resolve_language_register(None) == LanguageRegister.ENGLISH


def test_language_preference_forces_simple_english():
    assert (
        resolve_language_register("Karnataka", language_preference="english")
        == LanguageRegister.ENGLISH
    )


def test_fallback_templates_preserve_link_for_every_region():
    states = {
        "Karnataka": LanguageRegister.KANNADA_ENGLISH,
        "Tamil Nadu": LanguageRegister.TANGLISH,
        "Telangana": LanguageRegister.TELUGU_ENGLISH,
        "Maharashtra": LanguageRegister.MARATHI_HINGLISH,
        "Delhi": LanguageRegister.HINGLISH,
        None: LanguageRegister.ENGLISH,
    }
    for state, register in states.items():
        out = fallback_diagnostic(_request(customer_state=state), register=register)
        assert isinstance(out, LLMDiagnosticOutput)
        assert out.used_fallback is True
        assert out.language_register == register
        assert message_preserves_payment_link(out.hinglish_message, LINK)
        assert out.contains_payment_link is True
        assert contains_native_script(out.hinglish_message, register)
        if register != LanguageRegister.ENGLISH:
            assert out.hinglish_message.count(LINK) >= 2
            assert "💡" in out.hinglish_message


def test_diagnose_failure_uses_fallback_when_key_missing_or_test_mode(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-...")
    out = diagnose_failure(_request(customer_state="Maharashtra"))
    assert out.used_fallback is True
    assert out.language_register == LanguageRegister.MARATHI_HINGLISH
    assert LINK in out.hinglish_message
    LLMDiagnosticOutput.model_validate(out.model_dump())


def test_valid_llm_json_is_accepted_and_keeps_link():
    def complete(_system: str, _user: str) -> dict:
        return {
            "failure_category": "TEMPORARY_OUTAGE",
            "diagnostic_summary": "SBI issuer timed out; send a fresh payment link.",
            "hinglish_message": f"Hey Rahul, payment timeout aaytu. Complete: {LINK}",
            "confidence_score": 0.92,
            "contains_payment_link": True,
            "language_register": "kannada_english",
        }

    out = diagnose_failure(_request(customer_state="Karnataka"), complete_fn=complete)
    assert out.used_fallback is False
    assert out.failure_category == "TEMPORARY_OUTAGE"
    assert LINK in out.hinglish_message
    assert out.language_register == LanguageRegister.KANNADA_ENGLISH
    assert contains_native_script(out.hinglish_message, LanguageRegister.KANNADA_ENGLISH)


def test_llm_hallucinated_link_triggers_fallback():
    def complete(_system: str, _user: str) -> dict:
        return {
            "failure_category": "TEMPORARY_OUTAGE",
            "diagnostic_summary": "Timeout classified correctly but link was rewritten.",
            "hinglish_message": "Complete here: https://rzp.io/l/HACKED",
            "confidence_score": 0.99,
            "contains_payment_link": True,
        }

    out = diagnose_failure(_request(customer_state="Delhi"), complete_fn=complete)
    assert out.used_fallback is True
    assert LINK in out.hinglish_message
    assert "HACKED" not in out.hinglish_message


def test_low_confidence_triggers_fallback():
    def complete(_system: str, _user: str) -> dict:
        return {
            "failure_category": "USER_DROPOFF",
            "diagnostic_summary": "Model is unsure about the failure class.",
            "hinglish_message": f"Please pay here {LINK}",
            "confidence_score": 0.40,
            "contains_payment_link": True,
        }

    out = diagnose_failure(_request(), complete_fn=complete)
    assert out.used_fallback is True
    assert LINK in out.hinglish_message


def test_invalid_llm_json_triggers_fallback():
    def complete(_system: str, _user: str) -> dict:
        return {"not": "a valid diagnostic schema"}

    out = diagnose_failure(_request(customer_state="Tamil Nadu"), complete_fn=complete)
    assert out.used_fallback is True
    assert out.language_register == LanguageRegister.TANGLISH
    assert LINK in out.hinglish_message


def test_classify_failure_code_categories():
    assert classify_failure_code("BAD_REQUEST_PAYMENT_TIMED_OUT") == "TEMPORARY_OUTAGE"
    assert classify_failure_code("INSUFFICIENT_FUNDS") == "INSUFFICIENT_FUNDS"
    assert classify_failure_code("CARD_EXPIRED") == "EXPIRED_CARD"
    assert classify_failure_code("AUTHENTICATION_FAILED") == "AUTHENTICATION_FAILED"


def test_localhost_is_not_whatsapp_linkifiable():
    assert is_whatsapp_linkifiable("http://127.0.0.1:8000/api/v1/recovery/pay/x") is False
    assert is_whatsapp_linkifiable("http://localhost:8000/pay") is False
    assert is_whatsapp_linkifiable("https://rzp.io/l/x8y9z21") is True


def test_rich_message_puts_https_link_on_own_line():
    msg = build_rich_whatsapp_message(_request(), LanguageRegister.HINGLISH)
    assert f"\n{LINK}" in msg
    assert "1-Click Payment Link: http://" not in msg


def test_rich_message_is_dual_script_for_every_region():
    regional = {
        LanguageRegister.KANNADA_ENGLISH: "ನಮಸ್ಕಾರ",
        LanguageRegister.TANGLISH: "வணக்கம்",
        LanguageRegister.TELUGU_ENGLISH: "నమస్కారం",
        LanguageRegister.MARATHI_HINGLISH: "नमस्कार",
        LanguageRegister.HINGLISH: "नमस्ते",
    }
    for register, native_hello in regional.items():
        msg = build_rich_whatsapp_message(_request(), register)
        assert native_hello in msg
        assert contains_native_script(msg, register)
        assert msg.count(LINK) == 2
        assert "💡" in msg
        latin_hello = {
            LanguageRegister.KANNADA_ENGLISH: "Namaskara",
            LanguageRegister.TANGLISH: "Vanakkam",
            LanguageRegister.TELUGU_ENGLISH: "Namaskaram",
            LanguageRegister.MARATHI_HINGLISH: "Namaskar",
            LanguageRegister.HINGLISH: "Namaste",
        }[register]
        assert latin_hello in msg
    english = build_rich_whatsapp_message(_request(), LanguageRegister.ENGLISH)
    assert contains_native_script(english, LanguageRegister.ENGLISH)
    assert english.count(LINK) == 1
    assert "Hello" in english
