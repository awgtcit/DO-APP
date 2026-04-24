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
from services import email_admin_service
from services.email_service import send_email
from services.do_pdf_service import should_attach_pdf, generate_order_pdf, pdf_filename

logger = logging.getLogger(__name__)


# ── Public API ──────────────────────────────────────────────────

def send_do_status_email(
    order: dict,
    new_status: str,
    creator_first_name: str | None = None,
    reject_reason: str | None = None,
    reject_remarks: str | None = None,
    extra_cc: list[str] | None = None,
    exclude_emails: list[str] | None = None,
    run_async: bool = True,
    diagnostics: dict | None = None,
) -> bool:
    """
    Queue or send a notification email for a DO status transition.

    The SMTP send runs in a daemon thread by default so the caller
    (and the HTTP response) is not blocked.  When *run_async* is False,
    the send runs inline and the return value reflects SMTP success.

    *extra_cc* — optional list of email addresses to CC.
    *exclude_emails* — optional list of addresses that must be removed from
    TO/CC/BCC (e.g. creator and acting user).
    *diagnostics* — optional dict to capture effective recipients and
    attachment/send outcome details.
    """
    po_number = order.get("PO_Number", "")

    workflow_cfg = email_admin_service.resolve_workflow_email_for_do(
        order=order,
        new_status=new_status,
        creator_first_name=creator_first_name,
        reject_reason=reject_reason,
        reject_remarks=reject_remarks,
    )

    if workflow_cfg:
        subject = workflow_cfg.get("subject") or _build_subject(po_number, new_status)
        body = workflow_cfg.get("body") or _build_body(
            po_number,
            new_status,
            creator_first_name=creator_first_name,
            reject_reason=reject_reason,
            reject_remarks=reject_remarks,
        )
        to_recipients = workflow_cfg.get("to") or []
        configured_cc = workflow_cfg.get("cc") or []
        configured_bcc = workflow_cfg.get("bcc") or []
        include_default_attachment = bool(workflow_cfg.get("include_default_attachment"))
        configured_attachments = list(workflow_cfg.get("extra_attachments") or [])
    else:
        subject = _build_subject(po_number, new_status)
        body = _build_body(
            po_number,
            new_status,
            creator_first_name=creator_first_name,
            reject_reason=reject_reason,
            reject_remarks=reject_remarks,
        )
        to_recipients = []
        configured_cc = []
        configured_bcc = []
        include_default_attachment = False
        configured_attachments = []

    def _normalize_emails(values: list[str] | None) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for value in values or []:
            email = (value or "").strip().lower()
            if not email or email in seen:
                continue
            seen.add(email)
            normalized.append(email)
        return normalized

    excluded = set(_normalize_emails(exclude_emails))

    to_list = [e for e in _normalize_emails(list(to_recipients or [])) if e not in excluded]

    cc_candidates = _normalize_emails(list(extra_cc or []) + list(configured_cc or []))
    cc_list = [e for e in cc_candidates if e not in excluded and e not in set(to_list)]

    bcc_candidates = _normalize_emails(list(configured_bcc or []))
    bcc_list = [e for e in bcc_candidates if e not in excluded and e not in set(to_list) and e not in set(cc_list)]

    # Generate PDF attachment (must happen here — needs Flask app context)
    attachments = list(configured_attachments)
    attach_pdf = include_default_attachment and should_attach_pdf(new_status)
    app = current_app._get_current_object() if attach_pdf else None

    send_state = {
        "workflow_config_used": bool(workflow_cfg),
        "to": list(to_list),
        "cc": list(cc_list),
        "bcc": list(bcc_list),
        "attachment_expected": bool(attach_pdf),
        "attachment_added": False,
        "attachment_name": None,
        "sent": False,
        "error": None,
    }

    if not workflow_cfg:
        send_state["error"] = "Workflow email configuration is missing or disabled for this status"

    if diagnostics is not None:
        diagnostics.clear()
        diagnostics.update(send_state)

    def _send_once() -> bool:
        local_attachments = list(attachments)
        try:
            if not workflow_cfg:
                logger.info(
                    "Skipping DO email for %s -> %s: workflow email configuration missing/disabled",
                    po_number,
                    new_status,
                )
                return False

            if not to_list and not cc_list and not bcc_list:
                send_state["error"] = (
                    f"No recipients available after filtering "
                    f"(raw_to={workflow_cfg.get('to') if workflow_cfg else 'n/a'}, "
                    f"extra_cc={extra_cc!r})"
                )
                logger.warning(
                    "Skipping DO email for %s -> %s: no recipients after filtering "
                    "(raw_to=%s extra_cc=%s)",
                    po_number,
                    new_status,
                    workflow_cfg.get("to") if workflow_cfg else "n/a",
                    extra_cc,
                )
                return False

            # PDF generation in background thread (with app context)
            if attach_pdf and app is not None:
                with app.app_context():
                    pdf_bytes = generate_order_pdf(order)
                    if pdf_bytes:
                        fname = pdf_filename(po_number)
                        local_attachments.append((fname, pdf_bytes, "pdf"))
                        send_state["attachment_added"] = True
                        send_state["attachment_name"] = fname
                        logger.info("PDF attachment ready: %s (%d bytes)", fname, len(pdf_bytes))
                    else:
                        logger.warning("PDF generation failed for %s — sending without attachment", po_number)

            sent_ok = send_email(
                to=to_list,
                subject=subject,
                body_html=body,
                cc=cc_list or None,
                bcc=bcc_list or None,
                attachments=local_attachments or None,
            )
            if not sent_ok:
                send_state["error"] = "SMTP send failed"
                return False

            send_state["sent"] = True
            logger.info("DO email sent for %s -> %s (to=%s cc=%s)", po_number, new_status, to_list, cc_list)
            return True
        except Exception:
            send_state["error"] = "SMTP send failed"
            logger.exception(
                "Background DO email failed for %s -> %s", po_number, new_status
            )
            return False
        finally:
            if diagnostics is not None:
                diagnostics.clear()
                diagnostics.update(send_state)

    if run_async:
        thread = threading.Thread(target=_send_once, daemon=True)
        thread.start()
        return True

    return _send_once()


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
