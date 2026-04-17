"""
Placeholder controller for modules that are not yet migrated.
Provides a clean "coming soon" page for each module.
"""

from flask import Blueprint, render_template
from auth.middleware import login_required

placeholder_bp = Blueprint("placeholder", __name__)

_MODULES = {
    "documents": "Document Management",
    "sales-orders": "Sales Orders",
    "announcements": "Announcements",
    "facility": "Facility Management",
    "users": "User Management",
    "settings": "Settings",
}


@placeholder_bp.route("/<module_slug>")
@login_required
def coming_soon(module_slug: str):
    module_name = _MODULES.get(module_slug, module_slug.replace("-", " ").title())
    return render_template("coming_soon.html", module_name=module_name)
