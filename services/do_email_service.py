"""
Delivery Order email notification service.

Sends HTML email notifications when DO status changes.
Replicates the legacy SalesOrderMail.php behaviour using the
shared email_service.send_email helper.

Email sends run in a background thread so the HTTP response is
not blocked by the SMTP handshake (which can take 15+ seconds).
"""

import logging
import threading
from flask import url_for, request, current_app
from services.email_service import send_email
from services.do_pdf_service import should_attach_pdf, generate_order_pdf, pdf_filename

logger = logging.getLogger(__name__)

# ── Recipient lists (matching legacy hardcoded addresses) ───────

# Primary recipient for ALL DO status emails
DO_PRIMARY_TO = ["purchaseorder@alwahdania.com"]

# BCC — admin / IT notification copies (matches legacy SalesOrderMail.php)
DO_BCC = [
    "vivan_it@universaltobacco.ae",
    "ajoy@alwahdania.com",
]


# ── Public API ──────────────────────────────────────────────────

def send_do_status_email(
    order: dict,
    new_status: str,
    creator_first_name: str | None = None,
    reject_reason: str | None = None,
    reject_remarks: str | None = None,
    extra_cc: list[str] | None = None,
) -> bool:
    """
    Queue a notification email for a DO status transition.

    The actual SMTP send runs in a daemon thread so the caller
    (and the HTTP response) is not blocked.  Returns True immediately;
    any SMTP failures are logged but do not propagate.

    *extra_cc* — optional list of email addresses to CC (e.g. the order
    creator and/or the user performing the action).
    """
    po_number = order.get("PO_Number", "")

    subject = _build_subject(po_number, new_status)
    body = _build_body(
        po_number,
        new_status,
        creator_first_name=creator_first_name,
        reject_reason=reject_reason,
        reject_remarks=reject_remarks,
    )

    # Deduplicate and filter out empty / primary-TO addresses for CC
    cc_list = list({
        e.strip().lower()
        for e in (extra_cc or [])
        if e and e.strip() and e.strip().lower() not in
           {a.lower() for a in DO_PRIMARY_TO}
    })

    # Generate PDF attachment (must happen here — needs Flask app context)
    attachments = None
    attach_pdf = should_attach_pdf(new_status)
    app = current_app._get_current_object() if attach_pdf else None

    def _send():
        try:
            # PDF generation in background thread (with app context)
            nonlocal attachments
            if attach_pdf and app is not None:
                with app.app_context():
                    pdf_bytes = generate_order_pdf(order)
                    if pdf_bytes:
                        fname = pdf_filename(po_number)
                        attachments = [(fname, pdf_bytes, "pdf")]
                        logger.info("PDF attachment ready: %s (%d bytes)", fname, len(pdf_bytes))
                    else:
                        logger.warning("PDF generation failed for %s — sending without attachment", po_number)

            send_email(
                to=DO_PRIMARY_TO,
                subject=subject,
                body_html=body,
                cc=cc_list or None,
                bcc=DO_BCC,
                attachments=attachments,
            )
            logger.info("DO email sent for %s -> %s (cc=%s)", po_number, new_status, cc_list)
        except Exception:
            logger.exception(
                "Background DO email failed for %s -> %s", po_number, new_status
            )

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()
    return True


# ── Subject ─────────────────────────────────────────────────────

def _build_subject(po_number: str, new_status: str) -> str:
    """Return the email subject matching legacy format."""
    status_map = {
        "SUBMITTED":       f"Order # {po_number} is Placed",
        "CONFIRMED":       f"Order # {po_number} is Confirmed",
        "REJECTED":        f"Order # {po_number} is Rejected",
        "PRICE AGREED":    f"Order # {po_number} Price Agreed",
        "NEED ATTACHMENT": f"Order # {po_number} Need Attachment",
        "CANCELLED":       f"Order # {po_number} is Cancelled",
    }
    return status_map.get(new_status, f"Order # {po_number} — {new_status}")


# ── Body ────────────────────────────────────────────────────────

def _build_body(
    po_number: str,
    new_status: str,
    creator_first_name: str | None = None,
    reject_reason: str | None = None,
    reject_remarks: str | None = None,
) -> str:
    """
    Build the HTML body matching the legacy SalesOrderMail.php format.
    """
    try:
        detail_link = request.host_url.rstrip("/") + url_for(
            "delivery_orders.order_list"
        )
    except RuntimeError:
        detail_link = "#"

    greeting = (
        f"Dear {creator_first_name},"
        if creator_first_name
        else "Dear User,"
    )

    action_text = _STATUS_ACTION_TEXT.get(new_status, f"status changed to {new_status}")

    # Reject / Need-Attachment may carry reason + remarks
    reason_block = ""
    if reject_reason or reject_remarks:
        parts = []
        if reject_reason:
            parts.append(f"<strong>Reason:</strong> {reject_reason}")
        if reject_remarks:
            parts.append(f"<strong>Remarks:</strong> {reject_remarks}")
        reason_block = "<br>".join(parts) + "<br><br>"

    return f"""\
<html>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#333;">
<p>{greeting}</p>

<p>This is to notify you that the order # <strong>{po_number}</strong>
has been {action_text}.</p>

{reason_block}

<p>You would be notified when there is a change on the status of the order.</p>

<p>Please click on the link below to see the order in detail:<br>
<a href="{detail_link}">{detail_link}</a></p>

<p>Best Regards,<br>Ahlaan</p>
</body>
</html>"""


_STATUS_ACTION_TEXT = {
    "SUBMITTED":       "placed (submitted)",
    "CONFIRMED":       "confirmed",
    "REJECTED":        "rejected",
    "PRICE AGREED":    "accepted — Price Agreed by finance",
    "NEED ATTACHMENT": "accepted but approved attachment is requested by finance",
    "CANCELLED":       "cancelled",
}
