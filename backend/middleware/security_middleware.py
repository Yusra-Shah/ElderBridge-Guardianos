"""
security_middleware.py — ElderBridge GuardianOS
Rate limiting and replay protection via nonce and timestamp.
"""
import time
import logging
from collections import defaultdict
from threading import Lock
from typing import Optional
from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)

_seen_nonces: dict = {}
_nonce_lock = Lock()
_rate_counters: dict = defaultdict(list)
_rate_lock = Lock()

MAX_REQUEST_AGE_SECONDS = 300
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 30

def validate_replay_protection(nonce: Optional[str], timestamp_ms: Optional[str]) -> None:
    if not nonce or not timestamp_ms:
        raise HTTPException(status_code=400, detail="Missing security headers X-Nonce and X-Timestamp")
    try:
        ts = int(timestamp_ms)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid X-Timestamp format")
    age_seconds = abs(time.time() - ts / 1000)
    if age_seconds > MAX_REQUEST_AGE_SECONDS:
        raise HTTPException(status_code=400, detail=f"Request expired: {int(age_seconds)}s old")
    with _nonce_lock:
        if nonce in _seen_nonces:
            logger.warning("[SECURITY] Duplicate nonce — replay attempt blocked")
            raise HTTPException(status_code=400, detail="Duplicate request")
        _seen_nonces[nonce] = time.time()

def check_rate_limit(client_ip: str, endpoint: str = "default") -> None:
    key = f"{client_ip}:{endpoint}"
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    with _rate_lock:
        _rate_counters[key] = [t for t in _rate_counters[key] if t > window_start]
        if len(_rate_counters[key]) >= RATE_LIMIT_MAX_REQUESTS:
            logger.warning(f"[SECURITY] Rate limit exceeded for {client_ip}")
            raise HTTPException(status_code=429, detail="Too many requests")
        _rate_counters[key].append(now)

def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
