"""In-memory OTP store for email login (single-process uvicorn is fine)."""

from __future__ import annotations

import hashlib
import secrets
import time
from threading import Lock

_lock = Lock()
# email -> { code_hash, expires_at, attempts }
_store: dict[str, dict] = {}

OTP_LENGTH = 6
OTP_TTL_SECONDS = 10 * 60
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 45


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def generate_otp(length: int = OTP_LENGTH) -> str:
    # Numeric OTP, no leading-zero issues for display (allow leading zeros)
    upper = 10**length
    return str(secrets.randbelow(upper)).zfill(length)


def can_resend(email: str) -> tuple[bool, int]:
    """Return (allowed, seconds_remaining)."""
    key = email.strip().lower()
    with _lock:
        row = _store.get(key)
        if not row:
            return True, 0
        elapsed = time.time() - row.get("sent_at", 0)
        wait = RESEND_COOLDOWN_SECONDS - int(elapsed)
        if wait > 0:
            return False, wait
        return True, 0


def save_otp(email: str, code: str, ttl_seconds: int = OTP_TTL_SECONDS) -> None:
    key = email.strip().lower()
    with _lock:
        _store[key] = {
            "code_hash": _hash_code(code),
            "expires_at": time.time() + ttl_seconds,
            "attempts": 0,
            "sent_at": time.time(),
        }


def verify_otp(email: str, code: str) -> bool:
    key = email.strip().lower()
    code = (code or "").strip()
    with _lock:
        row = _store.get(key)
        if not row:
            return False
        if time.time() > row["expires_at"]:
            _store.pop(key, None)
            return False
        if row["attempts"] >= MAX_ATTEMPTS:
            _store.pop(key, None)
            return False
        row["attempts"] += 1
        if secrets.compare_digest(row["code_hash"], _hash_code(code)):
            _store.pop(key, None)
            return True
        return False
