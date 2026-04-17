"""
Delivery Order management controller — Products, Customers, GRMS, Reports.

Each management section is independently gated by its own role:
  - do_mgmt_products  → Products
  - do_mgmt_customers → Customers
  - do_mgmt_grms      → GRMS
  - do_mgmt_reports   → Reports
  - do_approver       → full access to all sections

Roles are assigned per-user in Admin Settings → Modules → Delivery Orders.
"""

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session,
)
from auth.middleware import login_required
from services.do_permission_service import (
    get_do_context,
    is_do_admin,
    can_manage_products,
    can_manage_customers,
    can_manage_grms,
    can_manage_reports,
)
from services.admin_settings_service import check_text_for_restricted_words
from repos.delivery_order_repo import (
    # Products
    get_all_products,
    get_product_by_id,
    product_exists,
    create_product,
    update_product,
    get_sales_managers,
    # Customers
    get_all_customers,
    get_customer_by_pk,
    customer_sap_exists,
    next_customer_sap_code,
    create_customer,
    update_customer,
    # GRMS
    get_all_receipts,
    get_receipt_by_id,
    get_receipt_items,
    # Reports
    get_products_sold_report,
)

do_mgmt_bp = Blueprint(
    "do_management",
    __name__,
    url_prefix="/delivery-orders/manage",
)


def _deny():
    """Flash a permission message and redirect to the DO dashboard."""
    flash("You do not have permission to access this page.", "warning")
    return redirect(url_for("delivery_orders.dashboard"))


# ══════════════════════════════════════════════════════════════════
# ── PRODUCTS ─────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════

@do_mgmt_bp.route("/products")
@login_required
def products():
    """List all products."""
    if not can_manage_products():
        return _deny()

    products_list = get_all_products()
    ctx = get_do_context()
    return render_template(
        "delivery_orders/manage/products.html",
        products=products_list,
        **ctx,
    )


@do_mgmt_bp.route("/products/create", methods=["GET", "POST"])
@login_required
def product_create():
    """Create a new product."""
    if not can_manage_products():
        return _deny()

    ctx = get_do_context()
    managers = get_sales_managers()

    if request.method == "POST":
        data = {
            "product_id":     request.form.get("product_id", "").strip(),
            "name":           request.form.get("name", "").strip(),
            "market":         request.form.get("market", "").strip(),
            "uom":            request.form.get("uom", "").strip(),
            "sales_manager":  request.form.get("sales_manager"),
            "created_by":     session.get("emp_id"),
        }

        if not data["product_id"] or not data["name"]:
            flash("Product ID and Name are required.", "danger")
            return render_template(
                "delivery_orders/manage/product_form.html",
                form=data, managers=managers, editing=False, **ctx,
            )

        if product_exists(data["product_id"]):
            flash("A product with this ID already exists.", "danger")
            return render_template(
                "delivery_orders/manage/product_form.html",
                form=data, managers=managers, editing=False, **ctx,
            )

        try:
            create_product(data)
            flash("Product created successfully.", "success")
            return redirect(url_for("do_management.products"))
        except Exception as exc:
            flash(f"Error creating product: {exc}", "danger")

    return render_template(
        "delivery_orders/manage/product_form.html",
        form={}, managers=managers, editing=False, **ctx,
    )


@do_mgmt_bp.route("/products/<int:pk>/edit", methods=["GET", "POST"])
@login_required
def product_edit(pk):
    """Edit an existing product."""
    if not can_manage_products():
        return _deny()

    product = get_product_by_id(pk)
    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("do_management.products"))

    ctx = get_do_context()
    managers = get_sales_managers()

    if request.method == "POST":
        data = {
            "product_id":     request.form.get("product_id", "").strip(),
            "name":           request.form.get("name", "").strip(),
            "market":         request.form.get("market", "").strip(),
            "uom":            request.form.get("uom", "").strip(),
            "sales_manager":  request.form.get("sales_manager"),
            "modified_by":    session.get("emp_id"),
        }

        if not data["product_id"] or not data["name"]:
            flash("Product ID and Name are required.", "danger")
            return render_template(
                "delivery_orders/manage/product_form.html",
                form=data, managers=managers, editing=True, pk=pk, **ctx,
            )

        if product_exists(data["product_id"], exclude_id=pk):
            flash("Another product with this ID already exists.", "danger")
            return render_template(
                "delivery_orders/manage/product_form.html",
                form=data, managers=managers, editing=True, pk=pk, **ctx,
            )

        try:
            update_product(pk, data)
            flash("Product updated successfully.", "success")
            return redirect(url_for("do_management.products"))
        except Exception as exc:
            flash(f"Error updating product: {exc}", "danger")

    # Pre-fill form from existing product
    form = {
        "product_id":    product.get("Product_ID", ""),
        "name":          product.get("Name", ""),
        "market":        product.get("Market", ""),
        "uom":           product.get("Unit_Of_Measure", ""),
        "sales_manager": product.get("Sales_Manager"),
    }
    return render_template(
        "delivery_orders/manage/product_form.html",
        form=form, managers=managers, editing=True, pk=pk, **ctx,
    )


# ══════════════════════════════════════════════════════════════════
# ── CUSTOMERS ────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════

@do_mgmt_bp.route("/customers")
@login_required
def customers():
    """List all active customers."""
    if not can_manage_customers():
        return _deny()

    customers_list = get_all_customers()
    ctx = get_do_context()
    return render_template(
        "delivery_orders/manage/customers.html",
        customers=customers_list,
        **ctx,
    )


@do_mgmt_bp.route("/customers/create", methods=["GET", "POST"])
@login_required
def customer_create():
    """Create a new customer."""
    if not can_manage_customers():
        return _deny()

    ctx = get_do_context()

    if request.method == "POST":
        data = {
            "sap_code":          next_customer_sap_code(),
            "sap_code_from_sap": request.form.get("sap_code_from_sap", "").strip(),
            "name":              request.form.get("name", "").strip(),
            "address":           request.form.get("address", "").strip(),
            "postal_code":       request.form.get("postal_code", "").strip(),
            "country_iso":       request.form.get("country_iso", "").strip(),
            "region":            request.form.get("region", "").strip(),
            "contact_number":    request.form.get("contact_number", "").strip(),
            "created_by":        session.get("emp_id"),
        }

        if not data["name"]:
            flash("Customer name is required.", "danger")
            customers_list = get_all_customers()
            return render_template(
                "delivery_orders/manage/customer_form.html",
                form=data, editing=False,
                next_sap_code=data["sap_code"],
                customers=customers_list, **ctx,
            )

        # Check restricted words in text fields
        _cust_text_fields = {
            "sap_code_from_sap": "SAP Code",
            "name": "Name",
            "address": "Address",
            "postal_code": "Postal Code",
            "region": "Region / State",
            "contact_number": "Contact Number",
        }
        for fld, label in _cust_text_fields.items():
            val = data.get(fld, "")
            if val:
                blocked = check_text_for_restricted_words(val)
                if blocked:
                    flash(f"{label} contains blocked word(s): {', '.join(blocked)}", "danger")
                    customers_list = get_all_customers()
                    return render_template(
                        "delivery_orders/manage/customer_form.html",
                        form=data, editing=False,
                        next_sap_code=data["sap_code"],
                        customers=customers_list, **ctx,
                    )

        try:
            create_customer(data)
            flash("Customer created successfully.", "success")
            return redirect(url_for("do_management.customers"))
        except Exception as exc:
            flash(f"Error creating customer: {exc}", "danger")

    next_code = next_customer_sap_code()
    customers_list = get_all_customers()
    return render_template(
        "delivery_orders/manage/customer_form.html",
        form={}, editing=False, next_sap_code=next_code,
        customers=customers_list, **ctx,
    )


@do_mgmt_bp.route("/customers/<int:pk>/edit", methods=["GET", "POST"])
@login_required
def customer_edit(pk):
    """Edit an existing customer."""
    if not can_manage_customers():
        return _deny()

    customer = get_customer_by_pk(pk)
    if not customer:
        flash("Customer not found.", "danger")
        return redirect(url_for("do_management.customers"))

    ctx = get_do_context()

    if request.method == "POST":
        data = {
            "sap_code_from_sap": request.form.get("sap_code_from_sap", "").strip(),
            "name":              request.form.get("name", "").strip(),
            "address":           request.form.get("address", "").strip(),
            "postal_code":       request.form.get("postal_code", "").strip(),
            "country_iso":       request.form.get("country_iso", "").strip(),
            "region":            request.form.get("region", "").strip(),
            "contact_number":    request.form.get("contact_number", "").strip(),
            "modified_by":       session.get("emp_id"),
        }

        if not data["name"]:
            flash("Customer name is required.", "danger")
            customers_list = get_all_customers()
            return render_template(
                "delivery_orders/manage/customer_form.html",
                form=data, editing=True, pk=pk,
                ahlaan_vendor_code=customer.get("SapCode", ""),
                customers=customers_list, **ctx,
            )

        # Check restricted words in text fields
        _cust_text_fields = {
            "sap_code_from_sap": "SAP Code",
            "name": "Name",
            "address": "Address",
            "postal_code": "Postal Code",
            "region": "Region / State",
            "contact_number": "Contact Number",
        }
        for fld, label in _cust_text_fields.items():
            val = data.get(fld, "")
            if val:
                blocked = check_text_for_restricted_words(val)
                if blocked:
                    flash(f"{label} contains blocked word(s): {', '.join(blocked)}", "danger")
                    customers_list = get_all_customers()
                    return render_template(
                        "delivery_orders/manage/customer_form.html",
                        form=data, editing=True, pk=pk,
                        ahlaan_vendor_code=customer.get("SapCode", ""),
                        customers=customers_list, **ctx,
                    )

        try:
            update_customer(pk, data)
            flash("Customer updated successfully.", "success")
            return redirect(url_for("do_management.customers"))
        except Exception as exc:
            flash(f"Error updating customer: {exc}", "danger")

    form = {
        "sap_code_from_sap": customer.get("SapCodeFromSAP", ""),
        "name":              customer.get("Name", ""),
        "address":           customer.get("Address", ""),
        "postal_code":       customer.get("Postal_Code", ""),
        "country_iso":       customer.get("Country_ISO_Code", ""),
        "region":            customer.get("Region", ""),
        "contact_number":    customer.get("Contact_Number", ""),
    }
    customers_list = get_all_customers()
    return render_template(
        "delivery_orders/manage/customer_form.html",
        form=form, editing=True, pk=pk,
        ahlaan_vendor_code=customer.get("SapCode", ""),
        customers=customers_list, **ctx,
    )


# ══════════════════════════════════════════════════════════════════
# ── GRMS (Receipts) ──────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════

@do_mgmt_bp.route("/grms")
@login_required
def grms_list():
    """List GRMS receipts with pagination."""
    if not can_manage_grms():
        return _deny()

    status = request.args.get("status", "ALL")
    page = int(request.args.get("page", 1))

    receipts, total = get_all_receipts(status=status, page=page)
    per_page = 25
    total_pages = max(1, (total + per_page - 1) // per_page)

    ctx = get_do_context()
    return render_template(
        "delivery_orders/manage/grms.html",
        receipts=receipts,
        total=total,
        page=page,
        total_pages=total_pages,
        current_status=status,
        **ctx,
    )


@do_mgmt_bp.route("/grms/<int:receipt_id>")
@login_required
def grms_detail(receipt_id):
    """View a single GRMS receipt."""
    if not can_manage_grms():
        return _deny()

    receipt = get_receipt_by_id(receipt_id)
    if not receipt:
        flash("Receipt not found.", "danger")
        return redirect(url_for("do_management.grms_list"))

    receipt["items"] = get_receipt_items(receipt.get("Receipt_Number", ""))
    ctx = get_do_context()
    return render_template(
        "delivery_orders/manage/grms_detail.html",
        receipt=receipt,
        **ctx,
    )


# ══════════════════════════════════════════════════════════════════
# ── REPORTS ──────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════

@do_mgmt_bp.route("/reports")
@login_required
def reports():
    """Show the DO reports page."""
    if not can_manage_reports():
        return _deny()

    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    data = get_products_sold_report(
        date_from=date_from or None,
        date_to=date_to or None,
    )

    ctx = get_do_context()
    return render_template(
        "delivery_orders/manage/reports.html",
        report_data=data,
        date_from=date_from,
        date_to=date_to,
        **ctx,
    )
