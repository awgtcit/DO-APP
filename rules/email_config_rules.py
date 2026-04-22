"""Validation rules for SMTP and workflow email configuration."""

import re


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_smtp_payload(data: dict) -> list[str]:
    errors: list[str] = []
    host = (data.get("smtp_host") or "").strip()
    if not host:
        errors.append("SMTP Host is required.")

    try:
        port = int(data.get("smtp_port") or 0)
        if port < 1 or port > 65535:
            errors.append("SMTP Port must be between 1 and 65535.")
    except (TypeError, ValueError):
        errors.append("SMTP Port must be numeric.")

    user = (data.get("smtp_username") or "").strip()
    if not user:
        errors.append("SMTP Username is required.")

    sender = (data.get("sender_email") or "").strip()
    if not sender:
        errors.append("Sender Email is required.")
    elif not _EMAIL_RE.match(sender):
        errors.append("Sender Email is invalid.")

    return errors


def validate_email_list(values: list[str], label: str) -> list[str]:
    errors: list[str] = []
    for value in values:
        if value and not _EMAIL_RE.match(value):
            errors.append(f"Invalid {label} email: {value}")
    return errors


def validate_workflow_email_payload(data: dict) -> list[str]:
    errors: list[str] = []

    module_key = (data.get("module_key") or "").strip()
    status_key = (data.get("status_key") or "").strip()
    if not module_key:
        errors.append("Workflow module is required.")
    if not status_key:
        errors.append("Workflow status is required.")

    subject = (data.get("subject_template") or "").strip()
    body = (data.get("body_template") or "").strip()
    if not subject:
        errors.append("Email subject is required.")
    if not body:
        errors.append("Email body is required.")

    to_emails = data.get("to_emails") or []
    cc_emails = data.get("cc_emails") or []
    bcc_emails = data.get("bcc_emails") or []
    selected_users = data.get("selected_user_ids") or []

    if not selected_users and not to_emails:
        errors.append("Select at least one recipient user or direct TO email.")

    errors.extend(validate_email_list(to_emails, "TO"))
    errors.extend(validate_email_list(cc_emails, "CC"))
    errors.extend(validate_email_list(bcc_emails, "BCC"))

    return errors
