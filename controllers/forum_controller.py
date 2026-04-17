"""
Employee Forum controller — directory, profiles, and birthday calendar.
Blueprint prefix: /forum
"""

from flask import Blueprint, render_template, request

from auth.middleware import login_required
from services.forum_service import (
    list_employees,
    get_department_options,
    get_stats,
    get_employee_profile,
    get_birthday_list,
)

forum_bp = Blueprint(
    "forum",
    __name__,
    url_prefix="/forum",
    template_folder="../templates",
)


# ── Directory ──────────────────────────────────────────────────

@forum_bp.route("/")
@login_required
def index():
    """Employee directory — searchable, filterable list."""
    search = request.args.get("search", "").strip() or None
    department = request.args.get("department", "").strip() or None
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 25

    employees, total = list_employees(
        search=search,
        department=department,
        page=page,
        per_page=per_page,
    )
    total_pages = max(1, -(-total // per_page))

    departments = get_department_options()
    stats = get_stats()

    return render_template(
        "forum/directory.html",
        employees=employees,
        departments=departments,
        stats=stats,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search or "",
        department=department or "",
    )


# ── Profile ────────────────────────────────────────────────────

@forum_bp.route("/profile/<int:emp_id>")
@login_required
def profile(emp_id: int):
    """Single employee profile view."""
    emp = get_employee_profile(emp_id)
    if not emp:
        return render_template("forum/directory.html", employees=[], departments=[],
                               stats={}, page=1, total_pages=1, total=0,
                               search="", department=""), 404
    return render_template("forum/profile.html", employee=emp)


# ── Birthdays ──────────────────────────────────────────────────

@forum_bp.route("/birthdays")
@login_required
def birthdays():
    """Birthday list for the current month."""
    people = get_birthday_list()
    return render_template("forum/birthdays.html", people=people)
