"""Controller – Facility requests blueprint."""

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, abort,
)
from auth.middleware import login_required
from services import facility_service as svc
from repos.facility_repo import SITES

facility_bp = Blueprint(
    "facility", __name__,
    url_prefix="/facility",
    template_folder="../templates",
)


# ─── Dashboard / list ────────────────────────────────────────────
@facility_bp.route("/")
@login_required
def index():
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "").strip() or None
    q = request.args.get("q", "").strip() or None

    admin = svc.is_facility_admin()
    emp_id = None if admin else session.get("emp_id")
    stats = svc.get_dashboard(emp_id=emp_id)
    requests_list, meta = svc.list_requests(page=page, status=status, search=q)

    return render_template(
        "facility/list.html",
        requests=requests_list,
        stats=stats,
        meta=meta,
        current_status=status,
        search_query=q,
        is_admin=admin,
    )


# ─── Create (GET) ───────────────────────────────────────────────
@facility_bp.route("/create")
@login_required
def create_form():
    return render_template(
        "facility/form.html",
        sites=SITES,
        form={},
    )


# ─── Create (POST) ──────────────────────────────────────────────
@facility_bp.route("/create", methods=["POST"])
@login_required
def create_post():
    form_data = {
        "subject": request.form.get("subject", "").strip(),
        "site": request.form.get("site", ""),
        "summary": request.form.get("summary", ""),
    }
    if not form_data["subject"] or len(form_data["subject"]) < 4:
        flash("Subject must be at least 4 characters.", "error")
        return render_template(
            "facility/form.html",
            sites=SITES,
            form=form_data,
        )
    from services.admin_settings_service import check_text_for_restricted_words
    blocked = check_text_for_restricted_words(form_data["subject"])
    if not blocked and form_data.get("summary"):
        blocked = check_text_for_restricted_words(form_data["summary"])
    if blocked:
        flash(f"Text contains blocked word(s): {', '.join(blocked)}", "error")
        return render_template(
            "facility/form.html",
            sites=SITES,
            form=form_data,
        )
    files = request.files.getlist("files")
    req_id = svc.create_request(form_data, files)
    flash("Facility request created successfully.", "success")
    return redirect(url_for("facility.detail", req_id=req_id))


# ─── Detail ──────────────────────────────────────────────────────
@facility_bp.route("/<int:req_id>")
@login_required
def detail(req_id):
    req, comments = svc.get_request_detail(req_id)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("facility.index"))
    if not svc.can_view(req):
        abort(403)

    return render_template(
        "facility/detail.html",
        req=req,
        comments=comments,
        is_admin=svc.is_facility_admin(),
    )


# ─── Close request ──────────────────────────────────────────────
@facility_bp.route("/<int:req_id>/close", methods=["POST"])
@login_required
def close(req_id):
    reason = request.form.get("reason", "").strip()
    if not reason:
        flash("A reason is required to close the request.", "error")
        return redirect(url_for("facility.detail", req_id=req_id))

    svc.close_request(req_id, reason)
    flash("Request closed.", "success")
    return redirect(url_for("facility.detail", req_id=req_id))


# ─── Re-open request ────────────────────────────────────────────
@facility_bp.route("/<int:req_id>/reopen", methods=["POST"])
@login_required
def reopen(req_id):
    reason = request.form.get("reason", "").strip()
    if not reason:
        flash("A reason is required to re-open the request.", "error")
        return redirect(url_for("facility.detail", req_id=req_id))

    svc.reopen_request(req_id, reason)
    flash("Request re-opened.", "success")
    return redirect(url_for("facility.detail", req_id=req_id))


# ─── Add comment ────────────────────────────────────────────────
@facility_bp.route("/<int:req_id>/comment", methods=["POST"])
@login_required
def add_comment(req_id):
    desc = request.form.get("description", "").strip()
    if not desc:
        flash("Comment cannot be empty.", "error")
    else:
        svc.add_comment(req_id, desc)
        flash("Comment added.", "success")
    return redirect(url_for("facility.detail", req_id=req_id))
