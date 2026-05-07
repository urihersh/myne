import hmac
import secrets
import time
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from database import get_settings

router = APIRouter(tags=["auth"])

SESSION_TTL = 86400        # 24 hours
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 60

# token -> expiry timestamp
_sessions: dict[str, float] = {}
# ip -> (attempt_count, window_start)
_rate_limit: dict[str, tuple[int, float]] = {}


def _cleanup_sessions():
    now = time.time()
    for token in [t for t, exp in _sessions.items() if exp < now]:
        del _sessions[token]


def is_valid_session(token: str) -> bool:
    exp = _sessions.get(token)
    if exp is None:
        return False
    if time.time() > exp:
        del _sessions[token]
        return False
    return True


def _check_rate_limit(ip: str) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds)."""
    now = time.time()
    count, window_start = _rate_limit.get(ip, (0, now))
    if now - window_start > LOCKOUT_SECONDS:
        _rate_limit[ip] = (0, now)
        return True, 0
    if count >= MAX_ATTEMPTS:
        return False, int(LOCKOUT_SECONDS - (now - window_start))
    return True, 0


def _record_failed_attempt(ip: str) -> int:
    """Record a failed attempt. Return remaining attempts."""
    now = time.time()
    count, window_start = _rate_limit.get(ip, (0, now))
    if now - window_start > LOCKOUT_SECONDS:
        count, window_start = 0, now
    count += 1
    _rate_limit[ip] = (count, window_start)
    return max(MAX_ATTEMPTS - count, 0)


@router.get("/status")
async def auth_status(request: Request):
    s = get_settings()
    pin_enabled = s.get("pin_enabled") == "true"
    if not pin_enabled:
        return {"pin_enabled": False, "authenticated": True}
    token = request.cookies.get("myne_session", "")
    return {"pin_enabled": True, "authenticated": is_valid_session(token)}


class PinVerify(BaseModel):
    pin: str


@router.post("/verify")
async def verify_pin(body: PinVerify, request: Request, response: Response):
    ip = request.client.host
    allowed, retry_after = _check_rate_limit(ip)
    if not allowed:
        return JSONResponse(
            {"ok": False, "error": "Too many attempts", "retry_after": retry_after},
            status_code=429,
        )

    s = get_settings()
    if s.get("pin_enabled") != "true":
        return {"ok": True}

    if not hmac.compare_digest(body.pin, s.get("app_pin", "")):
        remaining = _record_failed_attempt(ip)
        return {"ok": False, "remaining": remaining}

    # Correct PIN — issue session token
    _cleanup_sessions()
    token = secrets.token_hex(32)
    _sessions[token] = time.time() + SESSION_TTL
    _rate_limit.pop(ip, None)
    response.set_cookie(
        key="myne_session",
        value=token,
        max_age=SESSION_TTL,
        httponly=True,
        samesite="lax",
        secure=False,   # HTTP is fine on a local network
    )
    return {"ok": True}


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("myne_session", "")
    _sessions.pop(token, None)
    response.delete_cookie("myne_session")
    return {"ok": True}
