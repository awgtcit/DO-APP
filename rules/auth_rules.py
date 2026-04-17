"""
Auth validation rules.
Pure functions — no DB access, no side effects.
"""

import re

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_login(username: str, password: str) -> list[str]:
    """Return a list of validation errors (empty = valid)."""
    errors: list[str] = []

    if not username or not username.strip():
        errors.append("Username or email is required.")
    elif len(username.strip()) < 2:
        errors.append("Username must be at least 2 characters.")

    if not password:
        errors.append("Password is required.")
    elif len(password) < 3:
        errors.append("Password must be at least 3 characters.")

    return errors


def validate_isp_acceptance(accepted: bool) -> list[str]:
    errors: list[str] = []
    if not accepted:
        errors.append("You must accept the Information Security Policy to continue.")
    return errors
