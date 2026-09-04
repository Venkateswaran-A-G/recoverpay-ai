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
import backend.env  # noqa: F401 — process env + .env.example placeholders only

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
        "DUAL SCRIPT. Block 1: Kannada native script (ಕನ್ನಡ). "
        "Block 2: Kanglish / Kannada-English in Latin script. "
        "Both blocks must include the same plain failure cause, a 💡 tip, "
        "and the exact payment_link on its own line."
    ),
    LanguageRegister.TANGLISH: (
        "DUAL SCRIPT. Block 1: Tamil native script (தமிழ்). "
        "Block 2: Tanglish in Latin script. "
        "Both blocks must include the same plain failure cause, a 💡 tip, "
        "and the exact payment_link on its own line."
    ),
    LanguageRegister.TELUGU_ENGLISH: (
        "DUAL SCRIPT. Block 1: Telugu native script (తెలుగు). "
        "Block 2: Telugu-English in Latin script. "
        "Both blocks must include the same plain failure cause, a 💡 tip, "
        "and the exact payment_link on its own line."
    ),
    LanguageRegister.MARATHI_HINGLISH: (
        "DUAL SCRIPT. Block 1: Marathi native script (मराठी). "
        "Block 2: Marathi-Hinglish in Latin script. "
        "Both blocks must include the same plain failure cause, a 💡 tip, "
        "and the exact payment_link on its own line."
    ),
    LanguageRegister.HINGLISH: (
        "DUAL SCRIPT. Block 1: Hindi native script (हिंदी). "
        "Block 2: Hinglish in Latin script. "
        "Both blocks must include the same plain failure cause, a 💡 tip, "
        "and the exact payment_link on its own line."
    ),
    LanguageRegister.ENGLISH: "Simple, polite Indian English only. No slang. No second script.",
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

_NATIVE_GREETINGS: dict[LanguageRegister, str] = {
    LanguageRegister.KANNADA_ENGLISH: "ನಮಸ್ಕಾರ",
    LanguageRegister.TANGLISH: "வணக்கம்",
    LanguageRegister.TELUGU_ENGLISH: "నమస్కారం",
    LanguageRegister.MARATHI_HINGLISH: "नमस्कार",
    LanguageRegister.HINGLISH: "नमस्ते",
}

_NATIVE_POSSESSIVES: dict[LanguageRegister, str] = {
    LanguageRegister.KANNADA_ENGLISH: "ನಿಮ್ಮ",
    LanguageRegister.TANGLISH: "உங்கள்",
    LanguageRegister.TELUGU_ENGLISH: "మీ",
    LanguageRegister.MARATHI_HINGLISH: "तुमचा",
    LanguageRegister.HINGLISH: "आपका",
}

_NATIVE_ORDER_WORD: dict[LanguageRegister, str] = {
    LanguageRegister.KANNADA_ENGLISH: "ಆರ್ಡರ್",
    LanguageRegister.TANGLISH: "ஆர்டர்",
    LanguageRegister.TELUGU_ENGLISH: "ఆర్డర్",
    LanguageRegister.MARATHI_HINGLISH: "ऑर्डर",
    LanguageRegister.HINGLISH: "ऑर्डर",
}

_NATIVE_PAYMENT_WORD: dict[LanguageRegister, str] = {
    LanguageRegister.KANNADA_ENGLISH: "ಪಾವತಿ",
    LanguageRegister.TANGLISH: "பேமெண்ட்",
    LanguageRegister.TELUGU_ENGLISH: "చెల్లింపు",
    LanguageRegister.MARATHI_HINGLISH: "पेमेंट",
    LanguageRegister.HINGLISH: "पेमेंट",
}

_NATIVE_TIP_LABEL: dict[LanguageRegister, str] = {
    LanguageRegister.KANNADA_ENGLISH: "ಸಲಹೆ",
    LanguageRegister.TANGLISH: "குறிப்பு",
    LanguageRegister.TELUGU_ENGLISH: "సూచన",
    LanguageRegister.MARATHI_HINGLISH: "टीप",
    LanguageRegister.HINGLISH: "सुझाव",
}

_NATIVE_LINK_LABEL: dict[LanguageRegister, str] = {
    LanguageRegister.KANNADA_ENGLISH: "1-ಕ್ಲಿಕ್ ಪಾವತಿ ಲಿಂಕ್ ಕೆಳಗೆ:",
    LanguageRegister.TANGLISH: "1-கிளிக் கட்டண இணைப்பு கீழே:",
    LanguageRegister.TELUGU_ENGLISH: "1-క్లిక్ చెల్లింపు లింక్ కింద:",
    LanguageRegister.MARATHI_HINGLISH: "१-क्लिक पेमेंट लिंक खाली:",
    LanguageRegister.HINGLISH: "1-क्लिक पेमेंट लिंक नीचे:",
}

_SCRIPT_RANGES: dict[LanguageRegister, tuple[int, int]] = {
    LanguageRegister.KANNADA_ENGLISH: (0x0C80, 0x0CFF),
    LanguageRegister.TANGLISH: (0x0B80, 0x0BFF),
    LanguageRegister.TELUGU_ENGLISH: (0x0C00, 0x0C7F),
    LanguageRegister.MARATHI_HINGLISH: (0x0900, 0x097F),
    LanguageRegister.HINGLISH: (0x0900, 0x097F),
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

_NATIVE_CAUSE_PHRASES: dict[str, dict[LanguageRegister, str]] = {
    "TEMPORARY_OUTAGE": {
        LanguageRegister.KANNADA_ENGLISH: "ಬ್ಯಾಂಕ್ ಸರ್ವರ್ ಟೈಮ್‌ಔಟ್‌ನಿಂದ ವಿಫಲವಾಗಿದೆ",
        LanguageRegister.TANGLISH: "வங்கி சர்வர் நேரம் முடிந்ததால் தோல்வியடைந்தது",
        LanguageRegister.TELUGU_ENGLISH: "బ్యాంక్ సర్వర్ టైమ్‌అవుట్ వల్ల విఫలమైంది",
        LanguageRegister.MARATHI_HINGLISH: "बँक सर्व्हर टाइमआउटमुळे अयशस्वी झाले",
        LanguageRegister.HINGLISH: "बैंक सर्वर टाइमआउट की वजह से फेल हो गया",
    },
    "INSUFFICIENT_FUNDS": {
        LanguageRegister.KANNADA_ENGLISH: "ಖಾತೆಯಲ್ಲಿ ಬ್ಯಾಲೆನ್ಸ್ ಸಾಲದೆ ವಿಫಲವಾಗಿದೆ",
        LanguageRegister.TANGLISH: "கணக்கில் இருப்பு போதாததால் தோல்வியடைந்தது",
        LanguageRegister.TELUGU_ENGLISH: "ఖాతాలో బ్యాలెన్స్ చాలకపోవడంతో విఫలమైంది",
        LanguageRegister.MARATHI_HINGLISH: "खात्यात शिल्लक अपुरी असल्याने अयशस्वी झाले",
        LanguageRegister.HINGLISH: "खाते में बैलेंस कम होने से फेल हो गया",
    },
    "EXPIRED_CARD": {
        LanguageRegister.KANNADA_ENGLISH: "ಕಾರ್ಡ್ ಅವಧಿ ಮುಗಿದಿರುವುದರಿಂದ ವಿಫಲವಾಗಿದೆ",
        LanguageRegister.TANGLISH: "அட்டை காலாவதியானதால் தோல்வியடைந்தது",
        LanguageRegister.TELUGU_ENGLISH: "కార్డ్ గడువు ముగిసినందున విఫలమైంది",
        LanguageRegister.MARATHI_HINGLISH: "कार्ड मुदत संपल्याने अयशस्वी झाले",
        LanguageRegister.HINGLISH: "कार्ड की अवधि खत्म होने से फेल हो गया",
    },
    "AUTHENTICATION_FAILED": {
        LanguageRegister.KANNADA_ENGLISH: "OTP/UPI PIN ದೃಢೀಕರಣ ವಿಫಲವಾಗಿದೆ",
        LanguageRegister.TANGLISH: "OTP/UPI PIN சரிபார்ப்பு தோல்வியடைந்தது",
        LanguageRegister.TELUGU_ENGLISH: "OTP/UPI PIN ధృవీకరణ విఫలమైంది",
        LanguageRegister.MARATHI_HINGLISH: "OTP/UPI PIN पडताळणी अयशस्वी झाली",
        LanguageRegister.HINGLISH: "OTP/UPI PIN प्रमाणीकरण फेल हो गया",
    },
    "USER_DROPOFF": {
        LanguageRegister.KANNADA_ENGLISH: "ಪೂರ್ಣಗೊಂಡಿಲ್ಲ",
        LanguageRegister.TANGLISH: "முடிக்கப்படவில்லை",
        LanguageRegister.TELUGU_ENGLISH: "పూర్తి కాలేదు",
        LanguageRegister.MARATHI_HINGLISH: "पूर्ण झाले नाही",
        LanguageRegister.HINGLISH: "पूरा नहीं हुआ",
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

_NATIVE_ACTION_TIPS: dict[str, dict[LanguageRegister, str]] = {
    "TEMPORARY_OUTAGE": {
        LanguageRegister.KANNADA_ENGLISH: "ಚೆಕ್‌ಔಟ್‌ನಲ್ಲಿ ನೇರವಾಗಿ GPay ಅಥವಾ PhonePe UPI ಆಯ್ಕೆಮಾಡಿ — ತಕ್ಷಣ ಅಧಿಕಾರ.",
        LanguageRegister.TANGLISH: "செக்அவுட்டில் நேரடியாக GPay அல்லது PhonePe UPI தேர்ந்தெடுங்கள் — உடனடி அனுமதி.",
        LanguageRegister.TELUGU_ENGLISH: "చెక్‌అవుట్‌లో నేరుగా GPay లేదా PhonePe UPI ఎంచుకోండి — తక్షణ అధికారం.",
        LanguageRegister.MARATHI_HINGLISH: "चेकआउटवर थेट GPay किंवा PhonePe UPI निवडा — त्वरित अधिकृतता.",
        LanguageRegister.HINGLISH: "चेकआउट पर सीधे GPay या PhonePe UPI चुनें — तुरंत अनुमति।",
    },
    "INSUFFICIENT_FUNDS": {
        LanguageRegister.KANNADA_ENGLISH: "ಖಾತೆಗೆ ಅಗತ್ಯ ಮೊತ್ತ ಸೇರಿಸಿ, ನಂತರ ಲಿಂಕ್ ಟ್ಯಾಪ್ ಮಾಡಿ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
        LanguageRegister.TANGLISH: "கணக்கில் தேவையான தொகையைச் சேர்த்து, இணைப்பைத் தட்டி மீண்டும் முயற்சிக்கவும்.",
        LanguageRegister.TELUGU_ENGLISH: "ఖాతాకు అవసరమైన మొత్తం జోడించి, లింక్ ట్యాప్ చేసి మళ్లీ ప్రయత్నించండి.",
        LanguageRegister.MARATHI_HINGLISH: "खात्यात आवश्यक रक्कम जमा करा, नंतर लिंक टॅप करून पुन्हा प्रयत्न करा.",
        LanguageRegister.HINGLISH: "खाते में जरूरी राशि डालें, फिर लिंक टैप करके दोबारा कोशिश करें।",
    },
    "EXPIRED_CARD": {
        LanguageRegister.KANNADA_ENGLISH: "ಬ್ಯಾಂಕ್ ಆ್ಯಪ್‌ನಲ್ಲಿ ಕಾರ್ಡ್ ವಿವರ ನವೀಕರಿಸಿ, ನಂತರ ಪಾವತಿ ಲಿಂಕ್ ಟ್ಯಾಪ್ ಮಾಡಿ.",
        LanguageRegister.TANGLISH: "வங்கி செயலியில் அட்டை விவரத்தைப் புதுப்பித்து, பிறகு கட்டண இணைப்பைத் தட்டவும்.",
        LanguageRegister.TELUGU_ENGLISH: "బ్యాంక్ యాప్‌లో కార్డ్ వివరాలు అప్‌డేట్ చేసి, చెల్లింపు లింక్ ట్యాప్ చేయండి.",
        LanguageRegister.MARATHI_HINGLISH: "बँक अॅपमध्ये कार्ड तपशील अपडेट करा, नंतर पेमेंट लिंक टॅप करा.",
        LanguageRegister.HINGLISH: "बैंकिंग ऐप में कार्ड डिटेल अपडेट करें, फिर पेमेंट लिंक टैप करें।",
    },
    "AUTHENTICATION_FAILED": {
        LanguageRegister.KANNADA_ENGLISH: "ಪಾವತಿ ಲಿಂಕ್ ಟ್ಯಾಪ್ ಮಾಡುವ ಮೊದಲು UPI PIN ಅಥವಾ OTP ಸಿದ್ಧವಿರಲಿ.",
        LanguageRegister.TANGLISH: "கட்டண இணைப்பைத் தட்டுவதற்கு முன் UPI PIN அல்லது OTP தயார் வையுங்கள்.",
        LanguageRegister.TELUGU_ENGLISH: "చెల్లింపు లింక్ ట్యాప్ చేయడానికి ముందు UPI PIN లేదా OTP సిద్ధంగా ఉంచండి.",
        LanguageRegister.MARATHI_HINGLISH: "पेमेंट लिंक टॅप करण्यापूर्वी UPI PIN किंवा OTP तयार ठेवा.",
        LanguageRegister.HINGLISH: "पेमेंट लिंक टैप करने से पहले UPI PIN या OTP तैयार रखें।",
    },
    "USER_DROPOFF": {
        LanguageRegister.KANNADA_ENGLISH: "ನಿಮ್ಮ ಆರ್ಡರ್ ಉಳಿದಿದೆ — ಲಿಂಕ್ ಅವಧಿ ಮುಗಿಯುವ ಮೊದಲು ಪಾವತಿ ಪೂರ್ಣಗೊಳಿಸಿ!",
        LanguageRegister.TANGLISH: "உங்கள் ஆர்டர் சேமிக்கப்பட்டுள்ளது — இணைப்பு காலாவதியாகும் முன் பணம் செலுத்துங்கள்!",
        LanguageRegister.TELUGU_ENGLISH: "మీ ఆర్డర్ సేవ్ అయింది — లింక్ గడువు ముగిసేలోపు చెల్లింపు పూర్తి చేయండి!",
        LanguageRegister.MARATHI_HINGLISH: "तुमचा ऑर्डर जतन आहे — लिंक कालबाह्य होण्यापूर्वी पेमेंट पूर्ण करा!",
        LanguageRegister.HINGLISH: "आपका ऑर्डर सेव है — लिंक खत्म होने से पहले पेमेंट पूरा करें!",
    },
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
    if host == "api.trycloudflare.com":
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


def contains_native_script(message: str, register: LanguageRegister) -> bool:
    """True when regional copy includes the expected Indic script block."""
    if register == LanguageRegister.ENGLISH:
        return True
    bounds = _SCRIPT_RANGES.get(register)
    if not bounds or not message:
        return False
    start, end = bounds
    return any(start <= ord(ch) <= end for ch in message)


def render_fallback_message(
    request: RecoveryCopyRequest,
    register: LanguageRegister,
) -> str:
    return build_rich_whatsapp_message(request, register)


def _latin_block(
    request: RecoveryCopyRequest,
    register: LanguageRegister,
    *,
    name: str,
    merchant: str,
    amount: Decimal,
    cause: str,
    tip: str,
) -> str:
    greeting = _GREETINGS.get(register, "Hello")
    possessive = _POSSESSIVES.get(register, "Your")
    return (
        f"{greeting} {name}! {possessive} {merchant} order (₹{amount}) payment {cause}.\n"
        f"💡 Tip: {tip}\n"
        f"🔗 Tap the 1-click payment link below:\n"
        f"{request.payment_link}"
    )


def _native_block(
    request: RecoveryCopyRequest,
    register: LanguageRegister,
    *,
    name: str,
    merchant: str,
    amount: Decimal,
    failure_cat: str,
) -> str | None:
    greeting = _NATIVE_GREETINGS.get(register)
    if not greeting:
        return None
    possessive = _NATIVE_POSSESSIVES[register]
    order_word = _NATIVE_ORDER_WORD[register]
    pay_word = _NATIVE_PAYMENT_WORD[register]
    cause_map = _NATIVE_CAUSE_PHRASES.get(failure_cat, _NATIVE_CAUSE_PHRASES["USER_DROPOFF"])
    cause = cause_map.get(register, cause_map[LanguageRegister.HINGLISH])
    tip_map = _NATIVE_ACTION_TIPS.get(failure_cat, _NATIVE_ACTION_TIPS["USER_DROPOFF"])
    tip = tip_map.get(register, tip_map[LanguageRegister.HINGLISH])
    return (
        f"{greeting} {name}! {possessive} {merchant} {order_word} (₹{amount}) {pay_word} {cause}.\n"
        f"💡 {_NATIVE_TIP_LABEL[register]}: {tip}\n"
        f"🔗 {_NATIVE_LINK_LABEL[register]}\n"
        f"{request.payment_link}"
    )


def build_rich_whatsapp_message(
    request: RecoveryCopyRequest,
    register: LanguageRegister,
    *,
    bank_outage_note: str | None = None,
) -> str:
    """Build dual-script WhatsApp copy (native Indic + Latin) for Green API.

    Regional format::

        {native greeting / cause / 💡 tip / payment link}
        {latin greeting / cause / 💡 tip / payment link}

    Simple English stays a single Latin block. The Razorpay payment link is
    copied character-for-character into every script block.
    """
    name = sanitize_text(request.customer_first_name, fallback="there")
    merchant = sanitize_text(request.merchant_name, max_len=60, fallback="the merchant")
    amount = Decimal(request.order_amount).quantize(Decimal("0.01"))
    failure_cat = classify_failure_code(request.failure_code, request.failure_description)
    cause_map = _CAUSE_PHRASES.get(failure_cat, _CAUSE_PHRASES["USER_DROPOFF"])
    cause = cause_map.get(register, cause_map[LanguageRegister.ENGLISH])
    tip = _ACTION_TIPS.get(failure_cat, _ACTION_TIPS["USER_DROPOFF"])
    latin = _latin_block(
        request, register, name=name, merchant=merchant, amount=amount, cause=cause, tip=tip
    )
    native = _native_block(
        request, register, name=name, merchant=merchant, amount=amount, failure_cat=failure_cat
    )
    message = f"{native}\n\n{latin}" if native else latin
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
        "Diagnose the failure and write one WhatsApp recovery message. "
        "Reply with a single JSON object only. Never invent discounts, refunds, or new URLs. "
        "Copy the payment_link character-for-character into EVERY script block of hinglish_message. "
        "For regional registers, hinglish_message MUST be dual-script: native Indic script first, "
        "then a blank line, then the Latin transliteration. Both blocks need a plain failure cause, "
        "a 💡 actionable tip, and the payment link on its own line. Simple English is one block only."
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
            "hinglish_message": (
                "string, 10-1600 chars, dual-script for regional locales, "
                "must include payment_link exactly in each block"
            ),
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
    if not contains_native_script(output.hinglish_message, register):
        dual = build_rich_whatsapp_message(request, register)
        return output.model_copy(
            update={
                "hinglish_message": dual,
                "contains_payment_link": True,
                "language_register": register,
            }
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

    Prefers a plain ``sendMessage`` with the RecoverPay ``/pay/{{id}}`` URL on
    its own line. WhatsApp URL *buttons* from unofficial APIs often fail to
    open (or open a wrapper), so they are not used as the only tap target.
    """
    import sys

    if _test_mode_enabled():
        print("[GreenAPI] TEST_MODE=true → skipping live send.", file=sys.stderr)
        return False

    instance_id = os.getenv("GREEN_API_INSTANCE_ID", "").strip().strip('"')
    token = os.getenv("GREEN_API_TOKEN", "").strip().strip('"')
    placeholder_markers = ("your_instance", "your_green_api", "changeme", "xxxx", "...")
    if (
        not instance_id
        or not token
        or any(marker in instance_id.lower() or marker in token.lower() for marker in placeholder_markers)
    ):
        print("[GreenAPI] Live credentials missing or placeholder; skipping send.", file=sys.stderr)
        return False

    # Normalise phone: strip whatsapp:/+/spaces, keep digits only
    clean = re.sub(r"\D", "", to_phone.replace("whatsapp:", ""))
    if not clean:
        print("[GreenAPI] Empty phone number; skipping.", file=sys.stderr)
        return False

    chat_id = f"{clean}@c.us"
    clickable = (link_url or "").strip() or first_public_http_url(message_text)
    if clickable and (
        not is_whatsapp_linkifiable(clickable)
        or "/pay/" not in clickable
        or "href.li" in clickable.lower()
        or "rzp.io" in clickable.lower()
    ):
        clickable = None
    if not clickable:
        print("[GreenAPI] No public RecoverPay /pay URL; skipping send.", file=sys.stderr)
        return False
    base = f"https://api.green-api.com/waInstance{instance_id}"

    try:
        import requests as _requests  # type: ignore[import-untyped]

        # Plain text + link preview. GET /pay/{id} is a choice page, so a
        # crawler cannot mark RECOVERED. URL buttons are unreliable on WA.
        if clickable not in message_text:
            message_text = f"{message_text.rstrip()}\n\n{clickable}"
        payload: dict[str, Any] = {
            "chatId": chat_id,
            "message": message_text,
            "linkPreview": True,
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
