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

from services.smtp_runtime_service import get_runtime_smtp_settings

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
    smtp = get_runtime_smtp_settings()
    smtp_host = smtp.get("host") or ""
    smtp_user = smtp.get("user") or ""
    smtp_password = smtp.get("password") or ""
    smtp_port = int(smtp.get("port") or 587)
    smtp_from = smtp.get("from_email") or smtp_user
    use_tls = bool(smtp.get("use_tls", True))
    use_ssl = bool(smtp.get("use_ssl", False))

    if not smtp_host or not smtp_user:
        logger.warning("SMTP not configured — email skipped: %s (host=%r user=%r)", subject, smtp_host, smtp_user)
        return False

    logger.info("Preparing email: subject=%r  to=%s  cc=%s  bcc=%s  attachments=%d",
                subject, to, cc, bcc, len(attachments or []))

    msg = MIMEMultipart("mixed")
    msg["From"] = smtp_from
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
        logger.info("Connecting to SMTP %s:%s ...", smtp_host, smtp_port)
        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, all_recipients, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                if use_tls:
                    server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, all_recipients, msg.as_string())
        logger.info("Email sent OK: %s → %s (cc=%s)", subject, to, cc)
        return True
    except Exception as exc:
        err = str(exc)
        if "535" in err and "gmail" in smtp_host.lower():
            logger.error(
                "Email send FAILED (Gmail auth): %s — %s | Hint: use full Gmail as username and App Password",
                subject,
                err,
                exc_info=True,
            )
        else:
            logger.error("Email send FAILED: %s — %s", subject, err, exc_info=True)
        return False
