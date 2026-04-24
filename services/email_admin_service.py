"""Business logic for SMTP and workflow-specific email configuration."""

import logging
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from flask import current_app, has_request_context, url_for
from werkzeug.utils import secure_filename

from audit.logger import log_activity
from repos import admin_settings_repo
from repos import email_admin_repo as repo
from rules.email_config_rules import validate_smtp_payload, validate_workflow_email_payload
from utils.secret_crypto import decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)

WORKFLOW_EMAIL_MODULES = {
    "delivery_orders": "Delivery Orders",
}

PLACEHOLDER_KEYS = {
    "do_number",
    "customer_name",
    "date",
    "status",
    "created_by",
    "approved_by",
    "order_link",
    "reject_reason",
    "reject_remarks",
}


_DO_DEFAULT_TEMPLATES = {
    "SUBMITTED": (
        "Order # {{do_number}} is Placed",
        """<html><body style='font-family:Arial,sans-serif;font-size:14px;color:#333;'>
<p>Dear {{created_by}},</p>
<p>Your order <strong>{{do_number}}</strong> for <strong>{{customer_name}}</strong> has been submitted.</p>
<p>You will be notified when there is a change on the status of the order.</p>
<p><a href='{{order_link}}'>{{order_link}}</a></p>
<p>Best Regards,<br>Ahlaan</p>
</body></html>""",
    ),
    "CONFIRMED": (
        "Order # {{do_number}} is Confirmed",
        """<html><body style='font-family:Arial,sans-serif;font-size:14px;color:#333;'>
<p>Dear {{created_by}},</p>
<p>This is to notify you that order <strong>{{do_number}}</strong> for <strong>{{customer_name}}</strong> has been confirmed.</p>
<p>You will be notified when there is a change on the status of the order.</p>
<p><a href='{{order_link}}'>{{order_link}}</a></p>
<p>Best Regards,<br>Ahlaan</p>
</body></html>""",
    ),
    "REJECTED": (
        "Order # {{do_number}} is Rejected",
        """<html><body style='font-family:Arial,sans-serif;font-size:14px;color:#333;'>
<p>Dear {{created_by}},</p>
<p>Order <strong>{{do_number}}</strong> has been rejected.</p>
<p>Reason: {{reject_reason}}</p>
<p>Remarks: {{reject_remarks}}</p>
<p><a href='{{order_link}}'>{{order_link}}</a></p>
<p>Best Regards,<br>Ahlaan</p>
</body></html>""",
    ),
    "PRICE AGREED": (
        "Order # {{do_number}} Price Agreed",
        """<html><body style='font-family:Arial,sans-serif;font-size:14px;color:#333;'>
<p>Dear {{created_by}},</p>
<p>Order <strong>{{do_number}}</strong> has been accepted — Price Agreed by finance.</p>
<p><a href='{{order_link}}'>{{order_link}}</a></p>
<p>Best Regards,<br>Ahlaan</p>
</body></html>""",
    ),
    "NEED ATTACHMENT": (
        "Order # {{do_number}} — Need Attachment",
        """<html><body style='font-family:Arial,sans-serif;font-size:14px;color:#333;'>
<p>Dear {{created_by}},</p>
<p>Order <strong>{{do_number}}</strong> has been accepted but an approved attachment is required by finance.</p>
<p><a href='{{order_link}}'>{{order_link}}</a></p>
<p>Best Regards,<br>Ahlaan</p>
</body></html>""",
    ),
    "CANCELLED": (
        "Order # {{do_number}} is Cancelled",
        """<html><body style='font-family:Arial,sans-serif;font-size:14px;color:#333;'>
<p>Dear {{created_by}},</p>
<p>Order <strong>{{do_number}}</strong> has been cancelled.</p>
<p><a href='{{order_link}}'>{{order_link}}</a></p>
<p>Best Regards,<br>Ahlaan</p>
</body></html>""",
    ),
}


def _split_csv(values: str) -> list[str]:
    return [v.strip() for v in (values or "").split(",") if v.strip()]


def ensure_default_do_confirmation_config(actor_emp_id: int = 0) -> None:
    """Idempotently seed default email templates for all DO statuses."""
    for status_key, (subject, body) in _DO_DEFAULT_TEMPLATES.items():
        setting_id = repo.ensure_default_workflow_email_setting(
            module_key="delivery_orders",
            status_key=status_key,
            subject_template=subject,
            body_template=body,
            include_default_attachment=True,
            actor_emp_id=int(actor_emp_id or 0),
        )
        logger.debug("Seeded DO email config %s id=%s", status_key, setting_id)


def _coerce_ids(values: list[str]) -> list[int]:
    result: list[int] = []
    for value in values:
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            continue
    return result


def get_smtp_configs() -> list[dict]:
    rows = repo.get_smtp_configs()
    for row in rows:
        row["smtp_password_encrypted"] = ""
    return rows


def get_active_smtp_runtime() -> dict | None:
    cfg = repo.get_active_smtp_config()
    if not cfg:
        return None
    runtime = dict(cfg)
    runtime["smtp_password"] = decrypt_secret(cfg.get("smtp_password_encrypted") or "")
    return runtime


def save_smtp_config(form: dict, actor_emp_id: int) -> tuple[bool, list[str], int | None]:
    data = {
        "id": form.get("id") or 0,
        "smtp_host": (form.get("smtp_host") or "").strip(),
        "smtp_port": form.get("smtp_port") or "587",
        "smtp_username": (form.get("smtp_username") or "").strip(),
        "sender_email": (form.get("sender_email") or "").strip(),
        "sender_name": (form.get("sender_name") or "").strip(),
        "use_tls": form.get("use_tls") == "1",
        "use_ssl": form.get("use_ssl") == "1",
        "is_active": form.get("is_active") == "1",
        "confirmation_subject": (form.get("confirmation_subject") or "").strip() or "SMTP Configuration Saved Successfully",
        "confirmation_body": (form.get("confirmation_body") or "").strip(),
    }

    errors = validate_smtp_payload(data)
    if errors:
        return False, errors, None

    password = (form.get("smtp_password") or "").strip()
    if not password and int(data["id"] or 0):
        existing = next((x for x in repo.get_smtp_configs() if int(x["id"]) == int(data["id"])), None)
        password = decrypt_secret(existing.get("smtp_password_encrypted") or "") if existing else ""

    if not password:
        return False, ["SMTP Password is required."], None

    data["smtp_port"] = int(data["smtp_port"])
    data["smtp_password_encrypted"] = encrypt_secret(password)

    config_id = repo.save_smtp_config(data, actor_emp_id)
    log_activity(
        emp_id=actor_emp_id,
        user_name=str(actor_emp_id),
        activity_type="SMTP_CONFIG_SAVE",
        remarks=f"Saved SMTP config id={config_id} active={int(data['is_active'])}",
    )

    # Send a confirmation email using the newly saved settings (non-blocking)
    _send_smtp_save_confirmation(data, password)

    return True, [], config_id



def _send_smtp_save_confirmation(cfg: dict, plain_password: str) -> None:
    """Send a confirmation email to the sender address after SMTP config is saved."""
    recipient = (cfg.get("sender_email") or cfg.get("smtp_username") or "").strip()
    if not recipient:
        return

    sender_name = (cfg.get("sender_name") or "SMTP Config").strip()
    host = cfg.get("smtp_host", "")
    port = int(cfg.get("smtp_port") or 587)
    use_ssl = bool(cfg.get("use_ssl"))
    use_tls = bool(cfg.get("use_tls"))
    security = "SSL" if use_ssl else "TLS" if use_tls else "None"

    subject = (cfg.get("confirmation_subject") or "").strip() or "SMTP Configuration Saved Successfully"
    default_body = (
        "<html><body style='font-family:Arial,sans-serif;padding:20px;'>"
        "<h2 style='color:#2d7a3a;'>SMTP Configuration Saved</h2>"
        "<p>Your SMTP settings have been saved. This email confirms they are working correctly.</p>"
        "<table style='border-collapse:collapse;width:100%;max-width:480px;'>"
        f"<tr><td style='padding:6px 12px;font-weight:bold;'>Host</td><td style='padding:6px 12px;'>{host}</td></tr>"
        f"<tr style='background:#f5f5f5;'><td style='padding:6px 12px;font-weight:bold;'>Port</td><td style='padding:6px 12px;'>{port}</td></tr>"
        f"<tr><td style='padding:6px 12px;font-weight:bold;'>Security</td><td style='padding:6px 12px;'>{security}</td></tr>"
        f"<tr style='background:#f5f5f5;'><td style='padding:6px 12px;font-weight:bold;'>Sender Name</td><td style='padding:6px 12px;'>{sender_name}</td></tr>"
        f"<tr><td style='padding:6px 12px;font-weight:bold;'>Sender Email</td><td style='padding:6px 12px;'>{recipient}</td></tr>"
        "</table>"
        "<p style='margin-top:20px;color:#555;'>If you did not make this change, please contact your system administrator.</p>"
        "</body></html>"
    )
    body_html = (cfg.get("confirmation_body") or "").strip() or default_body

    msg = MIMEMultipart("alternative")
    msg["From"] = recipient
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html"))

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                server.login(cfg["smtp_username"], plain_password)
                server.sendmail(recipient, [recipient], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                if use_tls:
                    server.starttls()
                server.login(cfg["smtp_username"], plain_password)
                server.sendmail(recipient, [recipient], msg.as_string())
        logger.info("SMTP save confirmation email sent to %s", recipient)
    except Exception as exc:
        logger.warning("Could not send SMTP save confirmation to %s: %s", recipient, exc)

def test_smtp_config(config_id: int, test_email: str, actor_emp_id: int) -> tuple[bool, str]:
    cfg = next((x for x in repo.get_smtp_configs() if int(x["id"]) == int(config_id)), None)
    if not cfg:
        return False, "SMTP config not found."

    runtime = dict(cfg)
    runtime["smtp_password"] = decrypt_secret(cfg.get("smtp_password_encrypted") or "")

    if not test_email:
        return False, "Test email is required."

    msg = MIMEMultipart("alternative")
    msg["From"] = runtime.get("sender_email") or runtime.get("smtp_username")
    msg["To"] = test_email
    msg["Subject"] = "SMTP Test Email"
    msg.attach(MIMEText("SMTP test succeeded.", "plain"))

    try:
        use_ssl = bool(runtime.get("use_ssl"))
        if use_ssl:
            with smtplib.SMTP_SSL(runtime["smtp_host"], int(runtime["smtp_port"]), timeout=15) as server:
                server.login(runtime["smtp_username"], runtime["smtp_password"])
                server.sendmail(msg["From"], [test_email], msg.as_string())
        else:
            with smtplib.SMTP(runtime["smtp_host"], int(runtime["smtp_port"]), timeout=15) as server:
                if runtime.get("use_tls"):
                    server.starttls()
                server.login(runtime["smtp_username"], runtime["smtp_password"])
                server.sendmail(msg["From"], [test_email], msg.as_string())
        repo.mark_smtp_test(int(config_id), "SUCCESS", f"Sent to {test_email}", actor_emp_id)
        log_activity(actor_emp_id, str(actor_emp_id), "SMTP_CONFIG_TEST", remarks=f"SMTP test success config={config_id} email={test_email}")
        return True, f"Test email sent to {test_email}."
    except Exception as exc:
        err = str(exc)
        if "535" in err and "gmail" in str(runtime.get("smtp_host", "")).lower():
            err = (
                f"{err}. Gmail rejected credentials. Use full Gmail address as username and a Google App Password "
                "(not your normal password). Use SMTP 587 + TLS or 465 + SSL."
            )
        repo.mark_smtp_test(int(config_id), "FAILED", err, actor_emp_id)
        log_activity(actor_emp_id, str(actor_emp_id), "SMTP_CONFIG_TEST", remarks=f"SMTP test failed config={config_id}: {err}")
        return False, f"SMTP test failed: {err}"


def _build_recipients_payload(form: dict) -> list[dict]:
    recipients: list[dict] = []
    user_bucket = (form.get("user_recipient_bucket") or "to").strip().lower()
    user_is_cc = user_bucket == "cc"
    user_is_bcc = user_bucket == "bcc"

    for uid in _coerce_ids(form.getlist("selected_user_ids")):
        recipients.append(
            {
                "recipient_type": "USER",
                "recipient_value": str(uid),
                "is_cc": user_is_cc,
                "is_bcc": user_is_bcc,
            }
        )

    for email in _split_csv(form.get("to_emails") or ""):
        recipients.append(
            {
                "recipient_type": "EMAIL",
                "recipient_value": email,
                "is_cc": False,
                "is_bcc": False,
            }
        )

    for email in _split_csv(form.get("cc_emails") or ""):
        recipients.append(
            {
                "recipient_type": "EMAIL",
                "recipient_value": email,
                "is_cc": True,
                "is_bcc": False,
            }
        )

    for email in _split_csv(form.get("bcc_emails") or ""):
        recipients.append(
            {
                "recipient_type": "EMAIL",
                "recipient_value": email,
                "is_cc": False,
                "is_bcc": True,
            }
        )

    return recipients


def save_workflow_email_setting(form, actor_emp_id: int) -> tuple[bool, list[str], int | None]:
    data = {
        "module_key": (form.get("module_key") or "delivery_orders").strip(),
        "status_key": (form.get("status_key") or "").strip().upper(),
        "is_enabled": form.get("is_enabled") == "1",
        "subject_template": (form.get("subject_template") or "").strip(),
        "body_template": (form.get("body_template") or "").strip(),
        "include_default_attachment": form.get("include_default_attachment") == "1",
        "selected_user_ids": form.getlist("selected_user_ids"),
        "to_emails": _split_csv(form.get("to_emails") or ""),
        "cc_emails": _split_csv(form.get("cc_emails") or ""),
        "bcc_emails": _split_csv(form.get("bcc_emails") or ""),
    }

    errors = validate_workflow_email_payload(data)
    if errors:
        return False, errors, None

    data["recipients"] = _build_recipients_payload(form)
    setting_id = repo.upsert_workflow_email_setting(data, actor_emp_id)

    log_activity(
        emp_id=actor_emp_id,
        user_name=str(actor_emp_id),
        activity_type="WORKFLOW_EMAIL_SAVE",
        remarks=f"Saved workflow email module={data['module_key']} status={data['status_key']} id={setting_id}",
    )
    return True, [], setting_id


def list_workflow_email_settings(module_key: str) -> list[dict]:
    return repo.get_workflow_email_settings(module_key)


def get_workflow_email_setting(module_key: str, status_key: str) -> dict | None:
    payload = repo.get_workflow_email_payload(module_key, status_key)
    return payload


def get_recipient_users() -> list[dict]:
    users = admin_settings_repo.get_all_users_full()
    result = []
    for user in users:
        email = (user.get("EmailAddress") or user.get("CredEmail") or "").strip()
        if not email:
            continue
        result.append(
            {
                "emp_id": user.get("EmpID"),
                "name": f"{(user.get('FirstName') or '').strip()} {(user.get('LastName') or '').strip()}".strip() or str(user.get("EmpID")),
                "email": email,
            }
        )
    return result


def _placeholder_context(order: dict, new_status: str, creator_first_name: str | None,
                         reject_reason: str | None, reject_remarks: str | None,
                         order_link: str) -> dict[str, str]:
    return {
        "do_number": str(order.get("PO_Number") or ""),
        "customer_name": str(order.get("bill_to_name") or order.get("Bill_To_Name") or ""),
        "date": str(order.get("Created_on") or order.get("Order_Date") or ""),
        "status": str(new_status or ""),
        "created_by": str(creator_first_name or order.get("creator_first") or ""),
        "approved_by": str(order.get("approved_by") or ""),
        "order_link": order_link,
        "reject_reason": str(reject_reason or ""),
        "reject_remarks": str(reject_remarks or ""),
    }


def render_template_text(template: str, context: dict[str, str]) -> str:
    def _replace(match: re.Match) -> str:
        key = match.group(1).strip().lower()
        return str(context.get(key, ""))

    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", _replace, template or "")


def resolve_workflow_email_for_do(
    order: dict,
    new_status: str,
    creator_first_name: str | None,
    reject_reason: str | None,
    reject_remarks: str | None,
) -> dict | None:
    setting = repo.get_workflow_email_payload("delivery_orders", new_status)
    if not setting or not setting.get("is_enabled"):
        return None

    order_link = ""
    try:
        if current_app:
            order_id = order.get("id")
            if order_id and has_request_context():
                order_link = url_for("delivery_orders.order_detail", order_id=order_id, _external=True)
    except RuntimeError:
        order_link = ""

    context = _placeholder_context(order, new_status, creator_first_name, reject_reason, reject_remarks, order_link)
    subject = render_template_text(setting.get("subject_template") or "", context)
    body = render_template_text(setting.get("body_template") or "", context)

    to_list: list[str] = []
    cc_list: list[str] = []
    bcc_list: list[str] = []

    for rec in setting.get("recipients", []):
        r_type = (rec.get("recipient_type") or "").upper()
        value = (rec.get("recipient_value") or "").strip()
        email = ""

        if r_type == "USER":
            try:
                user = admin_settings_repo.get_user_by_empid(int(value))
            except (TypeError, ValueError):
                user = None
            email = (user or {}).get("EmailAddress") or (user or {}).get("CredEmail") or ""
        elif r_type == "PLACEHOLDER":
            key = value.replace("{{", "").replace("}}", "").strip().lower()
            email = context.get(key, "")
        else:
            email = value

        email = (email or "").strip().lower()
        if not email:
            continue

        if rec.get("is_bcc"):
            bcc_list.append(email)
        elif rec.get("is_cc"):
            cc_list.append(email)
        else:
            to_list.append(email)

    # Build extra attachments from config
    extra_attachments: list[tuple[str, bytes, str]] = []
    for att in setting.get("attachments", []):
        storage_path = (att.get("storage_path") or "").strip()
        if not storage_path or not os.path.exists(storage_path):
            continue

        original_name = att.get("original_name") or att.get("file_name") or "attachment"
        ext = Path(original_name).suffix.lower().lstrip(".") or "octet-stream"

        with open(storage_path, "rb") as fh:
            content = fh.read()

        if att.get("is_editable"):
            if ext in {"txt", "html", "htm"}:
                rendered = render_template_text(content.decode("utf-8", errors="ignore"), context)
                content = rendered.encode("utf-8")
            else:
                # non-text templates cannot be safely transformed yet
                pass

        extra_attachments.append((original_name, content, ext if ext != "jpg" else "jpeg"))

    return {
        "to": sorted(set(to_list)),
        "cc": sorted(set(cc_list)),
        "bcc": sorted(set(bcc_list)),
        "subject": subject,
        "body": body,
        "include_default_attachment": bool(setting.get("include_default_attachment")),
        "extra_attachments": extra_attachments,
        "setting_id": setting.get("id"),
    }


def save_attachment(file_obj, setting_id: int, is_editable: bool, actor_emp_id: int) -> tuple[bool, str]:
    if not file_obj or not file_obj.filename:
        return False, "Attachment file is required."

    base_dir = Path(current_app.root_path) / "uploads" / "workflow_email"
    base_dir.mkdir(parents=True, exist_ok=True)

    original_name = secure_filename(file_obj.filename)
    safe_name = f"{setting_id}_{original_name}"
    target_path = base_dir / safe_name
    file_obj.save(target_path)

    repo.add_workflow_attachment(
        {
            "setting_id": setting_id,
            "file_name": safe_name,
            "original_name": original_name,
            "storage_path": str(target_path),
            "mime_type": file_obj.mimetype,
            "is_editable": is_editable,
        },
        actor_emp_id,
    )

    log_activity(
        emp_id=actor_emp_id,
        user_name=str(actor_emp_id),
        activity_type="WORKFLOW_EMAIL_ATTACHMENT_UPLOAD",
        remarks=f"Uploaded attachment for setting={setting_id} file={original_name} editable={int(is_editable)}",
    )
    return True, "Attachment uploaded."


def delete_attachment(attachment_id: int, actor_emp_id: int) -> tuple[bool, str]:
    row = repo.get_workflow_attachment(attachment_id)
    if not row:
        return False, "Attachment not found."

    storage_path = (row.get("storage_path") or "").strip()
    repo.deactivate_workflow_attachment(attachment_id)

    if storage_path and os.path.exists(storage_path):
        try:
            os.remove(storage_path)
        except OSError:
            logger.warning("Could not remove attachment file: %s", storage_path)

    log_activity(
        emp_id=actor_emp_id,
        user_name=str(actor_emp_id),
        activity_type="WORKFLOW_EMAIL_ATTACHMENT_DELETE",
        remarks=f"Deleted attachment id={attachment_id}",
    )
    return True, "Attachment removed."
