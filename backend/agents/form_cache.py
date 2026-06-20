"""
Fast-path response cache for known Pakistani government forms.

When the screen text matches a known form type, returns a pre-written accurate
explanation instantly without hitting Azure.  This guarantees the core demo
screens always respond regardless of LLM availability or network latency.

Cached text is plain, short, and elderly-friendly.  No markdown, no dashes.
"""
from __future__ import annotations

import re
from typing import Optional

from schemas.decision_schema import FinalDecision, RiskLevel

_KnownForm = dict  # {patterns: list[re.Pattern], response: FinalDecision}

_KNOWN_FORMS: list[_KnownForm] = [
    {
        "name": "sspa",
        "patterns": [
            re.compile(r"sindh\s+senior\s+citizen", re.IGNORECASE),
            re.compile(r"senior\s+citizen\s+card", re.IGNORECASE),
            re.compile(r"\bsspa\b", re.IGNORECASE),
            re.compile(r"sindh\s+social\s+protection", re.IGNORECASE),
        ],
        "response": FinalDecision(
            response_text=(
                "This is the Sindh Senior Citizen Card application form from the "
                "Sindh Social Protection Authority. It is a government program that "
                "provides financial support to senior citizens in Sindh province. "
                "You will need your CNIC, a recent photo, and proof of age (60 years "
                "or older). Fill in your personal details carefully. If you need help, "
                "visit your nearest SSPA office or call their helpline."
            ),
            risk_flag=RiskLevel.NONE,
            next_steps=[
                "Keep your CNIC ready before filling the form.",
                "Ask a trusted person to help if any field is unclear.",
            ],
            source_citations=[],
        ),
    },
    {
        "name": "nadra_cnic",
        "patterns": [
            re.compile(r"\bnadra\b", re.IGNORECASE),
            re.compile(r"\bcnic\b.*\b(form|appli|renew|modif)", re.IGNORECASE),
            re.compile(r"(form|appli|renew|modif).*\bcnic\b", re.IGNORECASE),
            re.compile(r"national\s+identity", re.IGNORECASE),
        ],
        "response": FinalDecision(
            response_text=(
                "This is a NADRA form for your national identity card (CNIC). "
                "You will need your old CNIC or B-Form, two recent passport size "
                "photos, and a valid document showing your current address. "
                "Fill in each field with your correct details. You can submit this "
                "at any NADRA office. For questions call NADRA at 051 111 786 100."
            ),
            risk_flag=RiskLevel.NONE,
            next_steps=[
                "Gather your documents before starting the form.",
                "For help call NADRA helpline 051 111 786 100.",
            ],
            source_citations=[],
        ),
    },
    {
        "name": "ehsaas",
        "patterns": [
            re.compile(r"\behsaas\b", re.IGNORECASE),
            re.compile(r"ehsaas\s+(program|kafalat|cash|ration)", re.IGNORECASE),
        ],
        "response": FinalDecision(
            response_text=(
                "This is an Ehsaas program form. Ehsaas is the Government of "
                "Pakistan's main social protection program. It provides cash "
                "assistance to eligible families. You will need your CNIC number "
                "and household details. Fill in your information carefully. "
                "For help call the Ehsaas helpline at 0800 26477 (toll free)."
            ),
            risk_flag=RiskLevel.NONE,
            next_steps=[
                "Keep your CNIC number ready.",
                "For questions call Ehsaas helpline 0800 26477.",
            ],
            source_citations=[],
        ),
    },
    {
        "name": "bisp",
        "patterns": [
            re.compile(r"\bbisp\b", re.IGNORECASE),
            re.compile(r"benazir\s+income", re.IGNORECASE),
        ],
        "response": FinalDecision(
            response_text=(
                "This is a BISP (Benazir Income Support Programme) form. BISP "
                "provides financial assistance to low income families across "
                "Pakistan. You will need your CNIC and may need to provide "
                "household income details. Fill in the form with your correct "
                "information. For help call the BISP helpline at 0800 26477."
            ),
            risk_flag=RiskLevel.NONE,
            next_steps=[
                "Keep your CNIC number ready.",
                "For questions call BISP helpline 0800 26477.",
            ],
            source_citations=[],
        ),
    },
    {
        "name": "utility_bill",
        "patterns": [
            re.compile(r"(electricity|gas|water|wapda|k.electric|sngpl|ssgc)\s*(bill|payment|due)", re.IGNORECASE),
            re.compile(r"(bill|payment)\s*(electricity|gas|water|wapda|k.electric)", re.IGNORECASE),
            re.compile(r"utility\s+bill", re.IGNORECASE),
            re.compile(r"(consumer|reference)\s*(number|no|id).*bill", re.IGNORECASE),
        ],
        "response": FinalDecision(
            response_text=(
                "This is a utility bill payment screen. Check the amount due and "
                "the due date carefully before paying. Make sure the consumer or "
                "reference number matches your bill. You can pay at your bank, "
                "through JazzCash or Easypaisa, or at any authorized payment point."
            ),
            risk_flag=RiskLevel.NONE,
            next_steps=[
                "Verify the amount and due date match your paper bill.",
                "For billing issues call 118 (WAPDA) or 119 (gas).",
            ],
            source_citations=[],
        ),
    },
]


def check_form_cache(text: str, source_app: str = "") -> Optional[FinalDecision]:
    """Check if the screen text matches a known Pakistani government form.

    Returns a pre-written FinalDecision if matched, None otherwise.
    """
    if not text or len(text.strip()) < 10:
        return None

    for form in _KNOWN_FORMS:
        for pattern in form["patterns"]:
            if pattern.search(text):
                return form["response"]

    return None
