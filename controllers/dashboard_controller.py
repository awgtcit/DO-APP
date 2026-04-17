"""
Dashboard controller — home page with KPI cards.
"""

from flask import Blueprint, render_template

from auth.middleware import login_required
from services.it_support_service import dashboard_stats

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/")


@dashboard_bp.route("/")
@login_required
def home():
    stats_result = dashboard_stats()
    stats = stats_result.data if stats_result.success else {}
    return render_template("dashboard/home.html", stats=stats)
