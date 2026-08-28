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
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.schemas.dashboard import MessageResponse
from app.services.otp_service import (
    can_resend,
    generate_otp,
    save_otp,
    verify_otp,
    PURPOSE_PASSWORD_RESET,
)
from app.services.email_service import send_login_otp_email, send_password_reset_email, smtp_configured

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _dev_otp_mode() -> bool:
    """Local login without Gmail: DEBUG on and SMTP not set."""
    return bool(settings.DEBUG) and not smtp_configured()


def _find_user_by_email(db: Session, email: str) -> User | None:
    """Match login email against username (case-insensitive)."""
    email = _normalize_email(email)
    users = db.query(User).all()
    for user in users:
        if _normalize_email(user.username) == email:
            return user
    return None


def _authenticate_user(db: Session, email: str, password: str) -> User:
    user = _find_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")
    return user


@router.get("/login-config", response_model=LoginConfigOut)
def login_config():
    return LoginConfigOut(
        otp_length=6,
        dev_otp_mode=_dev_otp_mode(),
    )


@router.post("/request-otp", response_model=OtpSentResponse)
def request_otp(data: RequestOtpRequest, db: Session = Depends(get_db)):
    email = _normalize_email(data.email)
    if not email or not data.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required",
        )

    user = _authenticate_user(db, email, data.password)

    allowed_resend, wait = can_resend(email)
    if not allowed_resend:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {wait} seconds before requesting another OTP",
        )

    code = generate_otp(6)
    save_otp(email, code, ttl_seconds=settings.OTP_EXPIRE_MINUTES * 60)

    # Local / DEBUG: no SMTP → show OTP on screen (and log)
    if _dev_otp_mode():
        print(f"\n=== LOCAL LOGIN OTP for {email}: {code} ===\n", flush=True)
        return OtpSentResponse(
            message=f"Local mode: use OTP {code} (email not sent)",
            dev_otp=code,
        )

    try:
        send_login_otp_email(user.username if "@" in user.username else email, code)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return OtpSentResponse(message="OTP sent to your email")


@router.post("/verify-otp", response_model=Token)
def verify_otp_login(data: VerifyOtpRequest, db: Session = Depends(get_db)):
    email = _normalize_email(data.email)
    if not verify_otp(email, data.otp):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP",
        )

    user = _find_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    access_token = create_access_token(data={"sub": user.username})
    return Token(access_token=access_token)


@router.post("/forgot-password", response_model=OtpSentResponse)
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = _normalize_email(data.email)
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")

    # Always respond the same way (do not reveal whether account exists)
    generic_ok = OtpSentResponse(
        message="If this email is registered, a password reset code has been sent.",
    )

    user = _find_user_by_email(db, email)
    if not user or not user.is_active:
        return generic_ok

    allowed_resend, wait = can_resend(email, purpose=PURPOSE_PASSWORD_RESET)
    if not allowed_resend:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {wait} seconds before requesting another code",
        )

    code = generate_otp(6)
    save_otp(email, code, ttl_seconds=settings.OTP_EXPIRE_MINUTES * 60, purpose=PURPOSE_PASSWORD_RESET)

    if _dev_otp_mode():
        print(f"\n=== PASSWORD RESET OTP for {email}: {code} ===\n", flush=True)
        return OtpSentResponse(
            message="If this email is registered, a password reset code has been sent.",
            dev_otp=code,
        )

    try:
        send_password_reset_email(user.username if "@" in user.username else email, code)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return generic_ok


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    email = _normalize_email(data.email)
    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

    if not verify_otp(email, data.otp, purpose=PURPOSE_PASSWORD_RESET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired reset code",
        )

    user = _find_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    user.password_hash = get_password_hash(data.new_password)
    db.add(user)
    db.commit()
    return MessageResponse(message="Password reset successfully. You can now sign in with your new password.")


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
