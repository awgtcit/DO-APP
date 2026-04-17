"""Service – Facility request business logic."""

import html
from flask import session

from repos import facility_repo as repo
from services.upload_service import save_upload
from services.email_service import send_email
from audit.logger import log_activity

# ─── Admin check ────────────────────────────────────────────────────
def is_facility_admin():
    roles = session.get("roles", [])
    return "it_admin" in roles or "admin" in roles


# ─── Dashboard ──────────────────────────────────────────────────────
def get_dashboard(emp_id=None):
    """Return counts for the current user (or all if admin)."""
    return repo.get_counts(emp_id=emp_id)


# ─── Listing ────────────────────────────────────────────────────────
def list_requests(page=1, status=None, search=None):
    admin = is_facility_admin()
    emp_id = None if admin else session.get("emp_id")
    return repo.get_requests(
        emp_id=emp_id, status=status, page=page, search=search
    )


# ─── Detail ─────────────────────────────────────────────────────────
def get_request_detail(req_id):
    req = repo.get_request_by_id(req_id)
    if req is None:
        return None, []

    # Parse attachments
    raw = req.get("attachments") or ""
    if raw and raw != "N/A":
        req["attachment_list"] = [f.strip() for f in raw.split("|") if f.strip()]
    else:
        req["attachment_list"] = []

    # Decode summary HTML
    body = req.get("summary") or ""
    try:
        req["summary_html"] = html.unescape(body)
    except Exception:
        req["summary_html"] = body

    # Age in days
    if req.get("created_on"):
        from datetime import datetime
        age = (datetime.now() - req["created_on"]).days
        req["age_days"] = age
        req["overdue"] = age >= (req.get("deadline") or 30)
    else:
        req["age_days"] = 0
        req["overdue"] = False

    comments = repo.get_comments(req_id)
    return req, comments


def can_view(req):
    """Check if current user can view this request."""
    if is_facility_admin():
        return True
    return str(req.get("EmpID")) == str(session.get("emp_id"))


# ─── Create ─────────────────────────────────────────────────────────
def create_request(form_data, files=None):
    emp_id = session.get("emp_id")

    # Handle file uploads
    attachment_parts = []
    if files:
        for f in files:
            if f and f.filename:
                result = save_upload(f, "facility")
                if result:
                    attachment_parts.append(result["filename"])

    attachments = "|" + "|".join(attachment_parts) if attachment_parts else "N/A"

    data = {
        "emp_id": emp_id,
        "subject": form_data["subject"],
        "site": form_data.get("site", ""),
        "summary": form_data.get("summary", ""),
        "attachments": attachments,
    }

    req_id = repo.create_request(data)
    log_activity("facility", f"Created facility request #{req_id}: {data['subject']}")
    return req_id


# ─── Status changes ────────────────────────────────────────────────
def close_request(req_id, reason):
    emp_id = session.get("emp_id")
    repo.close_request(req_id)
    repo.add_comment(
        req_id, emp_id,
        f"This request is closed — Reason: {reason}",
        request_status="closed",
    )
    log_activity("facility", f"Closed facility request #{req_id}")
    return True


def reopen_request(req_id, reason):
    emp_id = session.get("emp_id")
    repo.reopen_request(req_id)
    repo.add_comment(
        req_id, emp_id,
        f"This request has been re-opened — Reason: {reason}",
        request_status="re-opened",
    )
    log_activity("facility", f"Re-opened facility request #{req_id}")
    return True


# ─── Comments ───────────────────────────────────────────────────────
def add_comment(req_id, description):
    emp_id = session.get("emp_id")
    repo.add_comment(req_id, emp_id, description, request_status="open")
    log_activity("facility", f"Commented on facility request #{req_id}")
    return True
