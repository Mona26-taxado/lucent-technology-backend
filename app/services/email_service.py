import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    settings = get_settings()
    return bool(settings.SMTP_HOST and settings.SMTP_USER and (settings.SMTP_PASSWORD or "").strip())


def send_login_otp_email(to_email: str, otp_code: str) -> None:
    """Send OTP via SMTP. Raises RuntimeError if SMTP is not configured or send fails."""
    settings = get_settings()
    if not smtp_configured():
        raise RuntimeError(
            "Email OTP is not configured. Set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD "
            "(Gmail App Password) in backend/.env"
        )

    from_addr = settings.SMTP_FROM or settings.SMTP_USER
    msg = EmailMessage()
    msg["Subject"] = "Lucent Technology — Login OTP"
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.set_content(
        f"Your Lucent Technology login OTP is: {otp_code}\n\n"
        f"This code expires in {settings.OTP_EXPIRE_MINUTES} minutes.\n"
        "If you did not request this, ignore this email.\n"
    )
    msg.add_alternative(
        f"""
        <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;">
          <h2 style="color:#0b2a5b;margin:0 0 12px;">Lucent Technology</h2>
          <p style="color:#334155;margin:0 0 16px;">Your login OTP is:</p>
          <p style="font-size:32px;letter-spacing:8px;font-weight:700;color:#0b2a5b;margin:0 0 16px;">
            {otp_code}
          </p>
          <p style="color:#64748b;font-size:13px;margin:0;">
            Expires in {settings.OTP_EXPIRE_MINUTES} minutes. Do not share this code.
          </p>
        </div>
        """,
        subtype="html",
    )

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
            server.ehlo()
            if settings.SMTP_USE_TLS:
                server.starttls()
                server.ehlo()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Login OTP sent to %s", to_email)
    except Exception as exc:
        logger.exception("Failed to send OTP email")
        raise RuntimeError(f"Failed to send OTP email: {exc}") from exc
