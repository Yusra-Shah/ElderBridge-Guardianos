"""
secure_logger.py — ElderBridge GuardianOS
Filters PII from all log output before it is written anywhere.
"""
import logging
import re
from typing import List, Tuple

PII_REDACTIONS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)(otp|code|pin|verify)[:\s]+\d{4,8}"), r"\1: [REDACTED_CODE]"),
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "[REDACTED_EMAIL]"),
    (re.compile(r"(\+92|0092|0)[\s\-]?3\d{2}[\s\-]?\d{7}"), "[REDACTED_PHONE]"),
    (re.compile(r"\d{5}-\d{7}-\d"), "[REDACTED_CNIC]"),
    (re.compile(r"\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}"), "[REDACTED_CARD]"),
    (re.compile(r"PK\d{2}[A-Z]{4}\d{16}"), "[REDACTED_IBAN]"),
    (re.compile(r"(?i)password[=:\s]+\S+"), "password=[REDACTED]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]+"), "Bearer [REDACTED_TOKEN]"),
]

class SecurePIIFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pattern, replacement in PII_REDACTIONS:
            msg = pattern.sub(replacement, msg)
        record.msg = msg
        record.args = ()
        if record.exc_text:
            for pattern, replacement in PII_REDACTIONS:
                record.exc_text = pattern.sub(replacement, record.exc_text)
        return True

def setup_secure_logging(level: int = logging.INFO) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in root_logger.handlers[:]:
        handler.addFilter(SecurePIIFilter())
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        handler.addFilter(SecurePIIFilter())
        root_logger.addHandler(handler)
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"]:
        lgr = logging.getLogger(logger_name)
        for handler in lgr.handlers:
            handler.addFilter(SecurePIIFilter())
    logging.info("[SECURITY] Secure logging initialised — PII filter active")
