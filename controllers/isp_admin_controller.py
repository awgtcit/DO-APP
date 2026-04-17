"""
ISP Status Admin controller — view Information Security Policy
acceptance records (admin-only).
Blueprint prefix: /isp-admin
"""

from flask import Blueprint, render_template, request, session, flash, redirect, url_for

from auth.middleware import login_required
from services.isp_service import is_isp_admin, list_isp_records, isp_overview_stats

isp_admin_bp = Blueprint(
    "isp_admin",
    __name__,
    url_prefix="/isp-admin",
    template_folder="../templates",
)


@isp_admin_bp.route("/")
@login_required
def index():
    """ISP acceptance status list — admin only."""
    roles = session.get("roles", [])
    if not is_isp_admin(roles):
        flash("You are not authorised to view ISP status.", "error")
        return redirect(url_for("dashboard.home"))

    search = request.args.get("search", "").strip() or None
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 50

    records, total = list_isp_records(search=search, page=page, per_page=per_page)
    total_pages = max(1, -(-total // per_page))
    stats = isp_overview_stats()

    return render_template(
        "isp_admin/list.html",
        records=records,
        stats=stats,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search or "",
    )
