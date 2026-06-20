"""
Financial fraud / investment scam detector — pre-pipeline short-circuit.

Runs before the full agent pipeline (same pattern as injection_detector.py).
Catches high-confidence investment scam signals: crypto mentions, guaranteed
returns, referral schemes with invite links.

Conservative by design: requires a COMBINATION of signals to trigger.
A single weak signal (e.g. just the word "invest") does NOT fire.

Safe-context bypass: medical, bank statement, university, and utility bill
screens are never flagged (reuses guardrail_agent.SAFE_CONTEXTS).
"""
from __future__ import annotations

import re

from agents.guardrail_agent import _COMPILED_SAFE

_CRYPTO_SIGNALS = [
    re.compile(r"\busdt\b", re.IGNORECASE),
    re.compile(r"\bcrypto\b", re.IGNORECASE),
    re.compile(r"\bbitcoin\b", re.IGNORECASE),
    re.compile(r"\bethereum\b", re.IGNORECASE),
    re.compile(r"\bblockchain\b", re.IGNORECASE),
    re.compile(r"\btether\b", re.IGNORECASE),
    re.compile(r"\bbinance\b", re.IGNORECASE),
]

_UNREALISTIC_RETURNS = [
    re.compile(r"daily\s+returns?\s*\d", re.IGNORECASE),
    re.compile(r"guaranteed\s+(profit|returns?|income|earning)", re.IGNORECASE),
    re.compile(r"earn\s+(passively|passive)", re.IGNORECASE),
    re.compile(r"passive\s+(income|earning)", re.IGNORECASE),
    re.compile(r"break\s+even\s+in\s+\d+\s*day", re.IGNORECASE),
    re.compile(r"\d+\s*%\s*(daily|per\s*day)", re.IGNORECASE),
    re.compile(r"double\s+your\s+(money|investment)", re.IGNORECASE),
    re.compile(r"\d+\s*percent\s*(daily|per\s*day|returns?)", re.IGNORECASE),
]

_REFERRAL_SIGNALS = [
    re.compile(r"invite\s+(friends?|code)", re.IGNORECASE),
    re.compile(r"referral\s+(code|bonus|commission)", re.IGNORECASE),
    re.compile(r"commission\s+(for|when|on|earn)", re.IGNORECASE),
    re.compile(r"earn\s+(by\s+)?invit", re.IGNORECASE),
    re.compile(r"invite[_\-]?code", re.IGNORECASE),
]

_LINK_PATTERNS = [
    re.compile(r"https?://\S*invite", re.IGNORECASE),
    re.compile(r"https?://\S*ref[=&]", re.IGNORECASE),
    re.compile(r"t\.me/", re.IGNORECASE),
    re.compile(r"wa\.me/", re.IGNORECASE),
    re.compile(r"https?://\S+", re.IGNORECASE),
]

_URGENCY_SIGNALS = [
    re.compile(r"join\s+now", re.IGNORECASE),
    re.compile(r"register\s+now", re.IGNORECASE),
    re.compile(r"sign\s+up\s+now", re.IGNORECASE),
    re.compile(r"limited\s+(time|spots?|offer)", re.IGNORECASE),
]

_PRIZE_LOTTERY_SIGNALS = [
    re.compile(r"lucky\s+draw", re.IGNORECASE),
    re.compile(r"selected\s+winner", re.IGNORECASE),
    re.compile(r"claim\s+your\s+prize", re.IGNORECASE),
    re.compile(r"prize\s+distribution", re.IGNORECASE),
    re.compile(r"call\s+within\s+\d+\s*hours?\s+to\s+claim", re.IGNORECASE),
    re.compile(r"reference\s+number\s+jld", re.IGNORECASE),
]

_BANKING_IMPERSONATION = [
    re.compile(r"your\s+account\s+will\s+be\s+blocked", re.IGNORECASE),
    re.compile(r"verify\s+your\s+account", re.IGNORECASE),
    re.compile(r"unusual\s+activity\s+detected\s+on\s+your\s+account", re.IGNORECASE),
]

_BANKING_ACTION = [
    re.compile(r"click\s+here", re.IGNORECASE),
    re.compile(r"call\s+now", re.IGNORECASE),
    re.compile(r"share\s+(your\s+)?otp", re.IGNORECASE),
]

_JOB_SCAM_SIGNALS = [
    re.compile(r"work\s+from\s+home\s+earn\s+daily", re.IGNORECASE),
    re.compile(r"online\s+typing\s+job", re.IGNORECASE),
    re.compile(r"data\s+entry\s+job\s+earn\s+per\s+hour", re.IGNORECASE),
]

_JOB_SCAM_FEE = [
    re.compile(r"advance\s+fee", re.IGNORECASE),
    re.compile(r"registration\s+fee", re.IGNORECASE),
    re.compile(r"security\s+deposit\s+required\s+first", re.IGNORECASE),
]

_PRIZE_REGISTRATION_SIGNALS = [
    re.compile(r"shortlisted\s+(for\s+)?(prize|reward|cash|internship)", re.IGNORECASE),
    re.compile(r"selected\s+(for\s+)?(reward|cash\s+prize|internship)", re.IGNORECASE),
    re.compile(r"cash\s+prize", re.IGNORECASE),
    re.compile(r"prize\s+and\s+internship", re.IGNORECASE),
    re.compile(r"you\s+(have\s+been|are)\s+(selected|shortlisted|chosen)", re.IGNORECASE),
    re.compile(r"congratulations\s+you\s+(are|have)", re.IGNORECASE),
]

_REGISTRATION_FEE_SIGNALS = [
    re.compile(r"(one|1)\s*time\s+registration", re.IGNORECASE),
    re.compile(r"registration\s+fee", re.IGNORECASE),
    re.compile(r"pay\s+to\s+register", re.IGNORECASE),
    re.compile(r"advance\s+(fee|payment)", re.IGNORECASE),
    re.compile(r"security\s+deposit", re.IGNORECASE),
]

_FAKE_OPPORTUNITY_SIGNALS = [
    re.compile(r"earn\s+from\s+home", re.IGNORECASE),
    re.compile(r"online\s+earning", re.IGNORECASE),
    re.compile(r"typing\s+job", re.IGNORECASE),
    re.compile(r"data\s+entry\s+job", re.IGNORECASE),
    re.compile(r"work\s+from\s+home\s+earn", re.IGNORECASE),
]

_SCAM_URGENCY_SIGNALS = [
    re.compile(r"last\s+day", re.IGNORECASE),
    re.compile(r"final\s+call", re.IGNORECASE),
    re.compile(r"limited\s+(time|seats?|spots?)", re.IGNORECASE),
    re.compile(r"hurry", re.IGNORECASE),
    re.compile(r"closing\s+soon", re.IGNORECASE),
]


def detect_financial_fraud(text: str) -> bool:
    """Return True if the text contains a high-confidence investment scam pattern.

    Requires a combination of signals to avoid false positives on legitimate
    bank or financial messages.  Trigger conditions (any one fires):
      1. crypto_mention AND unrealistic_returns
      2. referral_pattern AND link_pattern
      3. crypto_mention AND (referral OR urgency)
      4. unrealistic_returns AND (referral OR link_pattern)
    """
    if not text or not text.strip():
        return False

    for pat in _COMPILED_SAFE:
        if pat.search(text):
            return False

    has_crypto = any(p.search(text) for p in _CRYPTO_SIGNALS)
    has_unrealistic = any(p.search(text) for p in _UNREALISTIC_RETURNS)
    has_referral = any(p.search(text) for p in _REFERRAL_SIGNALS)
    has_link = any(p.search(text) for p in _LINK_PATTERNS)
    has_urgency = any(p.search(text) for p in _URGENCY_SIGNALS)

    if has_crypto and has_unrealistic:
        return True
    if has_referral and has_link:
        return True
    if has_crypto and (has_referral or has_urgency):
        return True
    if has_unrealistic and (has_referral or has_link):
        return True

    has_prize = any(p.search(text) for p in _PRIZE_LOTTERY_SIGNALS)
    has_bank_impersonation = any(p.search(text) for p in _BANKING_IMPERSONATION)
    has_bank_action = any(p.search(text) for p in _BANKING_ACTION)
    has_job_scam = any(p.search(text) for p in _JOB_SCAM_SIGNALS)
    has_job_fee = any(p.search(text) for p in _JOB_SCAM_FEE)

    if has_prize and has_link:
        return True
    if has_bank_impersonation and has_bank_action:
        return True
    if has_job_scam and has_job_fee:
        return True

    has_prize_reg = any(p.search(text) for p in _PRIZE_REGISTRATION_SIGNALS)
    has_reg_fee = any(p.search(text) for p in _REGISTRATION_FEE_SIGNALS)
    has_fake_opp = any(p.search(text) for p in _FAKE_OPPORTUNITY_SIGNALS)
    has_scam_urgency = any(p.search(text) for p in _SCAM_URGENCY_SIGNALS)

    if has_prize_reg and has_reg_fee:
        return True
    if has_prize_reg and has_scam_urgency and has_link:
        return True
    if has_fake_opp and has_reg_fee:
        return True

    return False


FRAUD_BLOCK_RESPONSE = (
    "This looks like an investment scam. Messages promising easy daily profits, "
    "guaranteed returns, or rewards for inviting friends are common fraud tactics. "
    "No real investment guarantees fixed daily returns. "
    "Do not send any money, do not click any links, and do not share your "
    "personal details. If someone you know sent this, they may have been "
    "tricked too. You can report this to the cybercrime helpline at 9911."
)

FRAUD_NEXT_STEPS = [
    "Do not send any money or cryptocurrency.",
    "Do not click any links in this message.",
    "Do not share personal or bank details.",
    "Report this to the cybercrime helpline at 9911.",
    "Contact your trusted family member or caregiver.",
]
