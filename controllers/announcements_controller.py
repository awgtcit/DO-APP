"""Controller – Announcements blueprint."""

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, abort,
)
from auth.middleware import login_required
from services import announcements_service as svc

announcements_bp = Blueprint(
    "announcements", __name__,
    url_prefix="/announcements",
    template_folder="../templates",
)


def _require_admin():
    if not svc.is_announcements_admin():
        abort(403)


# ─── List ────────────────────────────────────────────────────────
@announcements_bp.route("/")
@login_required
def index():
    cat_id = request.args.get("category", type=int)
    page = request.args.get("page", 1, type=int)
    q = request.args.get("search", "").strip() or request.args.get("q", "").strip()

    categories = svc.list_categories()
    announcements, meta = svc.list_announcements(
        category_id=cat_id, page=page, search=q or None
    )
    # Decode body snippets for card view
    import html as _html
    for a in announcements:
        raw = a.get("AnnouncementBody") or ""
        try:
            a["body_preview"] = _html.unescape(_html.unescape(raw))
        except Exception:
            a["body_preview"] = raw

    is_admin = svc.is_announcements_admin()

    return render_template(
        "announcements/list.html",
        announcements=announcements,
        categories=categories,
        meta=meta,
        current_category=cat_id,
        search_query=q,
        is_admin=is_admin,
    )


# ─── Detail ──────────────────────────────────────────────────────
@announcements_bp.route("/<int:ann_id>")
@login_required
def detail(ann_id):
    ann = svc.get_announcement(ann_id)
    if not ann:
        flash("Announcement not found.", "error")
        return redirect(url_for("announcements.index"))

    return render_template(
        "announcements/detail.html",
        ann=ann,
        is_admin=svc.is_announcements_admin(),
    )


# ─── Create (GET) ───────────────────────────────────────────────
@announcements_bp.route("/create")
@login_required
def create_form():
    _require_admin()
    categories = svc.list_categories()
    return render_template(
        "announcements/form.html",
        ann=None,
        categories=categories,
        form={},
    )


# ─── Create (POST) ──────────────────────────────────────────────
@announcements_bp.route("/create", methods=["POST"])
@login_required
def create_post():
    _require_admin()
    form_data = {
        "category_id": request.form.get("category_id", type=int),
        "subject": request.form.get("subject", "").strip(),
        "body": request.form.get("body", ""),
    }
    if not form_data["subject"]:
        flash("Subject is required.", "error")
        return render_template(
            "announcements/form.html",
            ann=None,
            categories=svc.list_categories(),
            form=form_data,
        )
    from services.admin_settings_service import check_text_for_restricted_words
    blocked = check_text_for_restricted_words(form_data["subject"])
    if not blocked and form_data.get("body"):
        blocked = check_text_for_restricted_words(form_data["body"])
    if blocked:
        flash(f"Text contains blocked word(s): {', '.join(blocked)}", "error")
        return render_template(
            "announcements/form.html",
            ann=None,
            categories=svc.list_categories(),
            form=form_data,
        )
    if not form_data["category_id"]:
        flash("Category is required.", "error")
        return render_template(
            "announcements/form.html",
            ann=None,
            categories=svc.list_categories(),
            form=form_data,
        )

    files = request.files.getlist("files")
    ann_id = svc.create_announcement(form_data, files)
    flash("Announcement created successfully.", "success")
    return redirect(url_for("announcements.detail", ann_id=int(ann_id)))


# ─── Edit (GET) ──────────────────────────────────────────────────
@announcements_bp.route("/<int:ann_id>/edit")
@login_required
def edit_form(ann_id):
    _require_admin()
    ann = svc.get_announcement(ann_id)
    if not ann:
        flash("Announcement not found.", "error")
        return redirect(url_for("announcements.index"))
    categories = svc.list_categories()
    return render_template(
        "announcements/form.html",
        ann=ann,
        categories=categories,
        form={},
    )


# ─── Edit (POST) ─────────────────────────────────────────────────
@announcements_bp.route("/<int:ann_id>/edit", methods=["POST"])
@login_required
def edit_post(ann_id):
    _require_admin()
    form_data = {
        "category_id": request.form.get("category_id", type=int),
        "subject": request.form.get("subject", "").strip(),
        "body": request.form.get("body", ""),
    }
    if not form_data["subject"]:
        flash("Subject is required.", "error")
        ann = svc.get_announcement(ann_id)
        return render_template(
            "announcements/form.html",
            ann=ann,
            categories=svc.list_categories(),
            form=form_data,
        )

    files = request.files.getlist("files")
    ok, msg = svc.update_announcement(ann_id, form_data, files)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("announcements.detail", ann_id=ann_id))


# ─── Delete ──────────────────────────────────────────────────────
@announcements_bp.route("/<int:ann_id>/delete", methods=["POST"])
@login_required
def delete(ann_id):
    _require_admin()
    if svc.delete_announcement_by_id(ann_id):
        flash("Announcement deleted.", "success")
    else:
        flash("Announcement not found.", "error")
    return redirect(url_for("announcements.index"))


# ─── Admin: Add Category ────────────────────────────────────────
@announcements_bp.route("/admin/category", methods=["POST"])
@login_required
def add_category():
    _require_admin()
    name = request.form.get("name", "").strip()
    if not name:
        flash("Category name is required.", "error")
    else:
        svc.create_category(name)
        flash(f"Category '{name}' created.", "success")
    return redirect(url_for("announcements.index"))
