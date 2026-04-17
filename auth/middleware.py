"""
Authentication & authorization middleware.

- check_session: runs before every request to enforce login
- login_required: decorator for explicit route protection
- role_required: decorator for permission-gated routes
"""

from functools import wraps

from flask import redirect, request, session, url_for, flash


# Routes that do NOT require authentication
_PUBLIC_ROUTES = frozenset(
    {
        "auth.login",
        "auth.login_post",
        "auth.isp_accept",
        "auth.isp_accept_post",
        "static",
    }
)


def check_session():
    """Flask before_request hook — redirects unauthenticated users."""
    if request.endpoint in _PUBLIC_ROUTES:
        return None

    if not session.get("email"):
        flash("Please log in to continue.", "warning")
        return redirect(url_for("auth.login"))

    return None


def login_required(fn):
    """Decorator: ensures user is authenticated."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("email"):
            flash("Session expired. Please log in again.", "warning")
            return redirect(url_for("auth.login"))
        return fn(*args, **kwargs)

    return wrapper


def role_required(*allowed_roles: str):
    """
    Decorator: ensures user has at least one of the given roles.
    Roles are stored in session['roles'] as a set of strings.

    Usage:
        @role_required("admin", "it_admin")
        def admin_page(): ...
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user_roles = set(session.get("roles", []))
            if not user_roles.intersection(allowed_roles):
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for("dashboard.home"))
            return fn(*args, **kwargs)

        return wrapper

    return decorator
