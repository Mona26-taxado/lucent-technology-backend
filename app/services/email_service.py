import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    settings = get_settings()
    return bool(settings.SMTP_HOST and settings.SMTP_USER and (settings.SMTP_PASSWORD or "").strip())


def _send_html_email(to_email: str, subject: str, plain: str, html: str) -> None:
    settings = get_settings()
    if not smtp_configured():
        raise RuntimeError(
            "Email is not configured. Set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD in backend/.env"
        )

    from_addr = settings.SMTP_FROM or settings.SMTP_USER
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
        server.ehlo()
        if settings.SMTP_USE_TLS:
            server.starttls()
            server.ehlo()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)


def _email_shell(title: str, body_html: str, footer_note: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#eef2f7;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#eef2f7;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 24px rgba(11,42,91,0.12);">
          <tr>
            <td style="background:linear-gradient(135deg,#0b2a5b 0%,#1a4b96 100%);padding:28px 32px;text-align:center;">
              <p style="margin:0;color:#f1c40f;font-size:11px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;">Lucent Technology</p>
              <h1 style="margin:10px 0 0;color:#ffffff;font-size:22px;font-weight:800;line-height:1.3;">Certificate Printing System</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:32px;">
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="padding:0 32px 28px;">
              <p style="margin:0;color:#94a3b8;font-size:12px;line-height:1.6;text-align:center;">
                {footer_note}
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def send_login_otp_email(to_email: str, otp_code: str) -> None:
    settings = get_settings()
    body = f"""
      <p style="margin:0 0 12px;color:#334155;font-size:15px;">Hello,</p>
      <p style="margin:0 0 20px;color:#334155;font-size:15px;line-height:1.6;">
        Use the one-time password below to sign in to your Lucent Technology account.
      </p>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:24px;text-align:center;margin:0 0 20px;">
        <p style="margin:0 0 8px;color:#64748b;font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">Login OTP</p>
        <p style="margin:0;font-size:34px;font-weight:800;letter-spacing:10px;color:#0b2a5b;">{otp_code}</p>
      </div>
      <p style="margin:0;color:#64748b;font-size:13px;line-height:1.6;">
        This code expires in <strong>{settings.OTP_EXPIRE_MINUTES} minutes</strong>.
        Do not share it with anyone.
      </p>
    """
    html = _email_shell(
        "Login OTP",
        body,
        "If you did not request this code, you can safely ignore this email.",
    )
    plain = (
        f"Your Lucent Technology login OTP is: {otp_code}\n\n"
        f"Expires in {settings.OTP_EXPIRE_MINUTES} minutes.\n"
    )
    try:
        _send_html_email(to_email, "Lucent Technology — Login OTP", plain, html)
        logger.info("Login OTP sent to %s", to_email)
    except Exception as exc:
        logger.exception("Failed to send login OTP email")
        raise RuntimeError(f"Failed to send OTP email: {exc}") from exc


def send_password_reset_email(to_email: str, otp_code: str) -> None:
    settings = get_settings()
    body = f"""
      <p style="margin:0 0 12px;color:#334155;font-size:15px;">Hello,</p>
      <p style="margin:0 0 20px;color:#334155;font-size:15px;line-height:1.6;">
        We received a request to reset the password for your Lucent Technology account.
        Enter the verification code below on the reset password page.
      </p>
      <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;padding:24px;text-align:center;margin:0 0 20px;">
        <p style="margin:0 0 8px;color:#c2410c;font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">Password Reset Code</p>
        <p style="margin:0;font-size:34px;font-weight:800;letter-spacing:10px;color:#0b2a5b;">{otp_code}</p>
      </div>
      <p style="margin:0 0 12px;color:#64748b;font-size:13px;line-height:1.6;">
        This code expires in <strong>{settings.OTP_EXPIRE_MINUTES} minutes</strong>.
      </p>
      <p style="margin:0;color:#64748b;font-size:13px;line-height:1.6;">
        If you did not request a password reset, please ignore this email. Your password will remain unchanged.
      </p>
    """
    html = _email_shell(
        "Password Reset",
        body,
        "Lucent Technology · Certificate Printing System · Secure account notification",
    )
    plain = (
        f"Your Lucent Technology password reset code is: {otp_code}\n\n"
        f"Expires in {settings.OTP_EXPIRE_MINUTES} minutes.\n"
        "If you did not request this, ignore this email.\n"
    )
    try:
        _send_html_email(to_email, "Lucent Technology — Password Reset", plain, html)
        logger.info("Password reset email sent to %s", to_email)
    except Exception as exc:
        logger.exception("Failed to send password reset email")
        raise RuntimeError(f"Failed to send password reset email: {exc}") from exc
