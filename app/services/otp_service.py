"""In-memory OTP store (single-process uvicorn is fine)."""

from __future__ import annotations

import hashlib
import secrets
import time
from threading import Lock

_lock = Lock()
# key -> { code_hash, expires_at, attempts, sent_at }
_store: dict[str, dict] = {}

OTP_LENGTH = 6
OTP_TTL_SECONDS = 10 * 60
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 45

PURPOSE_LOGIN = "login"
PURPOSE_PASSWORD_RESET = "password_reset"


def _store_key(email: str, purpose: str = PURPOSE_LOGIN) -> str:
    return f"{purpose}:{email.strip().lower()}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def generate_otp(length: int = OTP_LENGTH) -> str:
    upper = 10**length
    return str(secrets.randbelow(upper)).zfill(length)


def can_resend(email: str, purpose: str = PURPOSE_LOGIN) -> tuple[bool, int]:
    key = _store_key(email, purpose)
    with _lock:
        row = _store.get(key)
        if not row:
            return True, 0
        elapsed = time.time() - row.get("sent_at", 0)
        wait = RESEND_COOLDOWN_SECONDS - int(elapsed)
        if wait > 0:
            return False, wait
        return True, 0


def save_otp(email: str, code: str, ttl_seconds: int = OTP_TTL_SECONDS, purpose: str = PURPOSE_LOGIN) -> None:
    key = _store_key(email, purpose)
    with _lock:
        _store[key] = {
            "code_hash": _hash_code(code),
            "expires_at": time.time() + ttl_seconds,
            "attempts": 0,
            "sent_at": time.time(),
        }


def verify_otp(email: str, code: str, purpose: str = PURPOSE_LOGIN) -> bool:
    key = _store_key(email, purpose)
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
