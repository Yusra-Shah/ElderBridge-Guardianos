"""
Emergency / family-in-trouble scam detector — pre-pipeline short-circuit.

Detects the "I am your nephew/relative, send money urgently, don't tell
anyone" scam pattern.  Distinct from investment fraud — this exploits
family trust and emotional urgency.

Requires a COMBINATION of signals to avoid false positives on legitimate
family messages:
  relative_claim AND money_request AND (secrecy OR distress_narrative)
"""
from __future__ import annotations

import re

_RELATIVE_CLAIMS = [
    re.compile(r"\b(nephew|uncle|aunty?|brother|sister|cousin|niece|son|daughter|bhai|bhabhi|chacha|phuppo|mamu|khala)\b", re.IGNORECASE),
    re.compile(r"i\s+am\s+your\s+\w+", re.IGNORECASE),
]

_MONEY_REQUESTS = [
    re.compile(r"send\s+(the\s+)?money", re.IGNORECASE),
    re.compile(r"send\s+rs\.?\s*\d", re.IGNORECASE),
    re.compile(r"rs\.?\s*\d{3,}.*\b(send|transfer|deposit)\b", re.IGNORECASE),
    re.compile(r"\b(send|transfer|deposit)\b.*rs\.?\s*\d{3,}", re.IGNORECASE),
    re.compile(r"(jazzcash|easypaisa)\s*\[", re.IGNORECASE),
    re.compile(r"please\s+(send|transfer)", re.IGNORECASE),
]

_SECRECY_SIGNALS = [
    re.compile(r"do\s+not\s+tell", re.IGNORECASE),
    re.compile(r"don.?t\s+tell", re.IGNORECASE),
    re.compile(r"keep\s+(it\s+)?secret", re.IGNORECASE),
    re.compile(r"do\s+not\s+share", re.IGNORECASE),
    re.compile(r"(don.?t|do\s+not)\s+want\s+.{0,20}worry", re.IGNORECASE),
]

_DISTRESS_SIGNALS = [
    re.compile(r"\bhospital\b", re.IGNORECASE),
    re.compile(r"\baccident\b", re.IGNORECASE),
    re.compile(r"\babroad\b", re.IGNORECASE),
    re.compile(r"lost\s+(my\s+)?phone", re.IGNORECASE),
    re.compile(r"\bstranded\b", re.IGNORECASE),
    re.compile(r"\bjail\b", re.IGNORECASE),
    re.compile(r"\barrested\b", re.IGNORECASE),
    re.compile(r"\bemergency\b", re.IGNORECASE),
    re.compile(r"\btreatment\b", re.IGNORECASE),
]

_URGENCY_SIGNALS = [
    re.compile(r"\burgently\b", re.IGNORECASE),
    re.compile(r"\bimmediately\b", re.IGNORECASE),
    re.compile(r"very\s+urgent", re.IGNORECASE),
    re.compile(r"right\s+now", re.IGNORECASE),
    re.compile(r"as\s+soon\s+as", re.IGNORECASE),
]


def detect_emergency_scam(text: str) -> bool:
    """Return True if the text matches the family-in-trouble scam pattern.

    Requires: relative_claim AND money_request AND (secrecy OR distress+urgency).
    """
    if not text or not text.strip():
        return False

    has_relative = any(p.search(text) for p in _RELATIVE_CLAIMS)
    has_money = any(p.search(text) for p in _MONEY_REQUESTS)
    has_secrecy = any(p.search(text) for p in _SECRECY_SIGNALS)
    has_distress = any(p.search(text) for p in _DISTRESS_SIGNALS)
    has_urgency = any(p.search(text) for p in _URGENCY_SIGNALS)

    if not has_relative or not has_money:
        return False

    if has_secrecy:
        return True
    if has_distress and has_urgency:
        return True

    return False


EMERGENCY_SCAM_RESPONSE = (
    "Be very careful. This is a common scam where someone pretends to "
    "be a family member in trouble and asks for urgent money. Real family "
    "members would not ask you to keep it secret from everyone. Before "
    "sending any money, call your actual relative on their real phone "
    "number to check. If you cannot reach them, ask another family member "
    "first. Do not send money to unknown accounts."
)

EMERGENCY_SCAM_NEXT_STEPS = [
    "Do not send any money yet.",
    "Call your actual relative on their known phone number.",
    "Ask another family member to verify the story.",
    "If you cannot verify, do not send money.",
    "Report this to the cybercrime helpline at 9911.",
]
