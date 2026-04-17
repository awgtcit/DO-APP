"""
Admin Settings validation rules.
Pure functions — no DB, no side effects.
"""

import re


def validate_user(data: dict, is_new: bool = True) -> list[str]:
    """Validate user creation/update data."""
    errors: list[str] = []

    first_name = (data.get("first_name") or "").strip()
    if not first_name:
        errors.append("First name is required.")
    elif len(first_name) > 100:
        errors.append("First name must not exceed 100 characters.")

    last_name = (data.get("last_name") or "").strip()
    if not last_name:
        errors.append("Last name is required.")
    elif len(last_name) > 100:
        errors.append("Last name must not exceed 100 characters.")

    email = (data.get("email") or "").strip()
    if not email:
        errors.append("Email is required.")
    elif not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        errors.append("Invalid email format.")

    username = (data.get("username") or "").strip()
    if not username:
        errors.append("Username is required.")
    elif len(username) < 3:
        errors.append("Username must be at least 3 characters.")

    if not data.get("department_id"):
        errors.append("Department is required.")

    if is_new:
        password = data.get("password") or ""
        if not password:
            errors.append("Password is required.")
        elif len(password) < 6:
            errors.append("Password must be at least 6 characters.")

    return errors


def validate_password_reset(password: str) -> list[str]:
    """Validate new password for reset."""
    errors: list[str] = []
    if not password:
        errors.append("Password is required.")
    elif len(password) < 6:
        errors.append("Password must be at least 6 characters.")
    return errors


def validate_restricted_word(word: str) -> list[str]:
    """Validate a restricted word."""
    errors: list[str] = []
    word = (word or "").strip()
    if not word:
        errors.append("Word is required.")
    elif len(word) < 2:
        errors.append("Word must be at least 2 characters.")
    elif len(word) > 100:
        errors.append("Word must not exceed 100 characters.")
    elif not re.match(r'^[\w\s-]+$', word):
        errors.append("Word can only contain letters, numbers, spaces, and hyphens.")
    return errors


def validate_workflow_status(data: dict) -> list[str]:
    """Validate workflow status data."""
    errors: list[str] = []

    status_key = (data.get("status_key") or "").strip()
    if not status_key:
        errors.append("Status key is required.")
    elif len(status_key) > 50:
        errors.append("Status key must not exceed 50 characters.")

    display_name = (data.get("display_name") or "").strip()
    if not display_name:
        errors.append("Display name is required.")
    elif len(display_name) > 100:
        errors.append("Display name must not exceed 100 characters.")

    return errors


def validate_workflow_transition(data: dict) -> list[str]:
    """Validate workflow transition data."""
    errors: list[str] = []

    if not (data.get("from_status") or "").strip():
        errors.append("From status is required.")
    if not (data.get("to_status") or "").strip():
        errors.append("To status is required.")
    if data.get("from_status") == data.get("to_status"):
        errors.append("From and To status cannot be the same.")
    if not (data.get("required_role") or "").strip():
        errors.append("Role is required for transitions.")

    return errors
