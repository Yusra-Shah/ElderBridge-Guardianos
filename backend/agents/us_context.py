"""
US regional context — maps Pakistani programs to US equivalents.

Used only for hackathon Devpost descriptions and judge-facing materials,
NOT in the live pipeline.  Helps US-based evaluators understand the
significance of each detection and assistance capability.
"""
from __future__ import annotations

US_ANALOGIES: dict[str, str] = {
    "SSPA Senior Citizen Card": (
        "US equivalent: Social Security Administration (SSA) elderly benefits "
        "enrollment. Like applying for Social Security retirement benefits at "
        "your local SSA office, this program provides monthly financial support "
        "to senior citizens who meet age and income criteria."
    ),
    "NADRA CNIC": (
        "US equivalent: DMV state ID or Social Security card. The CNIC is "
        "Pakistan's national identity document, similar to a US state-issued "
        "ID card. NADRA is the equivalent of a combined DMV and Social Security "
        "Administration for identity documents."
    ),
    "Ehsaas/BISP": (
        "US equivalent: SNAP (food stamps) or Medicaid enrollment. Ehsaas and "
        "BISP are Pakistan's largest social safety net programs, providing cash "
        "transfers to low-income families, similar to how SNAP provides food "
        "assistance and Medicaid provides healthcare to qualifying Americans."
    ),
    "EOBI pension": (
        "US equivalent: 401(k) or pension claim process. EOBI is Pakistan's "
        "mandatory employer-contributed retirement fund, similar to Social "
        "Security retirement benefits combined with an employer pension plan. "
        "Workers contribute during employment and claim monthly payments after "
        "retirement."
    ),
    "Sehat Sahulat": (
        "US equivalent: Medicaid health insurance enrollment. Sehat Sahulat "
        "provides free health insurance covering hospital care up to a yearly "
        "limit, similar to how Medicaid provides healthcare coverage to "
        "low-income Americans. Families register with their national ID at "
        "participating hospitals."
    ),
    "Zakat program": (
        "US equivalent: local government welfare and food assistance programs. "
        "The government Zakat system collects and redistributes charitable funds "
        "to deserving families, functioning similarly to state-level welfare "
        "programs and food banks in the US."
    ),
    "Watan Card": (
        "US equivalent: FEMA disaster relief assistance. The Watan Card "
        "provides emergency financial relief to families affected by floods "
        "and natural disasters, similar to FEMA Individual Assistance grants "
        "that help American families recover from hurricanes, wildfires, and "
        "other disasters."
    ),
    "HEC scholarship": (
        "US equivalent: FAFSA student aid application. HEC scholarships and "
        "interest-free student loans help Pakistani students fund higher "
        "education, similar to how FAFSA determines eligibility for federal "
        "Pell Grants, subsidized loans, and work-study programs in the US."
    ),
    "Investment scam (pig butchering)": (
        "US context: The FTC warns this is the number one scam targeting "
        "elderly Americans, with losses exceeding 3.4 billion dollars in 2023. "
        "Victims are groomed over weeks via messaging apps and lured into fake "
        "crypto trading platforms showing fabricated returns. ElderBridge "
        "detects these scams pre-pipeline using signal combination analysis."
    ),
    "Emergency family scam": (
        "US context: Known as the grandparent scam. FBI reports elderly "
        "Americans lose over 500 million dollars annually to callers "
        "impersonating grandchildren or relatives in distress. ElderBridge "
        "detects the combination of relative claims, urgent money requests, "
        "and secrecy instructions."
    ),
    "Phishing government sites": (
        "US context: IRS and SSA impersonation scams are the top FTC complaint "
        "category. Scammers create fake government websites to steal identity "
        "information and charge fraudulent fees. ElderBridge checks URLs against "
        "official domain registries and flags non-government domains claiming "
        "to be government agencies."
    ),
    "Prize lottery scam": (
        "US context: FTC lottery and sweepstakes scams cause elderly victims "
        "to lose an average of 1,000 dollars per incident. Victims are told "
        "they won a prize but must pay fees or taxes to collect. ElderBridge "
        "detects prize/lottery language combined with callback numbers and "
        "fee requests."
    ),
}


def get_us_analogy(program_name: str) -> str:
    """Return the US analogy for a given Pakistani program or scam type.

    Args:
        program_name: Name of the program or scam type (case-insensitive partial match).

    Returns:
        The US analogy text, or a default message if no match found.
    """
    name_lower = program_name.lower()
    for key, value in US_ANALOGIES.items():
        if name_lower in key.lower() or key.lower() in name_lower:
            return value
    return f"No US analogy available for '{program_name}'."
