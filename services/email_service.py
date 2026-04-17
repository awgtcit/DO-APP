"""
Email service — shared email sending via SMTP (Office 365).
Replaces legacy PHPMailer calls across all modules.

Usage:
    from services.email_service import send_email
    send_email(
        to=["user@example.com"],
        subject="Order Submitted",
        body_html="<p>Your order has been submitted.</p>",
    )
"""

import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import Config

logger = logging.getLogger(__name__)


def send_email(
    to: list[str],
    subject: str,
    body_html: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> bool:
    """
    Send an HTML email via SMTP.

    *attachments* — optional list of ``(filename, content_bytes, mime_subtype)``
    tuples.  Example: ``[("order.pdf", pdf_bytes, "pdf")]``.

    Returns True on success, False on failure (never raises).
    """
    if not Config.SMTP_HOST or not Config.SMTP_USER:
        logger.warning("SMTP not configured — email skipped: %s (host=%r user=%r)", subject, Config.SMTP_HOST, Config.SMTP_USER)
        return False

    logger.info("Preparing email: subject=%r  to=%s  cc=%s  bcc=%s  attachments=%d",
                subject, to, cc, bcc, len(attachments or []))

    msg = MIMEMultipart("mixed")
    msg["From"] = Config.SMTP_USER
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject

    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)

    msg.attach(MIMEText(body_html, "html"))

    # Attach files (PDF, etc.)
    for filename, content, mime_sub in (attachments or []):
        part = MIMEApplication(content, _subtype=mime_sub)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    all_recipients = list(to) + (cc or []) + (bcc or [])

    try:
        logger.info("Connecting to SMTP %s:%s ...", Config.SMTP_HOST, Config.SMTP_PORT)
        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            server.sendmail(Config.SMTP_USER, all_recipients, msg.as_string())
        logger.info("Email sent OK: %s → %s (cc=%s)", subject, to, cc)
        return True
    except Exception as exc:
        logger.error("Email send FAILED: %s — %s", subject, exc, exc_info=True)
        return False
