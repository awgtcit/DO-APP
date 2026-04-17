"""Service – Announcements business logic."""

import html
from flask import session

from repos import announcements_repo as repo
from services.upload_service import save_upload, delete_upload
from services.email_service import send_email
from audit.logger import log_activity

# ─── Admin check ────────────────────────────────────────────────────
# Legacy used hardcoded emails.  We use ITAdmin or a future
# "announcements_admin" role.  For now, expose a simple helper.
ADMIN_ROLES = {"ITAdmin"}


def is_announcements_admin(emp_id=None):
    """Check if the current user can manage announcements."""
    roles = session.get("roles", [])
    return "it_admin" in roles or "admin" in roles


# ─── Categories ─────────────────────────────────────────────────────
def list_categories():
    return repo.get_categories()


def get_category(cat_id):
    return repo.get_category_by_id(cat_id)


def create_category(name):
    email = session.get("email", "system")
    cat_id = repo.create_category(name, email)
    log_activity("announcements", f"Created category '{name}' (ID={cat_id})")
    return cat_id


# ─── Announcements ──────────────────────────────────────────────────
def list_announcements(category_id=None, page=1, search=None):
    return repo.get_announcements(
        category_id=category_id, page=page, search=search
    )


def get_announcement(ann_id):
    ann = repo.get_announcement_by_id(ann_id)
    if ann is None:
        return None
    # Parse attachments into list
    raw = ann.get("Attachments") or ""
    ann["attachment_list"] = [
        f.strip() for f in raw.split(";") if f.strip()
    ]
    # Decode body (legacy double-encoded HTML)
    body = ann.get("AnnouncementBody") or ""
    try:
        ann["body_html"] = html.unescape(html.unescape(body))
    except Exception:
        ann["body_html"] = body
    return ann


def create_announcement(form_data, files=None):
    """Create a new announcement with optional file uploads."""
    # Build attachment string
    attachment_names = []
    if files:
        for f in files:
            if f and f.filename:
                result = save_upload(f, "announcements")
                if result:
                    attachment_names.append(result["filename"])

    data = {
        "category_id": form_data["category_id"],
        "subject": form_data["subject"],
        "body": form_data.get("body", ""),
        "attachments": "; ".join(attachment_names) + ("; " if attachment_names else ""),
    }
    email = session.get("email", "system")
    ann_id = repo.create_announcement(data, email)
    log_activity("announcements", f"Created announcement #{ann_id}: {data['subject']}")
    return ann_id


def update_announcement(ann_id, form_data, files=None):
    """Update an existing announcement."""
    existing = repo.get_announcement_by_id(ann_id)
    if not existing:
        return False, "Announcement not found"

    # Preserve existing attachments, add new ones
    raw = existing.get("Attachments") or ""
    existing_files = [f.strip() for f in raw.split(";") if f.strip()]

    if files:
        for f in files:
            if f and f.filename:
                result = save_upload(f, "announcements")
                if result:
                    existing_files.append(result["filename"])

    data = {
        "category_id": form_data["category_id"],
        "subject": form_data["subject"],
        "body": form_data.get("body", ""),
        "attachments": "; ".join(existing_files) + ("; " if existing_files else ""),
    }
    repo.update_announcement(ann_id, data)
    log_activity("announcements", f"Updated announcement #{ann_id}")
    return True, "Announcement updated"


def delete_announcement_by_id(ann_id):
    """Delete an announcement and its attachment files."""
    existing = repo.get_announcement_by_id(ann_id)
    if not existing:
        return False
    # Clean up attachment files
    raw = existing.get("Attachments") or ""
    for fname in [f.strip() for f in raw.split(";") if f.strip()]:
        delete_upload("announcements", fname)
    repo.delete_announcement(ann_id)
    log_activity("announcements", f"Deleted announcement #{ann_id}")
    return True
