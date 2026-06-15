"""
ElderBridge GuardianOS — Mock Official Source Database.

Static dataset used by the Research Engine in offline / no-API mode.
Covers the four content areas required for MVP demos:
  A. Senior healthcare benefit programs
  B. Pension document requirements
  C. Common government form fields
  D. Known scam SMS patterns

Each source follows the tier hierarchy from RESEARCH_ENGINE.md §5:
  Tier 1 — Official government / healthcare / bank websites
  Tier 2 — Recognised public-service organisations / official advisories
  Tier 3 — Reputable news / advisories
  Tier 4 — Community resource directories
  Tier 5 — Unknown domains, forums, unverified social posts

Swapping in a live RAG database or web-search API is a one-file change:
replace `MOCK_SOURCES` with a real retrieval call in engine.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MockSource:
    source_id: str
    title: str
    tier: int           # 1–5 per RESEARCH_ENGINE.md §5
    url: str
    content_snippet: str
    last_verified: date


# ---------------------------------------------------------------------------
# A. Senior healthcare benefit programs — Tier 1 & 2
# ---------------------------------------------------------------------------

SRC_HEALTHCARE_ELIGIBILITY = MockSource(
    source_id="src_hc_001",
    title="Senior Healthcare Assistance Program — Eligibility Guidelines",
    tier=1,
    url="https://health.gov.example/senior-assistance/eligibility",
    content_snippet=(
        "Citizens aged 65 and above may apply for the Senior Healthcare Assistance Program. "
        "Applicants must provide proof of age, national identity document, and evidence of "
        "income below the defined threshold. Healthcare benefit covers outpatient consultations, "
        "prescribed medication, and preventive screening. Applications are submitted online or "
        "at designated district health offices. No OTP or password is required during application."
    ),
    last_verified=date(2025, 11, 1),
)

SRC_HEALTHCARE_COST_REDUCTION = MockSource(
    source_id="src_hc_002",
    title="Healthcare Cost Reduction Scheme for Seniors — Application Process",
    tier=1,
    url="https://health.gov.example/cost-reduction/seniors",
    content_snippet=(
        "The Healthcare Cost Reduction Scheme provides subsidy for senior citizens on "
        "prescription medicine and specialist consultations. Eligible applicants are residents "
        "aged 60 or above with a valid national identity card. Required documents include the "
        "identity card, recent utility bill as proof of address, and most recent pension "
        "or income statement. Benefits are disbursed directly to registered healthcare providers. "
        "Never share your healthcare benefit PIN or OTP with anyone claiming to process your application."
    ),
    last_verified=date(2025, 12, 15),
)

SRC_HEALTHCARE_ADVISORY = MockSource(
    source_id="src_hc_003",
    title="Official Healthcare Program Directory — Senior Benefit Eligibility Checker",
    tier=2,
    url="https://seniorcare.org.example/benefit-checker",
    content_snippet=(
        "This directory lists government-recognised healthcare support programs available to "
        "senior citizens. Programs include subsidised medicine, home care assistance, and "
        "dental support for qualifying seniors. Eligibility is determined by age, income, "
        "and residency status. Do not enter your national identity number or financial details "
        "on websites not listed in this directory. Always verify program authenticity before applying."
    ),
    last_verified=date(2025, 10, 20),
)

# ---------------------------------------------------------------------------
# B. Pension document requirements — Tier 1 & 2
# ---------------------------------------------------------------------------

SRC_PENSION_DOCS = MockSource(
    source_id="src_pen_001",
    title="Pension Documentation Requirements — Official Application Guide",
    tier=1,
    url="https://pension.gov.example/apply/documents",
    content_snippet=(
        "To apply for a pension or renew pension entitlement, applicants must submit: "
        "(1) original national identity card or passport, (2) proof of employment or service "
        "record, (3) bank account details for direct deposit — provide these only on the official "
        "pension portal, (4) most recent income or salary slip, and (5) two passport photographs. "
        "The pension department will NEVER request your ATM PIN, OTP, or passwords via SMS or phone call. "
        "Submit documents in person or through the official secure online portal only."
    ),
    last_verified=date(2025, 9, 30),
)

SRC_PENSION_RENEWAL = MockSource(
    source_id="src_pen_002",
    title="Annual Pension Renewal — Required Documents Checklist",
    tier=1,
    url="https://pension.gov.example/renew/checklist",
    content_snippet=(
        "Annual pension renewal requires submission of a life certificate confirming the "
        "pensioner is alive, along with an updated identity document and proof of current address. "
        "Life certificates may be obtained from designated banks, post offices, or government offices. "
        "Renewal reminders are sent by official post — not by SMS links. "
        "If you receive a renewal request via SMS asking you to click a link or enter an OTP, "
        "it is likely a fraudulent message. Report suspicious messages to the pension helpline."
    ),
    last_verified=date(2025, 11, 10),
)

# ---------------------------------------------------------------------------
# C. Common government form fields — Tier 1 & 2
# ---------------------------------------------------------------------------

SRC_FORM_GLOSSARY = MockSource(
    source_id="src_form_001",
    title="Government Form Field Glossary — Plain Language Definitions",
    tier=2,
    url="https://forms.gov.example/help/glossary",
    content_snippet=(
        "Annual household income: total money received by all members of your household "
        "in one year before tax or deductions. Number of dependants: people who rely on you "
        "financially, such as children or elderly parents. Proof of address: a document showing "
        "where you live, such as a utility bill, bank statement, or lease agreement dated within "
        "three months. National identity number: your unique government-issued identification number — "
        "only enter this on official government websites. Proof of income: a salary slip, pension "
        "statement, or bank statement showing your regular income."
    ),
    last_verified=date(2025, 8, 15),
)

SRC_HOUSING_SUPPORT = MockSource(
    source_id="src_hou_001",
    title="Housing Support for Elderly Residents — Program Overview",
    tier=2,
    url="https://housing.gov.example/elderly-support",
    content_snippet=(
        "The Elderly Housing Support Program provides rental assistance and repair grants to "
        "senior citizens facing housing difficulties. Eligible applicants must be 65 or older, "
        "own or rent their primary residence, and demonstrate financial need through an income "
        "declaration form. Required documents include proof of age, identity card, tenancy "
        "agreement or property deed, and utility bills. Applications are reviewed within 30 days. "
        "Benefit amounts depend on household income and housing costs. Apply at your local housing office."
    ),
    last_verified=date(2025, 7, 20),
)

# ---------------------------------------------------------------------------
# D. Known scam SMS and fraud patterns — Tier 1 & 2
# ---------------------------------------------------------------------------

SRC_SCAM_ADVISORY = MockSource(
    source_id="src_scam_001",
    title="National Cyber Crime Unit — SMS Scam Patterns and Advisories",
    tier=1,
    url="https://cybercrime.gov.example/advisories/sms-scams",
    content_snippet=(
        "Common SMS scam patterns targeting senior citizens: (1) Fake benefit approval messages "
        "claiming a grant has been approved and requiring the recipient to click a link or enter "
        "an OTP to claim it. (2) Urgent messages claiming a pension or account has been suspended "
        "and requiring immediate action. (3) Messages impersonating government agencies requesting "
        "CNIC, bank account numbers, or one-time passwords. (4) Prize or lottery notifications "
        "requiring a processing fee. Official government agencies never request OTPs, passwords, "
        "or fees via SMS. Report suspicious messages immediately."
    ),
    last_verified=date(2026, 1, 5),
)

SRC_OTP_AWARENESS = MockSource(
    source_id="src_scam_002",
    title="Consumer Protection Advisory — OTP and Password Security for Seniors",
    tier=2,
    url="https://consumerprotection.gov.example/otp-security",
    content_snippet=(
        "One-time passwords (OTPs) are single-use codes sent to your registered mobile number "
        "to verify your identity during secure transactions. You should NEVER share an OTP with "
        "anyone — not even someone claiming to be from your bank, government office, or healthcare "
        "provider. Scammers often create urgency by claiming your account will be closed or a benefit "
        "will expire if you do not provide the OTP immediately. If you receive an unsolicited OTP, "
        "do not use it and contact your bank or service provider directly using their official number."
    ),
    last_verified=date(2025, 12, 1),
)

# ---------------------------------------------------------------------------
# E. Community directory — Tier 4
# ---------------------------------------------------------------------------

SRC_COMMUNITY_DIRECTORY = MockSource(
    source_id="src_comm_001",
    title="Elder Support Community Resource Directory",
    tier=4,
    url="https://community.eldercare.example/resources",
    content_snippet=(
        "Community-compiled list of support services for elderly residents. Includes local "
        "healthcare clinics, pension advisory centres, government form assistance desks, "
        "legal aid services for seniors, and social welfare offices. Listings are maintained "
        "by volunteer coordinators and may not always reflect the latest program details. "
        "Always verify eligibility and benefit amounts directly with the official government "
        "website or office before applying or making any decisions based on this directory."
    ),
    last_verified=date(2025, 6, 1),
)

# ---------------------------------------------------------------------------
# F. Unverified social content — Tier 5 (used to test human-review escalation)
# ---------------------------------------------------------------------------

SRC_UNVERIFIED_SOCIAL = MockSource(
    source_id="src_social_001",
    title="Unverified Social Post — Viral Claim About Free Senior Lottery Prize",
    tier=5,
    url="https://unknown-forum.example/post/lottery-inheritance-winner",
    content_snippet=(
        "SHARE THIS POST: Every senior citizen is eligible for a free lottery prize and unclaimed "
        "inheritance fund from the government. Click the link to verify your jackpot winner status "
        "and claim your windfall today. This viral chain message has been forwarded by thousands. "
        "Limited time offer — act fast before the jackpot prize expires."
    ),
    last_verified=date(2024, 3, 15),
)

# ---------------------------------------------------------------------------
# Master list — consumed by the Research Engine
# ---------------------------------------------------------------------------

MOCK_SOURCES: list[MockSource] = [
    SRC_HEALTHCARE_ELIGIBILITY,
    SRC_HEALTHCARE_COST_REDUCTION,
    SRC_HEALTHCARE_ADVISORY,
    SRC_PENSION_DOCS,
    SRC_PENSION_RENEWAL,
    SRC_FORM_GLOSSARY,
    SRC_HOUSING_SUPPORT,
    SRC_SCAM_ADVISORY,
    SRC_OTP_AWARENESS,
    SRC_COMMUNITY_DIRECTORY,
    SRC_UNVERIFIED_SOCIAL,
]
