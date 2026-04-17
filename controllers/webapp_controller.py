"""
Web Application hub controller — the main menu grid matching the old PHP app.
Maps all sub-modules: Quality, R.M. Store, Production, Finance, Technical, Sales, News, IT.
"""

from flask import Blueprint, render_template, session
from auth.middleware import login_required

webapp_bp = Blueprint(
    "webapp",
    __name__,
    url_prefix="/web-application",
)

# ── Module definitions for the grid ──────────────────────────────
MODULES = {
    "quality": {
        "label": "Quality",
        "color": "amber",
        "icon": "clipboard-check",
        "sub_items": [
            {"slug": "inspection",     "label": "Inspection"},
            {"slug": "parameters",     "label": "Parameters"},
            {"slug": "qa-inspection",  "label": "QA Inspection"},
            {"slug": "mc-calculation", "label": "MC Calculation"},
        ],
    },
    "rm-store": {
        "label": "R. M. Store",
        "color": "brand",
        "icon": "archive",
        "sub_items": [
            {"slug": "purchase-order",        "label": "Purchase Order"},
            {"slug": "supplier",              "label": "Supplier"},
            {"slug": "material",              "label": "Material"},
            {"slug": "grn",                   "label": "GRN"},
            {"slug": "tobacco-storage",       "label": "Tobacco Storage Monitor"},
            {"slug": "rm-mc-calculation",     "label": "MC Calculation"},
        ],
    },
    "production": {
        "label": "Production",
        "color": "green",
        "icon": "factory",
        "sub_items": [
            {"slug": "production-screens",   "label": "Production Screens"},
            {"slug": "prod-mc-calculation",  "label": "MC Calculation"},
        ],
    },
    "finance": {
        "label": "Finance",
        "color": "purple",
        "icon": "banknotes",
        "sub_items": [
            {"slug": "customers", "label": "Customers"},
        ],
    },
    "technical": {
        "label": "Technical",
        "color": "teal",
        "icon": "wrench",
        "sub_items": [
            {"slug": "facility", "label": "Facility"},
        ],
    },
    "sales": {
        "label": "Sales",
        "color": "red",
        "icon": "truck",
        "sub_items": [
            {"slug": "delivery-order", "label": "Delivery Order", "link": "/delivery-orders"},
            {"slug": "forecast",       "label": "Forecast"},
        ],
    },
    "news": {
        "label": "News",
        "color": "slate",
        "icon": "newspaper",
        "sub_items": [
            {"slug": "gulf-news", "label": "Gulf News"},
        ],
    },
    "it": {
        "label": "IT",
        "color": "indigo",
        "icon": "server",
        "sub_items": [
            {"slug": "db-log",      "label": "Database Logs"},
            {"slug": "it-helpdesk", "label": "IT Help Desk"},
            {"slug": "sap",         "label": "SAP"},
        ],
    },
}


@webapp_bp.route("/")
@login_required
def index():
    """Render the Web Application module grid hub."""
    return render_template(
        "webapp/index.html",
        modules=MODULES,
    )


@webapp_bp.route("/module/<slug>")
@login_required
def module_page(slug):
    """Generic placeholder for sub-modules not yet implemented."""
    # Find the label from MODULES
    label = slug.replace("-", " ").title()
    for group in MODULES.values():
        for item in group["sub_items"]:
            if item["slug"] == slug:
                label = item["label"]
                break
    return render_template(
        "webapp/module_coming_soon.html",
        module_name=label,
        module_slug=slug,
    )
