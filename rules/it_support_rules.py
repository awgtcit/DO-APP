"""
IT Support validation rules.
Validation functions with optional dependency injection for testability.
Service imports are deferred and only used as defaults when callers
don't supply pre-fetched data (e.g. workflow flow, restricted words).
"""

from services.admin_settings_service import check_text_for_restricted_words

VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_STATUSES = {"open", "in_progress", "closed"}


def validate_create_ticket(data: dict) -> list[str]:
    """Validate data for creating a new ticket."""
    errors: list[str] = []

    subject = (data.get("subject") or "").strip()
    if not subject:
        errors.append("Subject is required.")
    elif len(subject) < 5:
        errors.append("Subject must be at least 5 characters.")
    elif len(subject) > 200:
        errors.append("Subject must not exceed 200 characters.")
    else:
        blocked = check_text_for_restricted_words(subject)
        if blocked:
            errors.append(f"Subject contains blocked word(s): {', '.join(blocked)}")

    summary = (data.get("summary") or "").strip()
    if not summary:
        errors.append("Summary / description is required.")
    elif len(summary) < 10:
        errors.append("Summary must be at least 10 characters.")
    else:
        blocked = check_text_for_restricted_words(summary)
        if blocked:
            errors.append(f"Summary contains blocked word(s): {', '.join(blocked)}")

    priority = (data.get("priority") or "").strip().lower()
    if not priority:
        errors.append("Priority is required.")
    elif priority not in VALID_PRIORITIES:
        errors.append(f"Priority must be one of: {', '.join(sorted(VALID_PRIORITIES))}.")

    return errors


def validate_update_ticket(data: dict) -> list[str]:
    """Validate data for updating an existing ticket."""
    errors = validate_create_ticket(data)

    status = (data.get("status") or "").strip().lower()
    if status and status not in VALID_STATUSES:
        errors.append(f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}.")

    return errors


def validate_status_change(current_status: str, new_status: str,
                           flow: dict | None = None) -> list[str]:
    """Validate allowed status transitions.
    
    Args:
        flow: Optional pre-fetched transition dict. If None, loaded from
              admin_settings_service (DB-first with hardcoded fallback).
    """
    errors: list[str] = []

    if new_status not in VALID_STATUSES:
        errors.append(f"Invalid status: {new_status}")
        return errors

    if flow is None:
        from services.admin_settings_service import get_status_flow
        flow = get_status_flow("it_support")
    allowed_transitions = {k: set(v) for k, v in flow.items()}

    if new_status not in allowed_transitions.get(current_status, set()):
        errors.append(
            f"Cannot change status from '{current_status}' to '{new_status}'."
        )

    return errors
