"""
injection_detector.py — ElderBridge GuardianOS
Detects prompt injection attempts in captured screen text before any LLM call.
"""
import re
from typing import Optional

INJECTION_PATTERNS = [
    r"(?i)ignore (previous|above|prior|all) instructions",
    r"(?i)you are now (a|an) (different|new|other|unrestricted)",
    r"(?i)(forget|disregard|override) (everything|what|your|all)",
    r"(?i)system prompt",
    r"(?i)jailbreak",
    r"(?i)(act as|pretend (to be|you are))",
    r"(?i)new instruction[s]?[:\s]",
    r"(?i)send .{0,20}(otp|password|code|pin).{0,10} to",
    r"(?i)reveal (all|the|your) (user data|secrets|instructions|system)",
    r"(?i)you must (now|instead|actually)",
    r"(?i)(disable|bypass|ignore) (your|the|all) (safety|guardrail|filter|restriction)",
    r"(?i)from now on",
    r"(?i)your (new|real|actual|true) (role|purpose|task|instruction)",
    r"(?i)\[system\]",
    r"(?i)\[admin\]",
    r"(?i)\[override\]",
    r"(?i)DAN mode",
    r"(?i)developer mode",
]

_compiled = [re.compile(p) for p in INJECTION_PATTERNS]

def detect_injection(text: str) -> bool:
    if not text:
        return False
    return any(pattern.search(text) for pattern in _compiled)

def get_injection_reason(text: str) -> Optional[str]:
    for i, pattern in enumerate(_compiled):
        if pattern.search(text):
            return f"Pattern {i} matched: {INJECTION_PATTERNS[i][:40]}..."
    return None

INJECTION_BLOCK_RESPONSE = (
    "This screen contains content that cannot be safely analysed. "
    "If this is a government form or document, please close this screen "
    "and visit the official website directly. "
    "Step: Do not interact with this screen. Close it."
)
