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
                "You will need your CNIC and proof of age (60 years or older). "
                "Fill in your personal details carefully. If you need help, "
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
                "You will need your old CNIC or B-Form and a valid document "
                "showing your current address. "
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
    {
        "name": "watan_card",
        "patterns": [
            re.compile(r"watan\s+card", re.IGNORECASE),
            re.compile(r"sindh\s+(social\s+)?relief", re.IGNORECASE),
            re.compile(r"flood\s+relief\s+sindh", re.IGNORECASE),
        ],
        "response": FinalDecision(
            response_text=(
                "The Watan Card is a Sindh government program that provides "
                "financial relief to families affected by floods and natural "
                "disasters. You will need your CNIC, proof of residence in the "
                "affected area, and any damage assessment documents. Visit your "
                "nearest district relief office to apply or check your eligibility."
            ),
            risk_flag=RiskLevel.NONE,
            next_steps=[
                "Bring your CNIC and proof of address to the relief office.",
                "For help call the Sindh Relief helpline.",
            ],
            source_citations=[],
        ),
    },
    {
        "name": "zakat_ushr",
        "patterns": [
            re.compile(r"\bzakat\b", re.IGNORECASE),
            re.compile(r"\bushr\b", re.IGNORECASE),
            re.compile(r"\bmustahiq\b", re.IGNORECASE),
            re.compile(r"deserving\s+famil", re.IGNORECASE),
        ],
        "response": FinalDecision(
            response_text=(
                "The government Zakat program provides financial assistance to "
                "deserving families (mustahiq). You may qualify if your savings "
                "are below the nisab threshold. Apply through your local zakat "
                "committee or district zakat office. You will need your CNIC "
                "and proof of income. For help call 051 9203736."
            ),
            risk_flag=RiskLevel.NONE,
            next_steps=[
                "Contact your local zakat committee to apply.",
                "For help call the Zakat Department at 051 9203736.",
            ],
            source_citations=[],
        ),
    },
    {
        "name": "eobi",
        "patterns": [
            re.compile(r"\beobi\b", re.IGNORECASE),
            re.compile(r"employees\s+old.age\s+benefit", re.IGNORECASE),
            re.compile(r"pension\s+contribution", re.IGNORECASE),
            re.compile(r"old\s+age\s+benefit", re.IGNORECASE),
        ],
        "response": FinalDecision(
            response_text=(
                "EOBI (Employees Old-Age Benefits Institution) provides pensions "
                "to retired employees who contributed during their working years. "
                "To claim your pension you need your CNIC, EOBI registration number, "
                "and retirement letter from your employer. Visit your nearest EOBI "
                "office or apply online at eobi.gov.pk."
            ),
            risk_flag=RiskLevel.NONE,
            next_steps=[
                "Keep your EOBI card and CNIC ready.",
                "Visit the nearest EOBI office or call their helpline.",
            ],
            source_citations=[],
        ),
    },
    {
        "name": "sehat_sahulat",
        "patterns": [
            re.compile(r"sehat\s*sahulat", re.IGNORECASE),
            re.compile(r"health\s+card", re.IGNORECASE),
            re.compile(r"seht?\s*sahulat", re.IGNORECASE),
            re.compile(r"sehat\s+card", re.IGNORECASE),
        ],
        "response": FinalDecision(
            response_text=(
                "Sehat Sahulat is the government free health insurance program. "
                "It covers hospital treatment up to Rs 1 million per family per "
                "year at empanelled hospitals. To register, visit a Sehat Sahulat "
                "counter at any participating hospital with your CNIC. Check your "
                "eligibility by sending your CNIC number to 8500."
            ),
            risk_flag=RiskLevel.NONE,
            next_steps=[
                "Send your CNIC number to 8500 to check eligibility.",
                "Visit any empanelled hospital with your CNIC to register.",
            ],
            source_citations=[],
        ),
    },
    {
        "name": "kisan_card",
        "patterns": [
            re.compile(r"kisan\s*card", re.IGNORECASE),
            re.compile(r"kisaan\s*card", re.IGNORECASE),
            re.compile(r"\bfasal\b", re.IGNORECASE),
            re.compile(r"agriculture\s+subsidy\s+punjab", re.IGNORECASE),
        ],
        "response": FinalDecision(
            response_text=(
                "The Punjab Kisan Card provides subsidised agricultural inputs "
                "like seeds, fertilizer, and pesticides to registered farmers. "
                "You need your CNIC, land ownership documents, and Khasra number "
                "to apply. Visit your tehsil agriculture office to register and "
                "receive your card."
            ),
            risk_flag=RiskLevel.NONE,
            next_steps=[
                "Bring your CNIC and land documents to the agriculture office.",
                "Ask your local patwari for your Khasra number if needed.",
            ],
            source_citations=[],
        ),
    },
    {
        "name": "hec_scholarship",
        "patterns": [
            re.compile(r"scholarship\s+form", re.IGNORECASE),
            re.compile(r"higher\s+education\s+commission", re.IGNORECASE),
            re.compile(r"\bhec\b", re.IGNORECASE),
            re.compile(r"student\s+loan\s+pakistan", re.IGNORECASE),
        ],
        "response": FinalDecision(
            response_text=(
                "HEC (Higher Education Commission) offers scholarships and "
                "interest-free student loans for Pakistani students. Apply "
                "through the HEC online portal at hec.gov.pk. You will need "
                "your academic transcripts, CNIC, income certificate, and "
                "university admission letter. Applications have fixed deadlines "
                "so check the HEC website for current dates."
            ),
            risk_flag=RiskLevel.NONE,
            next_steps=[
                "Check current deadlines on hec.gov.pk.",
                "Prepare your transcripts and income certificate.",
            ],
            source_citations=[],
        ),
    },
    {
        "name": "pensioner_portal",
        "patterns": [
            re.compile(r"\bpensioner\b", re.IGNORECASE),
            re.compile(r"pension\s+payment", re.IGNORECASE),
            re.compile(r"retired\s+government", re.IGNORECASE),
            re.compile(r"\bgpf\b", re.IGNORECASE),
            re.compile(r"general\s+provident\s+fund", re.IGNORECASE),
        ],
        "response": FinalDecision(
            response_text=(
                "You can check your government pension status and payment "
                "details through the AGPR (Accountant General Pakistan Revenues) "
                "office. Bring your pension book, CNIC, and last payment slip. "
                "For GPF balance or pension queries, contact AGPR helpline at "
                "051 9208637 or visit your district accounts office."
            ),
            risk_flag=RiskLevel.NONE,
            next_steps=[
                "Keep your pension book and CNIC ready.",
                "Contact AGPR helpline at 051 9208637.",
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
