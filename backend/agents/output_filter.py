"""
output_filter.py — ElderBridge GuardianOS
Filters sensitive data from AI-generated responses before they reach the user.
"""
import re
from typing import Tuple

OUTPUT_FILTERS: list[Tuple[re.Pattern, str]] = [
    # Redaction artifact cleanup — internal markers must never reach the user
    (re.compile(r"\[OTP\]"), "a verification code"),
    (re.compile(r"\[REDACTED_OTP\]"), "a verification code"),
    (re.compile(r"\[redacted_otp\]"), "a verification code"),
    (re.compile(r"\[REDACTED_CODE\]"), "a code"),
    (re.compile(r"\[REDACTED_CNIC\]"), "an ID number"),
    (re.compile(r"\[redacted_cnic\]"), "an ID number"),
    (re.compile(r"\[REDACTED_CARD\]"), "a card number"),
    (re.compile(r"\[REDACTED_EMAIL\]"), "an email address"),
    (re.compile(r"\[REDACTED_PHONE\]"), "a phone number"),
    (re.compile(r"\[REDACTED_IBAN\]"), "an account number"),
    (re.compile(r"\[REDACTED_TOKEN\]"), "a token"),
    (re.compile(r"\[ID number hidden\]"), "an ID number"),
    (re.compile(r"\[card number hidden\]"), "a card number"),
    (re.compile(r"\[account number hidden\]"), "an account number"),
    (re.compile(r"\[REDACTED[^\]]*\]"), "private information"),
    # Sensitive data in AI output
    (re.compile(r"(?i)(otp|one.time.code|verification code|pin)[:\s]+\d{4,8}"), "a one-time code"),
    (re.compile(r"(?i)code is[:\s]+\d{4,8}"), "a code"),
    (re.compile(r"(?i)pin is[:\s]+\d{4,8}"), "a PIN"),
    (re.compile(r"(?i)otp is[:\s]+\d{4,8}"), "a one-time code"),
    (re.compile(r"(?i)(the|your) (otp|code|pin) is \d{4,8}"), "the code"),
    (re.compile(r"(?i)(otp|code|pin)\s+is\s+\d{4,8}"), "code"),
    (re.compile(r"(?i)(your|the) code[:\s]+\d{4,8}"), "your code"),
    (re.compile(r"\d{5}-\d{7}-\d"), "an ID number"),
    (re.compile(r"\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}"), "a card number"),
    (re.compile(r"(?i)password is[:\s]+\S+"), "your password"),
    (re.compile(r"(?i)the password[:\s]+\S+"), "the password"),
    (re.compile(r"PK\d{2}[A-Z]{4}\d{16}"), "an account number"),
    # Action-taking language suppression
    (re.compile(r"(?i)I (will|am going to|can) (click|tap|press|submit|pay|transfer|fill)"), "You should"),
    (re.compile(r"(?i)let me (click|tap|press|submit|pay|transfer)"), "You can"),
    (re.compile(r"(?i)I (have|will have) (clicked|tapped|submitted|paid|transferred)"), ""),
    (re.compile(r"(?i)on your behalf"), ""),
    (re.compile(r"(?i)automatically (click|tap|submit|pay|fill)"), ""),
]

ACTION_FORBIDDEN = [
    re.compile(r"(?i)I will (click|tap|press|submit|pay|transfer|fill) "),
    re.compile(r"(?i)let me (click|tap|press|submit|pay) "),
    re.compile(r"(?i)I (have|am) (clicking|tapping|submitting|paying|transferring)"),
    re.compile(r"(?i)(automatically|on your behalf) (click|submit|pay|transfer|fill)"),
    re.compile(r"(?i)I (transferred|paid|submitted|filled|clicked)"),
]

def filter_output(response: str) -> str:
    if not response:
        return response
    for pattern, replacement in OUTPUT_FILTERS:
        response = pattern.sub(replacement, response)
    return response.strip()

def contains_forbidden_action(response: str) -> bool:
    return any(pattern.search(response) for pattern in ACTION_FORBIDDEN)

def validate_output_safe(response: str) -> Tuple[bool, str]:
    if contains_forbidden_action(response):
        return False, "Response contains action-taking language"
    filtered = filter_output(response)
    return True, filtered
