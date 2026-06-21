"""
Phishing website detector — pre-pipeline short-circuit.

Catches websites impersonating Pakistani government institutions.
Checks for: URL pattern mismatches (non-.gov.pk domain claiming to be
NADRA, BISP, etc.), government branding on unofficial domains, requests
for CNIC plus payment on unofficial sites.

Only fires when source_app is a browser.
"""
from __future__ import annotations

import re

_BROWSERS = ["chrome", "firefox", "brave", "opera", "edge", "browser", "webview", "samsung"]

_OFFICIAL_DOMAINS: dict[str, list[str]] = {
    "nadra":         ["nadra.gov.pk"],
    "bisp":          ["bisp.gov.pk"],
    "ehsaas":        ["ehsaas.gov.pk", "pass.gov.pk", "8171.pass.gov.pk"],
    "fbr":           ["fbr.gov.pk", "iris.fbr.gov.pk"],
    "pakistan post":  ["ep.gov.pk", "pakpost.gov.pk"],
    "sindh":         ["sindh.gov.pk", "swd.sindh.gov.pk", "gos.pk"],
    "punjab":        ["punjab.gov.pk"],
    "kp":            ["kp.gov.pk"],
    "balochistan":   ["balochistan.gov.pk"],
    "sbp":           ["sbp.org.pk"],
    "state bank":    ["sbp.org.pk"],
    "secp":          ["secp.gov.pk"],
    "pta":           ["pta.gov.pk"],
    "pemra":         ["pemra.gov.pk"],
    "jazz":          ["jazz.com.pk"],
    "telenor":       ["telenor.com.pk"],
    "ufone":         ["ufone.com"],
    "zong":          ["zong.com.pk"],
}

_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

_DOMAIN_RE = re.compile(
    r'(?:https?://)?([a-zA-Z0-9][-a-zA-Z0-9]*(?:\.[a-zA-Z0-9][-a-zA-Z0-9]*)+)',
)

_PAYMENT_SIGNALS = [
    re.compile(r"(processing|registration|renewal|service)\s*fee", re.IGNORECASE),
    re.compile(r"pay\s*(online|now|rs|pkr|fee)", re.IGNORECASE),
    re.compile(r"rs\.?\s*\d{2,}", re.IGNORECASE),
    re.compile(r"pkr\.?\s*\d{2,}", re.IGNORECASE),
    re.compile(r"(jazzcash|easypaisa|credit\s*card)\s*(payment|pay)", re.IGNORECASE),
]

_PERSONAL_DATA_SIGNALS = [
    re.compile(r"\bcnic\b", re.IGNORECASE),
    re.compile(r"mother.{0,5}(maiden|name)", re.IGNORECASE),
    re.compile(r"date\s*of\s*birth", re.IGNORECASE),
    re.compile(r"father.{0,5}name", re.IGNORECASE),
]


def detect_phishing(text: str, source_app: str) -> bool:
    """Return True if the screen looks like a phishing site impersonating a government institution."""
    if not text or not text.strip():
        return False

    if not any(b in source_app.lower() for b in _BROWSERS):
        return False

    text_lower = text.lower()

    email_positions = set()
    for m in _EMAIL_RE.finditer(text):
        email_positions.add(m.start())
    domains_found = []
    for m in _DOMAIN_RE.finditer(text):
        at_pos = text.rfind("@", max(0, m.start() - 50), m.start())
        if at_pos >= 0 and m.start() - at_pos < 50:
            continue
        domains_found.append(m.group(1).lower())

    if not domains_found:
        return False

    has_payment = any(p.search(text) for p in _PAYMENT_SIGNALS)
    has_personal = any(p.search(text) for p in _PERSONAL_DATA_SIGNALS)

    for institution, official_list in _OFFICIAL_DOMAINS.items():
        if institution not in text_lower:
            continue
        for domain in domains_found:
            is_official = any(off in domain for off in official_list)
            if is_official:
                continue
            if domain.endswith(".gov.pk"):
                continue
            if has_payment or has_personal:
                return True

    return False


PHISHING_BLOCK_RESPONSE = (
    "Be careful. This website is pretending to be a government agency but "
    "the web address is not an official .gov.pk website. Government websites "
    "in Pakistan always use .gov.pk addresses. No real government agency "
    "charges fees through a website for services like CNIC renewal. "
    "Do not enter any personal information on this page. Visit the real "
    "government office in person or go to the official .gov.pk website directly."
)

PHISHING_NEXT_STEPS = [
    "Close this website immediately.",
    "Do not enter your CNIC or any personal details.",
    "Do not make any payment on this site.",
    "Visit the official .gov.pk website or go to the office in person.",
    "Report this to the cybercrime helpline at 9911.",
]
