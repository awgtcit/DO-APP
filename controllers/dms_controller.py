"""
DMS controller — full CRUD + workflow for the Document Management System.
Routes: /documents (department grid), /documents/<dept_id> (doc list),
        /documents/doc/<id> (detail), /documents/doc/create, etc.
"""

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, jsonify,
)
from auth.middleware import login_required
from services.dms_service import (
    dms_department_grid,
    dms_global_stats,
    list_documents,
    get_document_detail,
    create_new_document,
    update_existing_document,
    change_document_status,
    add_document_attachment,
    remove_document_attachment,
    get_form_lookups,
    can_user_access_department,
    get_user_permissions_summary,
    admin_create_department,
    admin_create_document_type,
    admin_create_company,
    admin_create_party,
    is_dms_itadmin,
)
from services.upload_service import save_upload
from rules.dms_rules import STATUS_LABELS

dms_bp = Blueprint(
    "dms",
    __name__,
    url_prefix="/documents",
)


# ── Department grid (entry point) ──────────────────────────────

@dms_bp.route("/")
@login_required
def departments():
    """DMS department card grid."""
    emp_id = session.get("emp_id")
    depts = dms_department_grid(emp_id)
    stats = dms_global_stats()
    perms = get_user_permissions_summary(emp_id)
    return render_template(
        "dms/departments.html",
        departments=depts,
        stats=stats,
        permissions=perms,
    )


# ── Document list per department ────────────────────────────────

@dms_bp.route("/<int:dept_id>")
@login_required
def document_list(dept_id):
    """List documents in a department."""
    emp_id = session.get("emp_id")
    if not can_user_access_department(emp_id, dept_id):
        flash("You do not have access to this department.", "danger")
        return redirect(url_for("dms.departments"))

    status_filter = request.args.get("status")
    status_id = int(status_filter) if status_filter and status_filter.isdigit() else None
    page = int(request.args.get("page", 1))
    search = request.args.get("search", "").strip() or None

    docs, total = list_documents(
        dept_id=dept_id, emp_id=emp_id,
        status_id=status_id, page=page, search=search,
    )
    per_page = 25
    total_pages = max(1, (total + per_page - 1) // per_page)

    lookups = get_form_lookups()
    perms = get_user_permissions_summary(emp_id)

    return render_template(
        "dms/document_list.html",
        documents=docs,
        dept_id=dept_id,
        dept_name=next((d["Name"] for d in lookups["departments"] if d["id"] == dept_id), f"Dept {dept_id}"),
        total=total,
        page=page,
        total_pages=total_pages,
        search=search or "",
        status_filter=status_id,
        status_labels=STATUS_LABELS,
        permissions=perms,
    )


# ── Create document ────────────────────────────────────────────

@dms_bp.route("/<int:dept_id>/create", methods=["GET"])
@login_required
def create_form(dept_id):
    """Show create document form."""
    emp_id = session.get("emp_id")
    if not can_user_access_department(emp_id, dept_id):
        flash("You do not have access to this department.", "danger")
        return redirect(url_for("dms.departments"))

    lookups = get_form_lookups()
    return render_template(
        "dms/document_form.html",
        mode="create",
        dept_id=dept_id,
        lookups=lookups,
        form={},
    )


@dms_bp.route("/<int:dept_id>/create", methods=["POST"])
@login_required
def create_post(dept_id):
    """Process create document form."""
    emp_id = session.get("emp_id")
    data = {
        "name": request.form.get("name", "").strip(),
        "description": request.form.get("description", "").strip(),
        "valid_from": request.form.get("valid_from") or None,
        "valid_to": request.form.get("valid_to") or None,
        "dept_id": dept_id,
        "doc_type_id": request.form.get("doc_type_id"),
        "company_id": request.form.get("company_id") or None,
        "party_id": request.form.get("party_id") or None,
        "confidential": request.form.get("confidential") == "1",
        "created_by": emp_id,
    }

    new_id, errors = create_new_document(data)
    if errors:
        for field, msg in errors.items():
            flash(msg, "danger")
        lookups = get_form_lookups()
        return render_template(
            "dms/document_form.html",
            mode="create", dept_id=dept_id, lookups=lookups, form=data,
        )

    # Handle file attachment if provided
    if "attachment" in request.files:
        file = request.files["attachment"]
        if file and file.filename:
            upload = save_upload(file, "dms")
            if upload:
                add_document_attachment({
                    "document_id": new_id,
                    "name": upload["filename"],
                    "description": upload["original_name"],
                    "valid_from": data.get("valid_from"),
                    "valid_to": data.get("valid_to"),
                    "created_by": emp_id,
                })

    flash("Document created successfully.", "success")
    return redirect(url_for("dms.document_detail", doc_id=new_id))


# ── Document detail ─────────────────────────────────────────────

@dms_bp.route("/doc/<int:doc_id>")
@login_required
def document_detail(doc_id):
    """Show full document detail with actions."""
    emp_id = session.get("emp_id")
    doc = get_document_detail(doc_id, emp_id)
    if not doc:
        flash("Document not found.", "danger")
        return redirect(url_for("dms.departments"))

    return render_template("dms/document_detail.html", doc=doc)


# ── Edit document ───────────────────────────────────────────────

@dms_bp.route("/doc/<int:doc_id>/edit", methods=["GET"])
@login_required
def edit_form(doc_id):
    """Show edit form for a DRAFT document."""
    emp_id = session.get("emp_id")
    doc = get_document_detail(doc_id, emp_id)
    if not doc:
        flash("Document not found.", "danger")
        return redirect(url_for("dms.departments"))
    if not doc.get("can_edit"):
        flash("Only Draft documents can be edited.", "warning")
        return redirect(url_for("dms.document_detail", doc_id=doc_id))

    lookups = get_form_lookups()
    return render_template(
        "dms/document_form.html",
        mode="edit", doc=doc, dept_id=doc["DeptID"], lookups=lookups, form=doc,
    )


@dms_bp.route("/doc/<int:doc_id>/edit", methods=["POST"])
@login_required
def edit_post(doc_id):
    """Process edit document form."""
    emp_id = session.get("emp_id")
    data = {
        "name": request.form.get("name", "").strip(),
        "description": request.form.get("description", "").strip(),
        "valid_from": request.form.get("valid_from") or None,
        "valid_to": request.form.get("valid_to") or None,
        "doc_type_id": request.form.get("doc_type_id"),
        "company_id": request.form.get("company_id") or None,
        "party_id": request.form.get("party_id") or None,
        "confidential": request.form.get("confidential") == "1",
        "modified_by": emp_id,
    }

    ok, errors = update_existing_document(doc_id, data)
    if errors:
        for field, msg in errors.items():
            flash(msg, "danger")
        return redirect(url_for("dms.edit_form", doc_id=doc_id))

    flash("Document updated.", "success")
    return redirect(url_for("dms.document_detail", doc_id=doc_id))


# ── Status transition ──────────────────────────────────────────

@dms_bp.route("/doc/<int:doc_id>/status", methods=["POST"])
@login_required
def change_status(doc_id):
    """Change document status (submit, approve, reject, finalize, cancel)."""
    emp_id = session.get("emp_id")
    new_status = request.form.get("new_status")
    remarks = request.form.get("remarks", "").strip()

    if not new_status or not new_status.isdigit():
        flash("Invalid status.", "danger")
        return redirect(url_for("dms.document_detail", doc_id=doc_id))

    ok, message = change_document_status(doc_id, int(new_status), emp_id, remarks)
    flash(message, "success" if ok else "danger")
    return redirect(url_for("dms.document_detail", doc_id=doc_id))


# ── Attachment management ───────────────────────────────────────

@dms_bp.route("/doc/<int:doc_id>/attachments", methods=["POST"])
@login_required
def upload_attachment(doc_id):
    """Upload a new attachment to a document."""
    emp_id = session.get("emp_id")

    if "attachment" not in request.files:
        flash("No file selected.", "warning")
        return redirect(url_for("dms.document_detail", doc_id=doc_id))

    file = request.files["attachment"]
    upload = save_upload(file, "dms")
    if not upload:
        flash("Invalid file type or empty file.", "danger")
        return redirect(url_for("dms.document_detail", doc_id=doc_id))

    add_document_attachment({
        "document_id": doc_id,
        "name": upload["filename"],
        "description": upload["original_name"],
        "valid_from": request.form.get("att_valid_from") or None,
        "valid_to": request.form.get("att_valid_to") or None,
        "created_by": emp_id,
    })

    flash("Attachment uploaded.", "success")
    return redirect(url_for("dms.document_detail", doc_id=doc_id))


@dms_bp.route("/doc/<int:doc_id>/attachments/<int:att_id>/delete", methods=["POST"])
@login_required
def delete_attachment_route(doc_id, att_id):
    """Delete (soft) an attachment."""
    if remove_document_attachment(att_id):
        flash("Attachment removed.", "success")
    else:
        flash("Could not remove attachment.", "danger")
    return redirect(url_for("dms.document_detail", doc_id=doc_id))


# ── Admin config ────────────────────────────────────────────────

@dms_bp.route("/admin")
@login_required
def admin_config():
    """Admin configuration page for lookup tables."""
    emp_id = session.get("emp_id")
    if not is_dms_itadmin(emp_id):
        flash("Admin access required.", "danger")
        return redirect(url_for("dms.departments"))

    lookups = get_form_lookups()
    return render_template("dms/admin_config.html", lookups=lookups)


@dms_bp.route("/admin/add", methods=["POST"])
@login_required
def admin_add():
    """Add a new lookup item (department, doc type, company, party)."""
    emp_id = session.get("emp_id")
    if not is_dms_itadmin(emp_id):
        flash("Admin access required.", "danger")
        return redirect(url_for("dms.departments"))

    item_type = request.form.get("item_type")
    name = request.form.get("name", "").strip()

    if not name:
        flash("Name is required.", "danger")
        return redirect(url_for("dms.admin_config"))

    try:
        if item_type == "department":
            admin_create_department(name, emp_id)
        elif item_type == "document_type":
            admin_create_document_type(name, emp_id)
        elif item_type == "company":
            admin_create_company(name, emp_id)
        elif item_type == "party":
            admin_create_party(name, emp_id)
        else:
            flash("Unknown item type.", "danger")
            return redirect(url_for("dms.admin_config"))
        flash(f"{item_type.replace('_', ' ').title()} '{name}' created.", "success")
    except Exception as exc:
        flash(f"Error: {exc}", "danger")

    return redirect(url_for("dms.admin_config"))
