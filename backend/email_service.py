import os
import logging
from typing import Dict, Any, Tuple
import resend
from fastapi import HTTPException

logger = logging.getLogger("bizops.email")

# ─── Environment Configuration ───────────────────────────────────────────────

def get_resend_api_key() -> str:
    return os.environ.get("RESEND_API_KEY", "").strip() or os.environ.get("SMTP_PASSWORD", "").strip()

def get_resend_test_recipient() -> str:
    return os.environ.get("RESEND_TEST_RECIPIENT", "").strip().lower()

def validate_testing_recipient(email_addr: str):
    """
    Enforces Resend testing restrictions when RESEND_TEST_RECIPIENT is configured.
    Rejects attempts to send OTPs to any other address with a clear, helpful message.
    """
    test_rec = get_resend_test_recipient()
    if not test_rec:
        return
    clean = (email_addr or "").strip().lower()
    if clean != test_rec:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Resend testing restriction active: Without a custom domain, OTP emails can only be delivered to your registered "
                f"Resend account Gmail address ({mask_email(test_rec)}). "
                f"Please enter your registered Gmail address or configure RESEND_TEST_RECIPIENT in .env."
            )
        )

def get_resend_from_email() -> str:
    raw = os.environ.get("RESEND_FROM_EMAIL", "").strip() or os.environ.get("RESEND_FROM", "").strip()
    if raw:
        if "<" not in raw and "@" in raw:
            return f"AI Business Operations Copilot <{raw}>"
        return raw
    # Default sandbox address for Resend testing
    return "AI Business Operations Copilot <onboarding@resend.dev>"

def mask_email(email_addr: str) -> str:
    """Mask email for secure logging (e.g., al***r@domain.com)"""
    if not email_addr or "@" not in email_addr:
        return email_addr or ""
    parts = email_addr.split("@")
    user, domain = parts[0], parts[1]
    if len(user) <= 2:
        masked_user = user[0] + "***"
    else:
        masked_user = user[:2] + "***" + user[-1]
    return f"{masked_user}@{domain}"

def is_resend_configured() -> bool:
    """Returns True if a non-empty RESEND_API_KEY is available."""
    key = get_resend_api_key()
    return bool(key and key.startswith("re_"))

def get_email_service_status() -> Dict[str, Any]:
    """
    Returns public status of the Resend email service.
    Never exposes the full API key or secret credentials.
    """
    key = get_resend_api_key()
    from_email = get_resend_from_email()
    configured = is_resend_configured()

    masked_key = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else ("Configured" if key else "Not configured")
    missing = []
    if not key:
        missing.append("RESEND_API_KEY")

    return {
        "provider": "resend",
        "configured": configured,
        "from_email": from_email,
        "api_key_status": masked_key,
        "missing_variables": missing,
        "sdk_version": getattr(resend, "__version__", "unknown")
    }

def build_otp_email_content(recipient_name: str, otp: str) -> Tuple[str, str, str]:
    """
    Builds the subject, plain-text body, and responsive HTML body
    for the 6-digit registration OTP verification email.
    """
    subject = f"Your AI BizOps Verification Code: {otp}"

    text_content = f"""Hello {recipient_name},

Thank you for registering with AI Business Operations Copilot.

Your 6-digit email verification code is: {otp}

This code will expire in 5 minutes.
For your security, never share this code with anyone.

If you did not request this verification, you can safely disregard this email.

Best regards,
The AI BizOps Team
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Verification Code</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f8fafc;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #0f172a; padding: 40px 16px;">
    <tr>
      <td align="center">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 500px; background: #1e293b; border-radius: 16px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);">
          <!-- Brand Header -->
          <tr>
            <td style="padding: 28px 28px 20px; text-align: center; border-bottom: 1px solid #334155; background: linear-gradient(135deg, rgba(79, 70, 229, 0.2), rgba(124, 58, 237, 0.2));">
              <div style="display: inline-block; width: 44px; height: 44px; line-height: 44px; background: linear-gradient(135deg, #6366f1, #8b5cf6); border-radius: 12px; margin-bottom: 10px; text-align: center;">
                <span style="font-size: 22px; color: #ffffff;">⚡</span>
              </div>
              <h1 style="margin: 0; font-size: 19px; font-weight: 700; color: #ffffff; letter-spacing: -0.02em;">AI Business Operations Copilot</h1>
              <p style="margin: 4px 0 0; font-size: 12px; color: #94a3b8;">Email OTP Verification</p>
            </td>
          </tr>
          <!-- Body Content -->
          <tr>
            <td style="padding: 28px;">
              <p style="margin: 0 0 14px; font-size: 14px; color: #e2e8f0; line-height: 1.5;">
                Hello <strong style="color: #ffffff;">{recipient_name}</strong>,
              </p>
              <p style="margin: 0 0 20px; font-size: 13px; color: #94a3b8; line-height: 1.6;">
                Thank you for creating an account. Please enter the verification code below to verify your email and activate your business operations workspace:
              </p>
              
              <!-- Monospace OTP Box -->
              <div style="background: #0f172a; border: 1px solid #4f46e5; border-radius: 12px; padding: 18px; text-align: center; margin: 20px 0;">
                <div style="font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #818cf8; text-shadow: 0 0 12px rgba(129, 140, 248, 0.4);">
                  {otp}
                </div>
              </div>

              <!-- Expiry Alert -->
              <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 8px; padding: 10px 14px; text-align: center; margin: 16px 0;">
                <p style="margin: 0; font-size: 12px; color: #fca5a5;">
                  ⏱️ <strong>Valid for 5 minutes</strong> • Never share this code with anyone.
                </p>
              </div>

              <p style="margin: 20px 0 0; font-size: 11px; color: #64748b; line-height: 1.5;">
                If you did not initiate this registration, please disregard this email. Your business workspace will not be created without verification.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 16px 28px; background: #0f172a; border-top: 1px solid #334155; text-align: center;">
              <p style="margin: 0; font-size: 11px; color: #64748b;">
                © 2026 AI Business Operations Copilot. Powered by Resend.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    return subject, text_content, html_content

def send_resend_otp_email(to_email: str, recipient_name: str, otp: str) -> Dict[str, Any]:
    """
    Sends the 6-digit OTP email using the official Resend Python SDK.
    Never logs the OTP or the API key.
    Properly handles Resend API errors and ensures an email ID is returned.
    """
    api_key = get_resend_api_key()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Resend email delivery is not configured. Please set SMTP_PASSWORD (or RESEND_API_KEY) in .env."
        )

    # Validate testing recipient restriction if active
    validate_testing_recipient(to_email)

    resend.api_key = api_key
    from_email = get_resend_from_email()
    subject, text_content, html_content = build_otp_email_content(recipient_name, otp)

    params: resend.Emails.SendParams = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "html": html_content,
        "text": text_content,
    }

    try:
        response = resend.Emails.send(params)
    except Exception as exc:
        err_str = str(exc)
        logger.error("Resend API error sending to %s: %s", mask_email(to_email), err_str)
        # Check for rate limiting
        if "rate_limit" in err_str.lower() or "too many requests" in err_str.lower():
            raise HTTPException(
                status_code=429,
                detail="Resend rate limit exceeded. Please wait a moment and try again."
            )
        # Check for invalid key
        if "api_key" in err_str.lower() or "unauthorized" in err_str.lower():
            raise HTTPException(
                status_code=502,
                detail="Resend API key is invalid or unauthorized. Please verify RESEND_API_KEY in .env."
            )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to deliver verification email via Resend: {err_str}."
        )

    # In Resend Python SDK, response is typically a dict or object with an 'id' attribute
    email_id = None
    if isinstance(response, dict):
        email_id = response.get("id")
    elif hasattr(response, "id"):
        email_id = getattr(response, "id")

    if not email_id:
        logger.error("Resend API call did not return an email id for %s. Response: %s", mask_email(to_email), type(response))
        raise HTTPException(
            status_code=502,
            detail="Resend service did not return a valid delivery ID. Email delivery unconfirmed."
        )

    logger.info("Resend OTP verification email successfully dispatched to %s (id=%s)", mask_email(to_email), email_id)
    return {
        "id": email_id,
        "status": "delivered",
        "to": to_email
    }

