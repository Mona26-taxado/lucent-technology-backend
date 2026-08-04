from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.api.deps import get_current_user
from app.models import User
from app.schemas.auth import (
    Token,
    UserOut,
    ChangePasswordRequest,
    RequestOtpRequest,
    VerifyOtpRequest,
    LoginConfigOut,
    OtpSentResponse,
)
from app.schemas.dashboard import MessageResponse
from app.services.otp_service import can_resend, generate_otp, save_otp, verify_otp
from app.services.email_service import send_login_otp_email, smtp_configured

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _allowed_login_email() -> str:
    return _normalize_email(settings.LOGIN_EMAIL or settings.DEFAULT_ADMIN_USERNAME)


def _dev_otp_mode() -> bool:
    """Local login without Gmail: DEBUG on and SMTP not set."""
    return bool(settings.DEBUG) and not smtp_configured()


def _get_or_create_login_user(db: Session) -> User:
    """Resolve the single admin user allowed to log in via OTP."""
    email = _allowed_login_email()
    user = db.query(User).filter(User.username == email).first()
    if user:
        return user

    # Migrate legacy "admin" username to login email
    legacy = db.query(User).filter(User.username == "admin").first()
    if legacy:
        legacy.username = email
        db.add(legacy)
        db.commit()
        db.refresh(legacy)
        return legacy

    user = User(
        username=email,
        password_hash=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
        full_name=settings.DEFAULT_ADMIN_FULL_NAME,
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/login-config", response_model=LoginConfigOut)
def login_config():
    return LoginConfigOut(
        login_email=settings.LOGIN_EMAIL,
        otp_length=6,
        dev_otp_mode=_dev_otp_mode(),
    )


@router.post("/request-otp", response_model=OtpSentResponse)
def request_otp(data: RequestOtpRequest, db: Session = Depends(get_db)):
    email = _normalize_email(data.email)
    allowed = _allowed_login_email()
    if email != allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This email is not authorized to sign in",
        )

    allowed_resend, wait = can_resend(email)
    if not allowed_resend:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {wait} seconds before requesting another OTP",
        )

    user = _get_or_create_login_user(db)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    code = generate_otp(6)
    save_otp(email, code, ttl_seconds=settings.OTP_EXPIRE_MINUTES * 60)

    # Local / DEBUG: no SMTP → show OTP on screen (and log)
    if _dev_otp_mode():
        print(f"\n=== LOCAL LOGIN OTP for {settings.LOGIN_EMAIL}: {code} ===\n", flush=True)
        return OtpSentResponse(
            message=f"Local mode: use OTP {code} (email not sent)",
            dev_otp=code,
        )

    try:
        send_login_otp_email(settings.LOGIN_EMAIL, code)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return OtpSentResponse(message="OTP sent to your email")

@router.post("/verify-otp", response_model=Token)
def verify_otp_login(data: VerifyOtpRequest, db: Session = Depends(get_db)):
    email = _normalize_email(data.email)
    allowed = _allowed_login_email()
    if email != allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This email is not authorized to sign in",
        )

    if not verify_otp(email, data.otp):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP",
        )

    user = _get_or_create_login_user(db)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    access_token = create_access_token(data={"sub": user.username})
    return Token(access_token=access_token)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    current_user.password_hash = get_password_hash(data.new_password)
    db.add(current_user)
    db.commit()
    return MessageResponse(message="Password changed successfully")
