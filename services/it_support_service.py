"""
IT Support service layer.

Flow: Controller → Service → Rules → Repository → Audit
No direct DB access here — everything goes through repos.
"""

import logging

from repos.it_support_repo import (
    get_all_tickets,
    get_ticket_by_id,
    create_ticket as repo_create,
    update_ticket as repo_update,
    update_ticket_status as repo_update_status,
    delete_ticket as repo_delete,
    get_ticket_stats,
    count_tickets_by_empid,
)
from rules.it_support_rules import (
    validate_create_ticket,
    validate_update_ticket,
    validate_status_change,
)
from audit.logger import log_activity, log_db_operation

logger = logging.getLogger(__name__)


class ServiceResult:
    """Standardised service response."""

    def __init__(
        self,
        success: bool,
        data=None,
        errors: list[str] | None = None,
        meta: dict | None = None,
    ):
        self.success = success
        self.data = data
        self.errors = errors or []
        self.meta = meta or {}


def list_tickets(
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
) -> ServiceResult:
    """Paginated ticket listing with optional filters."""
    rows, total = get_all_tickets(status=status, page=page, per_page=per_page, search=search)
    return ServiceResult(
        success=True,
        data=rows,
        meta={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": max(1, -(-total // per_page)),  # ceil division
        },
    )


def get_ticket(
    ticket_id: int,
    emp_id: int = None,
    is_admin: bool = False,
    user_email: str = "",
) -> ServiceResult:
    """Get a single ticket with optional authorization check."""
    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        return ServiceResult(success=False, errors=["Ticket not found."])
    # Object-level authorization: only requester, admin, or IT staff can view
    if emp_id is not None and not is_admin:
        requester_val = str(ticket.get("requester", ""))
        if requester_val != str(emp_id) and requester_val != user_email:
            return ServiceResult(success=False, errors=["You do not have permission to view this ticket."])
    return ServiceResult(success=True, data=ticket)


def create_ticket(data: dict, emp_id: int, client_ip: str = "") -> ServiceResult:
    """Validate and create a new ticket."""
    # ── Rules engine ───────────────────────────────────────────────
    errors = validate_create_ticket(data)
    if errors:
        return ServiceResult(success=False, errors=errors)

    # ── Repository ─────────────────────────────────────────────────
    payload = {
        "requester_email": data.get("requester_email", str(emp_id)),
        "subject": data["subject"].strip(),
        "summary": data["summary"].strip(),
        "priority": data["priority"].strip().lower(),
        "on_behalf_of": data.get("on_behalf_of", "").strip(),
    }
    new_id = repo_create(payload)

    # ── Audit ──────────────────────────────────────────────────────
    log_activity(
        emp_id=emp_id,
        user_name=str(emp_id),
        activity_type="IT_SUPPORT_CREATE",
        client_ip=client_ip,
        remarks=f"Created ticket #{new_id}: {payload['subject']}",
    )
    log_db_operation(emp_id, f"INSERT Intra_ITSupport id={new_id}")

    return ServiceResult(success=True, data={"id": new_id})


def update_ticket(
    ticket_id: int,
    data: dict,
    emp_id: int,
    client_ip: str = "",
    is_admin: bool = False,
    user_email: str = "",
) -> ServiceResult:
    """Validate and update a ticket with authorization check."""
    existing = get_ticket_by_id(ticket_id)
    if not existing:
        return ServiceResult(success=False, errors=["Ticket not found."])

    # Authorization: only requester or admin can edit
    requester_val = str(existing.get("requester", ""))
    if not is_admin and requester_val != str(emp_id) and requester_val != user_email:
        return ServiceResult(success=False, errors=["You do not have permission to edit this ticket."])

    errors = validate_update_ticket(data)
    if errors:
        return ServiceResult(success=False, errors=errors)

    payload = {
        "subject": data["subject"].strip(),
        "summary": data["summary"].strip(),
        "priority": data["priority"].strip().lower(),
        "on_behalf_of": data.get("on_behalf_of", "").strip(),
        "status": data.get("status", existing.get("status", "open")).strip().lower(),
    }
    repo_update(ticket_id, payload)

    log_activity(
        emp_id=emp_id,
        user_name=str(emp_id),
        activity_type="IT_SUPPORT_UPDATE",
        client_ip=client_ip,
        remarks=f"Updated ticket #{ticket_id}",
    )
    log_db_operation(emp_id, f"UPDATE Intra_ITSupport id={ticket_id}")

    return ServiceResult(success=True, data={"id": ticket_id})


def change_status(
    ticket_id: int,
    new_status: str,
    emp_id: int,
    client_ip: str = "",
    is_admin: bool = False,
    user_email: str = "",
) -> ServiceResult:
    """Validate status transition and update with authorization check."""
    existing = get_ticket_by_id(ticket_id)
    if not existing:
        return ServiceResult(success=False, errors=["Ticket not found."])

    # Authorization: only requester or admin can change status
    requester_val = str(existing.get("requester", ""))
    if not is_admin and requester_val != str(emp_id) and requester_val != user_email:
        return ServiceResult(success=False, errors=["You do not have permission to change this ticket's status."])

    current = existing.get("status", "open")
    errors = validate_status_change(current, new_status)
    if errors:
        return ServiceResult(success=False, errors=errors)

    repo_update_status(ticket_id, new_status)

    log_activity(
        emp_id=emp_id,
        user_name=str(emp_id),
        activity_type="IT_SUPPORT_STATUS",
        client_ip=client_ip,
        remarks=f"Ticket #{ticket_id}: {current} → {new_status}",
    )
    log_db_operation(emp_id, f"UPDATE Intra_ITSupport SET status='{new_status}' id={ticket_id}")

    return ServiceResult(success=True, data={"id": ticket_id, "status": new_status})


def remove_ticket(
    ticket_id: int,
    emp_id: int,
    client_ip: str = "",
    is_admin: bool = False,
    user_email: str = "",
) -> ServiceResult:
    """Delete a ticket with authorization check."""
    existing = get_ticket_by_id(ticket_id)
    if not existing:
        return ServiceResult(success=False, errors=["Ticket not found."])

    # Authorization: only requester or admin can delete
    requester_val = str(existing.get("requester", ""))
    if not is_admin and requester_val != str(emp_id) and requester_val != user_email:
        return ServiceResult(success=False, errors=["You do not have permission to delete this ticket."])

    repo_delete(ticket_id)

    log_activity(
        emp_id=emp_id,
        user_name=str(emp_id),
        activity_type="IT_SUPPORT_DELETE",
        client_ip=client_ip,
        remarks=f"Deleted ticket #{ticket_id}",
    )
    log_db_operation(emp_id, f"DELETE Intra_ITSupport id={ticket_id}")

    return ServiceResult(success=True)


def dashboard_stats() -> ServiceResult:
    """Aggregated ticket statistics for the dashboard."""
    stats = get_ticket_stats()
    return ServiceResult(success=True, data=stats)
