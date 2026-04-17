"""
DMS validation rules — document creation, editing, and status transitions.
"""

from services.admin_settings_service import check_text_for_restricted_words


def validate_document(data: dict) -> dict | None:
    """Validate document creation/edit data. Returns errors dict or None."""
    errors = {}

    name = data.get("name", "").strip()
    if not name:
        errors["name"] = "Document name is required."
    else:
        blocked = check_text_for_restricted_words(name)
        if blocked:
            errors["name"] = f"Document name contains blocked word(s): {', '.join(blocked)}"

    if not data.get("dept_id"):
        errors["dept_id"] = "Department is required."

    if not data.get("doc_type_id"):
        errors["doc_type_id"] = "Document type is required."

    return errors if errors else None


# ── Status transition matrix ────────────────────────────────────
# Status IDs: 1=DRAFT, 2=SUBMITTED, 3=APPROVED, 4=APPROVER_REJECTED,
#             5=REVIEWER1_APPROVED (skipped), 7=FINALIZED,
#             8=REVIEWER_REJECTED, 9=CANCELLED

STATUS_TRANSITIONS = {
    1: [2, 9],       # DRAFT → SUBMITTED or CANCELLED
    2: [3, 4],       # SUBMITTED → APPROVED or APPROVER_REJECTED
    3: [7, 8],       # APPROVED → FINALIZED or REVIEWER_REJECTED
    4: [1],          # APPROVER_REJECTED → back to DRAFT
    7: [],           # FINALIZED (terminal)
    8: [1],          # REVIEWER_REJECTED → back to DRAFT
    9: [],           # CANCELLED (terminal)
}

# Who can perform each transition
TRANSITION_ROLES = {
    (1, 2): "Uploader",       # Uploader submits
    (1, 9): "Uploader",       # Uploader cancels
    (2, 3): "Approver",       # Approver approves
    (2, 4): "Approver",       # Approver rejects
    (3, 7): "Reviewer2",      # Reviewer2 finalizes
    (3, 8): "Reviewer2",      # Reviewer2 rejects
    (4, 1): "Uploader",       # Uploader re-edits after rejection
    (8, 1): "Uploader",       # Uploader re-edits after reviewer rejection
}

STATUS_LABELS = {
    1: "Draft",
    2: "Submitted",
    3: "Approved",
    4: "Approver Rejected",
    5: "Reviewer 1 Approved",
    7: "Finalized",
    8: "Reviewer Rejected",
    9: "Cancelled",
}


def _get_dms_transitions(flow: dict | None = None) -> dict:
    """Return DMS transitions.

    Args:
        flow: Optional pre-fetched transition dict. If None, loaded from
              admin_settings_service (DB-first with hardcoded fallback).
    """
    if flow is not None:
        return {int(k): [int(v) for v in vals] for k, vals in flow.items()}
    from services.admin_settings_service import get_status_flow
    db_flow = get_status_flow("dms")
    if db_flow:
        return {int(k): [int(v) for v in vals] for k, vals in db_flow.items()}
    return STATUS_TRANSITIONS


def can_transition(current_status: int, new_status: int,
                   flow: dict | None = None) -> bool:
    """Check if a status transition is valid.

    Args:
        flow: Optional pre-fetched transition dict for testability.
    """
    transitions = _get_dms_transitions(flow)
    allowed = transitions.get(current_status, [])
    return new_status in allowed


def get_required_role(current_status: int, new_status: int) -> str | None:
    """Return the DMS role required for a transition."""
    return TRANSITION_ROLES.get((current_status, new_status))


def get_allowed_transitions(current_status: int) -> list[dict]:
    """Return list of allowed target statuses with labels."""
    allowed_ids = STATUS_TRANSITIONS.get(current_status, [])
    return [{"id": sid, "label": STATUS_LABELS.get(sid, f"Status {sid}")} for sid in allowed_ids]
