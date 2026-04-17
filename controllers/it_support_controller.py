"""
IT Support controller — full CRUD with REST-style routes.

Routes:
  GET    /it-support              → list tickets
  GET    /it-support/create       → create form
  POST   /it-support/create       → submit new ticket
  GET    /it-support/<id>         → ticket detail
  GET    /it-support/<id>/edit    → edit form
  POST   /it-support/<id>/edit    → submit update
  POST   /it-support/<id>/status  → change status (AJAX-friendly)
  POST   /it-support/<id>/delete  → delete ticket
"""

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)

from auth.middleware import login_required
from services.it_support_service import (
    list_tickets,
    get_ticket,
    create_ticket,
    update_ticket,
    change_status,
    remove_ticket,
    dashboard_stats,
)

it_support_bp = Blueprint("it_support", __name__, url_prefix="/it-support")


def _is_admin() -> bool:
    """Check if current user has admin or IT staff role."""
    roles = set(session.get("roles", []))
    return bool(roles.intersection({"admin", "it_staff", "it_admin"}))


# ── List ────────────────────────────────────────────────────────────

@it_support_bp.route("/")
@login_required
def index():
    page = request.args.get("page", 1, type=int)
    status_filter = request.args.get("status", None)
    search = request.args.get("q", None)

    result = list_tickets(status=status_filter, page=page, search=search)
    stats = dashboard_stats()

    return render_template(
        "it_support/list.html",
        tickets=result.data,
        meta=result.meta,
        stats=stats.data,
        current_status=status_filter,
        search_query=search or "",
    )


# ── Create ──────────────────────────────────────────────────────────

@it_support_bp.route("/create", methods=["GET"])
@login_required
def create_form():
    return render_template("it_support/create.html", form={}, editing=False)


@it_support_bp.route("/create", methods=["POST"])
@login_required
def create_post():
    data = {
        "subject": request.form.get("subject", ""),
        "summary": request.form.get("summary", ""),
        "priority": request.form.get("priority", "medium"),
        "on_behalf_of": request.form.get("on_behalf_of", ""),
        "requester_email": session.get("email", ""),
    }
    emp_id = session.get("emp_id", 0)
    result = create_ticket(data, emp_id, request.remote_addr or "")

    if not result.success:
        for err in result.errors:
            flash(err, "danger")
        return render_template("it_support/create.html", form=data)

    flash("Ticket created successfully.", "success")
    return redirect(url_for("it_support.detail", ticket_id=result.data["id"]))


# ── Detail ──────────────────────────────────────────────────────────

@it_support_bp.route("/<int:ticket_id>")
@login_required
def detail(ticket_id: int):
    emp_id = session.get("emp_id", 0)
    user_email = session.get("email", "")
    result = get_ticket(ticket_id, emp_id=emp_id, is_admin=_is_admin(), user_email=user_email)
    if not result.success:
        flash(result.errors[0], "danger")
        return redirect(url_for("it_support.index"))
    return render_template("it_support/detail.html", ticket=result.data)


# ── Edit ────────────────────────────────────────────────────────────

@it_support_bp.route("/<int:ticket_id>/edit", methods=["GET"])
@login_required
def edit_form(ticket_id: int):
    emp_id = session.get("emp_id", 0)
    user_email = session.get("email", "")
    result = get_ticket(ticket_id, emp_id=emp_id, is_admin=_is_admin(), user_email=user_email)
    if not result.success:
        flash(result.errors[0], "danger")
        return redirect(url_for("it_support.index"))
    return render_template("it_support/create.html", form=result.data, editing=True)


@it_support_bp.route("/<int:ticket_id>/edit", methods=["POST"])
@login_required
def edit_post(ticket_id: int):
    data = {
        "subject": request.form.get("subject", ""),
        "summary": request.form.get("summary", ""),
        "priority": request.form.get("priority", "medium"),
        "on_behalf_of": request.form.get("on_behalf_of", ""),
        "status": request.form.get("status", "open"),
    }
    emp_id = session.get("emp_id", 0)
    user_email = session.get("email", "")
    result = update_ticket(ticket_id, data, emp_id, request.remote_addr or "", is_admin=_is_admin(), user_email=user_email)

    if not result.success:
        for err in result.errors:
            flash(err, "danger")
        return render_template("it_support/create.html", form=data, editing=True)

    flash("Ticket updated successfully.", "success")
    return redirect(url_for("it_support.detail", ticket_id=ticket_id))


# ── Status change (AJAX-friendly) ──────────────────────────────────

@it_support_bp.route("/<int:ticket_id>/status", methods=["POST"])
@login_required
def status_change(ticket_id: int):
    new_status = request.form.get("status", "") or request.json.get("status", "")
    emp_id = session.get("emp_id", 0)
    user_email = session.get("email", "")
    result = change_status(ticket_id, new_status, emp_id, request.remote_addr or "", is_admin=_is_admin(), user_email=user_email)

    # If called via AJAX, return JSON
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if result.success:
            return jsonify({"ok": True, "status": new_status})
        return jsonify({"ok": False, "errors": result.errors}), 422

    if not result.success:
        for err in result.errors:
            flash(err, "danger")
    else:
        flash(f"Status changed to {new_status}.", "success")

    return redirect(url_for("it_support.detail", ticket_id=ticket_id))


# ── Delete ──────────────────────────────────────────────────────────

@it_support_bp.route("/<int:ticket_id>/delete", methods=["POST"])
@login_required
def delete(ticket_id: int):
    emp_id = session.get("emp_id", 0)
    user_email = session.get("email", "")
    result = remove_ticket(ticket_id, emp_id, request.remote_addr or "", is_admin=_is_admin(), user_email=user_email)

    if not result.success:
        for err in result.errors:
            flash(err, "danger")
        return redirect(url_for("it_support.detail", ticket_id=ticket_id))

    flash("Ticket deleted.", "info")
    return redirect(url_for("it_support.index"))
