"""
DMS service — business logic for the Document Management System.
Handles permission checks, status transitions, and email notifications.
"""

from repos.dms_repo import (
    get_departments,
    get_document_types,
    get_document_statuses,
    get_companies,
    get_parties,
    get_user_dms_permissions,
    is_dms_itadmin,
    get_user_role_for_department,
    get_users_by_role_in_department,
    get_documents_for_department,
    get_document_by_id,
    get_document_attachments,
    create_document,
    update_document,
    update_document_status,
    add_attachment,
    delete_attachment,
    create_department,
    create_document_type,
    create_company,
    create_party,
    get_dms_stats,
)
from rules.dms_rules import (
    validate_document,
    can_transition,
    get_required_role,
    get_allowed_transitions,
    STATUS_LABELS,
)
from services.email_service import send_email
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Access & permissions
# ═══════════════════════════════════════════════════════════════

def get_accessible_departments(emp_id: int) -> list[dict]:
    """Get departments the user can access.
    ITAdmin sees ALL departments.
    Others see only departments they have permissions for.
    """
    if is_dms_itadmin(emp_id):
        return get_departments()

    perms = get_user_dms_permissions(emp_id)
    dept_ids = {p["DepartmentID"] for p in perms}
    all_depts = get_departments()
    return [d for d in all_depts if d["id"] in dept_ids]


def get_user_permissions_summary(emp_id: int) -> dict:
    """Build a summary of user's DMS permissions across all departments."""
    perms = get_user_dms_permissions(emp_id)
    admin = is_dms_itadmin(emp_id)
    return {
        "is_itadmin": admin,
        "departments": perms,
        "can_upload": admin or any(p.get("Uploader") for p in perms),
        "can_approve": admin or any(p.get("Approver") for p in perms),
        "can_review": admin or any(p.get("Reviewer2") for p in perms),
    }


def can_user_access_department(emp_id: int, dept_id: int) -> bool:
    """Check if user has any DMS role in the specified department."""
    if is_dms_itadmin(emp_id):
        return True
    role = get_user_role_for_department(emp_id, dept_id)
    return role is not None


def get_user_role_flags(emp_id: int, dept_id: int) -> dict:
    """Get the user's DMS role flags for a department."""
    if is_dms_itadmin(emp_id):
        return {
            "Uploader": True, "Approver": True,
            "Reviewer1": True, "Reviewer2": True, "ITAdmin": True,
        }
    role = get_user_role_for_department(emp_id, dept_id)
    if not role:
        return {
            "Uploader": False, "Approver": False,
            "Reviewer1": False, "Reviewer2": False, "ITAdmin": False,
        }
    return {k: bool(v) for k, v in role.items()}


# ═══════════════════════════════════════════════════════════════
#  Department grid & dashboard
# ═══════════════════════════════════════════════════════════════

def dms_department_grid(emp_id: int) -> list[dict]:
    """Build the department card grid with stats."""
    depts = get_accessible_departments(emp_id)
    for dept in depts:
        dept["stats"] = get_dms_stats(dept["id"])
    return depts


def dms_global_stats() -> dict:
    """Overall DMS stats across all departments."""
    return get_dms_stats()


# ═══════════════════════════════════════════════════════════════
#  Document listing
# ═══════════════════════════════════════════════════════════════

def list_documents(
    dept_id: int,
    emp_id: int,
    status_id: int | None = None,
    page: int = 1,
    per_page: int = 25,
    search: str | None = None,
) -> tuple[list[dict], int]:
    """List documents for a department with permission-based filtering."""
    admin = is_dms_itadmin(emp_id)
    role = get_user_role_for_department(emp_id, dept_id)
    is_reviewer2 = bool(role and role.get("Reviewer2")) if not admin else False

    return get_documents_for_department(
        dept_id=dept_id,
        emp_id=emp_id,
        is_itadmin=admin,
        is_reviewer2=is_reviewer2,
        status_id=status_id,
        page=page,
        per_page=per_page,
        search=search,
    )


# ═══════════════════════════════════════════════════════════════
#  Document CRUD
# ═══════════════════════════════════════════════════════════════

def get_document_detail(doc_id: int, emp_id: int) -> dict | None:
    """Get full document detail with attachments and allowed actions."""
    doc = get_document_by_id(doc_id)
    if not doc:
        return None

    doc["attachments"] = get_document_attachments(doc_id)
    doc["status_label"] = STATUS_LABELS.get(doc.get("DocStatusID"), "Unknown")

    # Determine allowed transitions based on user role
    admin = is_dms_itadmin(emp_id)
    dept_id = doc.get("DeptID")
    role_flags = get_user_role_flags(emp_id, dept_id)

    transitions = get_allowed_transitions(doc.get("DocStatusID", 0))
    allowed = []
    for t in transitions:
        required_role = get_required_role(doc["DocStatusID"], t["id"])
        if admin or (required_role and role_flags.get(required_role)):
            allowed.append(t)

    doc["allowed_transitions"] = allowed
    doc["role_flags"] = role_flags
    doc["can_edit"] = (doc.get("DocStatusID") == 1 and
                       (role_flags.get("Uploader") or admin))

    return doc


def create_new_document(data: dict) -> tuple[int | None, dict | None]:
    """Create a new document. Returns (new_id, errors)."""
    errors = validate_document(data)
    if errors:
        return None, errors
    new_id = create_document(data)
    return new_id, None


def update_existing_document(doc_id: int, data: dict) -> tuple[bool, dict | None]:
    """Update a draft document. Returns (success, errors)."""
    errors = validate_document(data)
    if errors:
        return False, errors
    ok = update_document(doc_id, data)
    return ok, None


def change_document_status(
    doc_id: int, new_status: int, emp_id: int, remarks: str = ""
) -> tuple[bool, str]:
    """
    Transition a document's status with permission checks and email notifications.
    Returns (success, message).
    """
    doc = get_document_by_id(doc_id)
    if not doc:
        return False, "Document not found."

    current = doc.get("DocStatusID", 0)
    if not can_transition(current, new_status):
        return False, f"Cannot transition from {STATUS_LABELS.get(current)} to {STATUS_LABELS.get(new_status)}."

    # Check role permission
    required_role = get_required_role(current, new_status)
    admin = is_dms_itadmin(emp_id)
    if not admin and required_role:
        role_flags = get_user_role_flags(emp_id, doc.get("DeptID"))
        if not role_flags.get(required_role):
            return False, f"You need the {required_role} role to perform this action."

    ok = update_document_status(doc_id, new_status, emp_id, remarks)
    if not ok:
        return False, "Failed to update status."

    # Send email notifications
    _send_status_notification(doc, new_status, remarks)

    return True, f"Status changed to {STATUS_LABELS.get(new_status, 'Unknown')}."


# ═══════════════════════════════════════════════════════════════
#  Attachments
# ═══════════════════════════════════════════════════════════════

def add_document_attachment(data: dict) -> int:
    """Add an attachment record."""
    return add_attachment(data)


def remove_document_attachment(attachment_id: int) -> bool:
    """Soft-delete an attachment."""
    return delete_attachment(attachment_id)


# ═══════════════════════════════════════════════════════════════
#  Admin config
# ═══════════════════════════════════════════════════════════════

def get_form_lookups() -> dict:
    """All dropdowns needed for document forms."""
    return {
        "departments": get_departments(),
        "document_types": get_document_types(),
        "statuses": get_document_statuses(),
        "companies": get_companies(),
        "parties": get_parties(),
    }


def admin_create_department(name: str, emp_id: int) -> int:
    return create_department(name, emp_id)


def admin_create_document_type(name: str, emp_id: int) -> int:
    return create_document_type(name, emp_id)


def admin_create_company(name: str, emp_id: int) -> int:
    return create_company(name, emp_id)


def admin_create_party(name: str, emp_id: int) -> int:
    return create_party(name, emp_id)


# ═══════════════════════════════════════════════════════════════
#  Email notifications
# ═══════════════════════════════════════════════════════════════

def _send_status_notification(doc: dict, new_status: int, remarks: str = "") -> None:
    """Send email notifications based on status transition (matches PHP logic)."""
    dept_id = doc.get("DeptID")
    doc_name = doc.get("Name", "")
    subject_prefix = f"DMS — {STATUS_LABELS.get(new_status, '')} — {doc_name}"

    recipients: list[str] = []

    try:
        if new_status == 2:  # SUBMITTED → notify Uploader + Approver
            for role in ["Uploader", "Approver"]:
                users = get_users_by_role_in_department(dept_id, role)
                recipients.extend(u["EmailAddress"] for u in users if u.get("EmailAddress"))

        elif new_status == 3:  # APPROVED → notify Approver + Reviewer2
            for role in ["Approver", "Reviewer2"]:
                users = get_users_by_role_in_department(dept_id, role)
                recipients.extend(u["EmailAddress"] for u in users if u.get("EmailAddress"))

        elif new_status in (4, 8):  # REJECTED → notify Uploader
            users = get_users_by_role_in_department(dept_id, "Uploader")
            recipients.extend(u["EmailAddress"] for u in users if u.get("EmailAddress"))

        elif new_status == 7:  # FINALIZED → notify ALL
            for role in ["Uploader", "Approver", "Reviewer2", "ITAdmin"]:
                users = get_users_by_role_in_department(dept_id, role)
                recipients.extend(u["EmailAddress"] for u in users if u.get("EmailAddress"))

        elif new_status == 9:  # CANCELLED → notify Uploader
            users = get_users_by_role_in_department(dept_id, "Uploader")
            recipients.extend(u["EmailAddress"] for u in users if u.get("EmailAddress"))

        if recipients:
            unique = list(set(recipients))
            body = f"""
            <h3>Document Status Update</h3>
            <p><strong>Document:</strong> {doc_name}</p>
            <p><strong>New Status:</strong> {STATUS_LABELS.get(new_status, 'Unknown')}</p>
            {"<p><strong>Remarks:</strong> " + remarks + "</p>" if remarks else ""}
            <p>Please log into the Intranet Portal to review.</p>
            """
            send_email(to=unique, subject=subject_prefix, body_html=body)
    except Exception as exc:
        logger.warning("DMS email notification failed: %s", exc)
