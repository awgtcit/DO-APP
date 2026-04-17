"""
Delivery Order controller — full CRUD for Sales/Delivery Orders.
Dashboard, create wizard, list, detail, status transitions, items,
QR code generation, print view, attachments.

Role-based access is enforced via do_permission_service.
"""

import io
import json
import mimetypes
import os

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, jsonify, send_file, abort, Response,
)
from werkzeug.utils import secure_filename
from auth.middleware import login_required
from services.delivery_order_service import (
    do_dashboard_stats,
    list_orders,
    get_order_detail,
    get_form_lookups,
    create_new_order,
    update_existing_order,
    change_order_status,
    add_item_to_order,
    remove_item_from_order,
    add_attachment,
    remove_attachment,
    get_attachment,
    build_qr_payload,
    save_logistics_fields,
    save_sales_fields,
    STATUS_OPTIONS,
)
from services.do_permission_service import (
    get_do_context,
    can_create_order,
    can_edit_order,
    can_transition,
    REJECT_REASONS,
)
from services.admin_settings_service import check_text_for_restricted_words


# Text fields in DO forms to validate against restricted words
_DO_TEXT_FIELDS = [
    ("payment_terms", "Payment Terms"),
    ("point_of_discharge", "Point of Discharge"),
    ("final_destination", "Final Destination"),
    ("notify_party", "Notify Party"),
    ("shipping_agent", "Shipping Agent"),
]

# All fields required to create / edit a delivery order
_REQUIRED_FIELDS = {
    "po_date": "Date",
    "on_behalf_of": "On Behalf Of",
    "loading_date": "Loading Date",
    "delivery_terms": "Delivery Terms",
    "payment_terms": "Payment Terms",
    "transportation_mode": "Transportation Mode",
    "bill_to": "Bill To",
    "ship_to": "Ship To",
    "point_of_exit": "Point of Exit",
    "point_of_discharge": "Point of Discharge",
    "final_destination": "Final Destination",
    "currency": "Currency",
    "notify_party": "Notify Party",
    "shipping_agent": "Shipping Agent",
}


def _check_restricted_words(data: dict) -> str | None:
    """Return flash message if any DO text field contains a restricted word."""
    for field_key, field_label in _DO_TEXT_FIELDS:
        val = (data.get(field_key) or "").strip()
        if val:
            blocked = check_text_for_restricted_words(val)
            if blocked:
                return f"{field_label} contains blocked word(s): {', '.join(blocked)}"
    return None


def _save_uploaded_files(files, order_id: int, emp_id) -> None:
    """Save a list of uploaded files as order attachments."""
    for f in files:
        safe_name = secure_filename(f.filename)
        file_bytes = f.read()
        content_type = (
            f.content_type
            or mimetypes.guess_type(safe_name)[0]
            or "application/octet-stream"
        )
        add_attachment({
            "order_id": order_id,
            "file_name": safe_name,
            "web_path": "",
            "dir_path": "",
            "file_data": file_bytes,
            "content_type": content_type,
            "uploaded_by": emp_id,
        })

do_bp = Blueprint(
    "delivery_orders",
    __name__,
    url_prefix="/delivery-orders",
)


# ── Dashboard ───────────────────────────────────────────────────

@do_bp.route("/")
@login_required
def dashboard():
    """Delivery Order dashboard with KPI bubbles."""
    stats = do_dashboard_stats()
    ctx = get_do_context()
    return render_template("delivery_orders/dashboard.html", stats=stats, **ctx)


# ── Order list ──────────────────────────────────────────────────

@do_bp.route("/orders")
@login_required
def order_list():
    """List delivery orders with filter & pagination."""
    status = request.args.get("status", "ALL")
    page = int(request.args.get("page", 1))
    search = request.args.get("search", "").strip() or None

    orders, total = list_orders(status=status, page=page, search=search)
    per_page = 25
    total_pages = max(1, (total + per_page - 1) // per_page)

    ctx = get_do_context()
    return render_template(
        "delivery_orders/order_list.html",
        orders=orders,
        total=total,
        current_status=status,
        status_options=STATUS_OPTIONS,
        page=page,
        total_pages=total_pages,
        search=search or "",
        **ctx,
    )


# ── Create order ────────────────────────────────────────────────

@do_bp.route("/create", methods=["GET"])
@login_required
def create_form():
    """Show the create delivery order form."""
    if not can_create_order():
        flash("You do not have permission to create orders.", "warning")
        return redirect(url_for("delivery_orders.dashboard"))

    lookups = get_form_lookups()
    ctx = get_do_context()
    return render_template(
        "delivery_orders/create.html",
        lookups=lookups,
        form={},
        **ctx,
    )


@do_bp.route("/create", methods=["POST"])
@login_required
def create_post():
    """Process the create delivery order form."""
    if not can_create_order():
        flash("You do not have permission to create orders.", "warning")
        return redirect(url_for("delivery_orders.dashboard"))

    data = {
        "po_date":              request.form.get("po_date"),
        "loading_date":         request.form.get("loading_date"),
        "on_behalf_of":         request.form.get("on_behalf_of"),
        "delivery_terms":       request.form.get("delivery_terms"),
        "payment_terms":        request.form.get("payment_terms"),
        "transportation_mode":  request.form.get("transportation_mode"),
        "bill_to":              request.form.get("bill_to"),
        "ship_to":              request.form.get("ship_to"),
        "point_of_exit":        request.form.get("point_of_exit"),
        "point_of_discharge":   request.form.get("point_of_discharge"),
        "final_destination":    request.form.get("final_destination"),
        "notify_party":         request.form.get("notify_party"),
        "shipping_agent":       request.form.get("shipping_agent"),
        "currency":             request.form.get("currency", "USD"),
        "created_by":           session.get("emp_id"),
    }

    missing = [label for key, label in _REQUIRED_FIELDS.items()
               if not (data.get(key) or "").strip()]
    if missing:
        flash(f"The following fields are required: {', '.join(missing)}.", "danger")
        lookups = get_form_lookups()
        ctx = get_do_context()
        return render_template("delivery_orders/create.html", lookups=lookups, form=data, **ctx)

    # ── Restricted word check ──────────────────────────────────
    rw_error = _check_restricted_words(data)
    if rw_error:
        flash(rw_error, "danger")
        lookups = get_form_lookups()
        ctx = get_do_context()
        return render_template("delivery_orders/create.html", lookups=lookups, form=data, **ctx)

    try:
        new_id = create_new_order(data)
        flash("Delivery Order created successfully.", "success")
        return redirect(url_for("delivery_orders.order_detail", order_id=new_id))
    except Exception as exc:
        flash(f"Error creating order: {exc}", "danger")
        lookups = get_form_lookups()
        ctx = get_do_context()
        return render_template("delivery_orders/create.html", lookups=lookups, form=data, **ctx)


# ── Order detail ────────────────────────────────────────────────

@do_bp.route("/<int:order_id>")
@login_required
def order_detail(order_id):
    """Show full order detail with items."""
    order = get_order_detail(order_id)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("delivery_orders.order_list"))

    ctx = get_do_context()
    return render_template("delivery_orders/detail.html", order=order, **ctx)


# ── Edit order ──────────────────────────────────────────────────

@do_bp.route("/<int:order_id>/edit", methods=["GET"])
@login_required
def edit_form(order_id):
    """Show the edit delivery order form."""
    order = get_order_detail(order_id)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("delivery_orders.order_list"))

    if not can_edit_order(order):
        flash("You do not have permission to edit this order.", "warning")
        return redirect(url_for("delivery_orders.order_detail", order_id=order_id))

    lookups = get_form_lookups()
    ctx = get_do_context()
    return render_template(
        "delivery_orders/edit.html",
        order=order,
        lookups=lookups,
        **ctx,
    )


@do_bp.route("/<int:order_id>/edit", methods=["POST"])
@login_required
def edit_post(order_id):
    """Process the edit delivery order form."""
    order = get_order_detail(order_id)
    if not order or not can_edit_order(order):
        flash("You do not have permission to edit this order.", "warning")
        return redirect(url_for("delivery_orders.order_detail", order_id=order_id))

    data = {
        "po_date":              request.form.get("po_date"),
        "loading_date":         request.form.get("loading_date"),
        "on_behalf_of":         request.form.get("on_behalf_of"),
        "delivery_terms":       request.form.get("delivery_terms"),
        "payment_terms":        request.form.get("payment_terms"),
        "transportation_mode":  request.form.get("transportation_mode"),
        "bill_to":              request.form.get("bill_to"),
        "ship_to":              request.form.get("ship_to"),
        "point_of_exit":        request.form.get("point_of_exit"),
        "point_of_discharge":   request.form.get("point_of_discharge"),
        "final_destination":    request.form.get("final_destination"),
        "notify_party":         request.form.get("notify_party"),
        "shipping_agent":       request.form.get("shipping_agent"),
        "currency":             request.form.get("currency", "USD"),
        "modified_by":          session.get("emp_id"),
    }

    # ── Required field check ────────────────────────────────────
    missing = [label for key, label in _REQUIRED_FIELDS.items()
               if not (data.get(key) or "").strip()]
    if missing:
        flash(f"The following fields are required: {', '.join(missing)}.", "danger")
        return redirect(url_for("delivery_orders.edit_form", order_id=order_id))

    # ── Restricted word check ──────────────────────────────────
    rw_error = _check_restricted_words(data)

    try:
        update_existing_order(order_id, data)
        flash("Order updated successfully.", "success")
        return redirect(url_for("delivery_orders.order_detail", order_id=order_id))
    except Exception as exc:
        flash(f"Error updating order: {exc}", "danger")
        return redirect(url_for("delivery_orders.edit_form", order_id=order_id))


# ── Status transitions ─────────────────────────────────────────

@do_bp.route("/<int:order_id>/status", methods=["POST"])
@login_required
def change_status(order_id):
    """Change the status of a delivery order with permission checks."""
    new_status = request.form.get("new_status", "").strip()
    emp_id = session.get("emp_id")
    reject_reason = request.form.get("reject_reason", "").strip() or None
    reject_remarks = request.form.get("reject_remarks", "").strip() or None

    if not new_status:
        flash("No status specified.", "danger")
        return redirect(url_for("delivery_orders.order_detail", order_id=order_id))

    ok, errors = change_order_status(order_id, new_status, emp_id, reject_reason, reject_remarks)
    if ok:
        flash(f"Order status changed to {new_status}.", "success")
    else:
        for err in errors:
            flash(err, "warning")
        if not errors:
            flash("Status transition not allowed or you lack permission.", "warning")

    return redirect(url_for("delivery_orders.order_detail", order_id=order_id))


# ── Add item ────────────────────────────────────────────────────

@do_bp.route("/<int:order_id>/items", methods=["POST"])
@login_required
def add_item(order_id):
    """Add a line item to the order."""
    order = get_order_detail(order_id)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("delivery_orders.order_list"))

    if not can_edit_order(order):
        flash("Cannot add items to this order.", "warning")
        return redirect(url_for("delivery_orders.order_detail", order_id=order_id))

    data = {
        "po_number":        order.get("PO_Number"),
        "product_id":       request.form.get("product_id"),
        "quantity":          request.form.get("quantity", 0),
        "unit_price":        request.form.get("unit_price", 0),
        "currency":          request.form.get("currency", order.get("DOCurrency", "USD")),
        "container":         request.form.get("container", ""),
        "truck":             request.form.get("truck", ""),
        "loading_sequence":  request.form.get("loading_sequence", 0),
        "remarks":           request.form.get("remarks", ""),
        "created_by":        session.get("emp_id"),
    }

    try:
        add_item_to_order(data)
        flash("Item added successfully.", "success")
    except Exception as exc:
        flash(f"Error adding item: {exc}", "danger")

    return redirect(url_for("delivery_orders.order_detail", order_id=order_id))


@do_bp.route("/<int:order_id>/items/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(order_id, item_id):
    """Delete a line item from the order."""
    order = get_order_detail(order_id)
    if not order or not can_edit_order(order):
        flash("Cannot remove items from this order.", "warning")
        return redirect(url_for("delivery_orders.order_detail", order_id=order_id))

    if remove_item_from_order(item_id):
        flash("Item removed.", "success")
    else:
        flash("Could not remove item.", "danger")
    return redirect(url_for("delivery_orders.order_detail", order_id=order_id))


# ── Post-delivery tracking fields ──────────────────────────────

@do_bp.route("/<int:order_id>/logistics-fields", methods=["POST"])
@login_required
def update_logistics(order_id):
    """Save Fujairah Logistics Team post-delivery fields with mandatory document uploads."""
    order = get_order_detail(order_id)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("delivery_orders.order_list"))

    # Only logistics or approver can update these fields
    ctx = get_do_context()
    if not (ctx["is_do_logistics"] or ctx["is_do_admin"]):
        flash("Only the Logistics team can update these fields.", "warning")
        return redirect(url_for("delivery_orders.order_detail", order_id=order_id))

    # Only on confirmed/need-attachment orders
    if order.get("Status") not in ("CONFIRMED", "NEED ATTACHMENT"):
        flash("These fields can only be updated on confirmed orders.", "warning")
        return redirect(url_for("delivery_orders.order_detail", order_id=order_id))

    # Mandatory file upload validation
    files = request.files.getlist("logistics_attachments")
    valid_files = [f for f in files if f and f.filename]
    if not valid_files:
        flash("At least one document must be uploaded.", "danger")
        return redirect(url_for("delivery_orders.order_detail", order_id=order_id))

    data = {
        "exit_document_number":     request.form.get("exit_document_number", "").strip(),
        "fta_declaration_number":   request.form.get("fta_declaration_number", "").strip(),
        "sap_sales_invoice_number": request.form.get("sap_sales_invoice_number", "").strip(),
    }

    try:
        emp_id = session.get("emp_id")
        # Save fields and change status to CUSTOMS DOCUMENT UPDATED
        save_logistics_fields(order_id, data, emp_id, "CUSTOMS DOCUMENT UPDATED")

        # Save all uploaded files
        _save_uploaded_files(valid_files, order_id, emp_id)

        flash("Customs documents uploaded and status updated to CUSTOMS DOCUMENT UPDATED.", "success")
    except Exception as exc:
        flash(f"Error updating logistics fields: {exc}", "danger")

    return redirect(url_for("delivery_orders.order_detail", order_id=order_id))


@do_bp.route("/<int:order_id>/sales-fields", methods=["POST"])
@login_required
def update_sales(order_id):
    """Save Sales Team post-delivery fields with mandatory document uploads."""
    order = get_order_detail(order_id)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("delivery_orders.order_list"))

    # Creator (owner) or approver can update sales fields
    ctx = get_do_context()
    emp_id = session.get("emp_id")
    is_owner = str(order.get("Created_by")) == str(emp_id)
    if not (is_owner or ctx["is_do_admin"] or ctx["is_do_creator"]):
        flash("Only the Sales team can update these fields.", "warning")
        return redirect(url_for("delivery_orders.order_detail", order_id=order_id))

    # Only on CUSTOMS DOCUMENT UPDATED status
    if order.get("Status") != "CUSTOMS DOCUMENT UPDATED":
        flash("These fields can only be updated after customs documents are uploaded.", "warning")
        return redirect(url_for("delivery_orders.order_detail", order_id=order_id))

    # Mandatory file upload validation
    files = request.files.getlist("sales_attachments")
    valid_files = [f for f in files if f and f.filename]
    if not valid_files:
        flash("At least one document must be uploaded.", "danger")
        return redirect(url_for("delivery_orders.order_detail", order_id=order_id))

    data = {
        "customs_boe_number": request.form.get("customs_boe_number", "").strip(),
        "airway_bill_number": request.form.get("airway_bill_number", "").strip(),
        "iec_code":           request.form.get("iec_code", "").strip(),
    }

    try:
        # Save fields and change status to DELIVERED
        save_sales_fields(order_id, data, emp_id, "DELIVERED")

        # Save all uploaded files
        _save_uploaded_files(valid_files, order_id, emp_id)

        flash("Delivery documents uploaded and status updated to DELIVERED.", "success")
    except Exception as exc:
        flash(f"Error updating sales fields: {exc}", "danger")

    return redirect(url_for("delivery_orders.order_detail", order_id=order_id))


# ── Attachments ─────────────────────────────────────────────────

@do_bp.route("/<int:order_id>/attachments", methods=["POST"])
@login_required
def upload_attachment(order_id):
    """Upload an attachment for NEED ATTACHMENT status orders."""
    order = get_order_detail(order_id)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("delivery_orders.order_list"))

    file = request.files.get("attachment")
    if not file or not file.filename:
        flash("No file selected.", "danger")
        return redirect(url_for("delivery_orders.order_detail", order_id=order_id))

    import mimetypes
    from werkzeug.utils import secure_filename
    safe_name = secure_filename(file.filename)
    file_bytes = file.read()
    content_type = file.content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"

    try:
        add_attachment({
            "order_id": order_id,
            "file_name": safe_name,
            "web_path": "",
            "dir_path": "",
            "file_data": file_bytes,
            "content_type": content_type,
            "uploaded_by": session.get("emp_id"),
        })
        flash("Attachment uploaded successfully.", "success")
    except Exception as exc:
        flash(f"Error uploading attachment: {exc}", "danger")

    return redirect(url_for("delivery_orders.order_detail", order_id=order_id))


@do_bp.route("/<int:order_id>/attachments/<int:att_id>/delete", methods=["POST"])
@login_required
def delete_attachment(order_id, att_id):
    """Delete an attachment."""
    if remove_attachment(att_id):
        flash("Attachment removed.", "success")
    else:
        flash("Could not remove attachment.", "danger")
    return redirect(url_for("delivery_orders.order_detail", order_id=order_id))


@do_bp.route("/<int:order_id>/attachments/<int:att_id>/view")
@login_required
def view_attachment(order_id, att_id):
    """Serve an attachment file from the database."""
    att = get_attachment(att_id)
    if not att or att.get("SalesOrder_ID") != order_id:
        abort(404)

    file_data = att.get("FileData")
    if not file_data:
        abort(404)

    content_type = att.get("ContentType") or "application/octet-stream"
    return send_file(
        io.BytesIO(file_data),
        mimetype=content_type,
        as_attachment=False,
        download_name=att.get("FileName", "attachment"),
    )


# ── QR Code ─────────────────────────────────────────────────────

@do_bp.route("/<int:order_id>/qrcode")
@login_required
def qr_code(order_id):
    """Generate a QR code image for a confirmed order."""
    order = get_order_detail(order_id)
    if not order:
        abort(404)

    if order.get("Status") not in ("CONFIRMED", "PRICE AGREED", "NEED ATTACHMENT"):
        abort(400, "QR code only available for confirmed+ orders")

    try:
        import qrcode as qrcode_lib
    except ImportError:
        abort(500, "qrcode package not installed")

    try:
        payload = build_qr_payload(order)
        if not payload:
            abort(500, "Failed to build QR payload")

        payload_json = json.dumps(payload, separators=(",", ":"))

        qr = qrcode_lib.QRCode(version=1, box_size=8, border=2)
        qr.add_data(payload_json)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf_data = buf.getvalue()

        response = Response(buf_data, mimetype="image/png")
        response.headers['Content-Disposition'] = f'inline; filename="DO_{order_id}_qr.png"'
        return response
    except Exception as exc:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"QR code generation error for order {order_id}: {exc}\n{traceback.format_exc()}")
        abort(500, f"QR code generation failed: {str(exc)}")


# ── Print view ──────────────────────────────────────────────────

@do_bp.route("/<int:order_id>/print")
@login_required
def print_view(order_id):
    """Render a print-friendly view of the delivery order."""
    order = get_order_detail(order_id)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("delivery_orders.order_list"))

    ctx = get_do_context()
    return render_template("delivery_orders/print.html", order=order, **ctx)


# ── AJAX endpoints ──────────────────────────────────────────────

@do_bp.route("/api/customer/<sap_code>")
@login_required
def get_customer_info(sap_code):
    """Return customer info for AJAX auto-fill."""
    from repos.delivery_order_repo import get_customer_by_sap_code
    customer = get_customer_by_sap_code(sap_code)
    if customer:
        return jsonify(customer)
    return jsonify({}), 404
