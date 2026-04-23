"""
Delivery Order service — business logic for the Sales/Delivery Order module.
"""

import builtins
import hashlib

from flask import session
from repos.delivery_order_repo import (
    get_dashboard_stats,
    get_dashboard_stats_for_user,
    get_all_orders,
    get_orders_for_user,
    get_order_by_id,
    get_order_items,
    get_order_attachments,
    get_sales_managers,
    get_bill_to_list,
    get_customer_by_sap_code,
    get_point_of_exit_list,
    get_products,
    get_last_po_number,
    create_order,
    update_order,
    update_order_status,
    update_order_status_with_reason,
    get_latest_rejection_status_history,
    get_order_status_history,
    add_order_status_history,
    add_order_item,
    delete_order_item,
    add_order_attachment,
    delete_order_attachment,
    update_logistics_fields as _repo_update_logistics_fields,
    update_sales_fields as _repo_update_sales_fields,
)
from services.do_permission_service import (
    get_do_role,
    get_my_action_statuses,
    get_allowed_transitions,
    can_transition,
    can_edit_order,
    can_see_prices,
    needs_reject_reason,
    DO_ROLE_APPROVER,
    DO_ROLE_FINANCE,
    DO_ROLE_LOGISTICS,
    DO_ROLE_CREATOR,
    DO_ROLE_CUSTOMER_MANAGER,
)
from services.do_email_service import send_do_status_email


# ── Constants ───────────────────────────────────────────────────

DELIVERY_TERMS = [
    ("EXW", "ExWorks"),
    ("FCA", "Free Carrier"),
    ("CPT", "Carriage Paid To"),
    ("CIP", "Carriage and Insurance Paid"),
    ("DAT", "Delivered at Terminal"),
    ("DAP", "Delivered At Place"),
    ("DDP", "Delivered Duty Paid"),
    ("FAS", "Free Alongside Ship"),
    ("FOB", "Free On Board"),
    ("CFR", "Cost and Freight"),
    ("CIF", "Cost, Insurance, Freight"),
    ("DAF", "Delivered at Frontier"),
    ("DES", "Delivered Ex Ship"),
    ("DEQ", "Delivered Ex Quay"),
    ("DDU", "Delivered Duty Unpaid"),
]

TRANSPORT_MODES = [
    ("by_road", "By Road"),
    ("by_sea", "By Sea"),
    ("by_air", "By Air"),
    ("combined_road_sea", "Combined Road & Sea"),
    ("combined_road_air", "Combined Road & Air"),
    ("combined_sea_air", "Combined Sea & Air"),
]

CURRENCIES = ["USD", "EURO", "AED"]

STATUS_OPTIONS = [
    "ALL", "DRAFT", "PENDING CUSTOMER APPROVAL", "SUBMITTED", "PRICE AGREED",
    "CONFIRMED", "CUSTOMS DOCUMENT UPDATED", "DELIVERED",
    "NEED ATTACHMENT", "REJECTED", "CANCELLED",
]

_HARDCODED_STATUS_FLOW = {
    "DRAFT":                       ["SUBMITTED", "PENDING CUSTOMER APPROVAL", "CANCELLED"],
    "PENDING CUSTOMER APPROVAL":   ["SUBMITTED", "REJECTED", "DRAFT"],
    "SUBMITTED":                   ["PRICE AGREED", "NEED ATTACHMENT", "REJECTED"],
    "PRICE AGREED":                ["CONFIRMED", "CANCELLED"],
    "CONFIRMED":                   ["NEED ATTACHMENT", "CUSTOMS DOCUMENT UPDATED"],
    "CUSTOMS DOCUMENT UPDATED":    ["DELIVERED"],
    "DELIVERED":                   [],
    "NEED ATTACHMENT":             ["CONFIRMED"],
    "REJECTED":                    ["DRAFT"],
    "CANCELLED":                   [],
}

def _get_status_flow() -> dict:
    """Return DO status-flow from admin settings service (DB + fallback)."""
    from services.admin_settings_service import get_status_flow
    return get_status_flow("delivery_orders")

# Keep module-level reference for backward compat (lazy-evaluated in functions)
STATUS_FLOW = _HARDCODED_STATUS_FLOW


# ── Dashboard ───────────────────────────────────────────────────

def do_dashboard_stats() -> dict:
    """
    Get KPI counts for the Delivery Order dashboard.
    Approvers/finance/logistics/customer_manager see ALL orders; creators see only their own.
    """
    do_role = get_do_role()
    if do_role in (DO_ROLE_APPROVER, DO_ROLE_FINANCE, DO_ROLE_LOGISTICS, DO_ROLE_CUSTOMER_MANAGER):
        return get_dashboard_stats()
    emp_id = session.get("emp_id")
    if emp_id:
        return get_dashboard_stats_for_user(emp_id)
    return get_dashboard_stats()


def get_dashboard_action_context() -> dict:
    """Return role-aware dashboard action hints and optional action queue rows."""
    role = get_do_role()
    action_statuses = get_my_action_statuses("delivery_orders")

    queue_rows: list[dict] = []
    queue_title = "My Action Orders"
    show_action_queue = bool(action_statuses)

    merged: dict[int, dict] = {}
    for st in action_statuses:
        rows, _ = list_orders(status=st, page=1, per_page=100)
        for row in rows:
            rid = int(row.get("id") or 0)
            if rid:
                merged[rid] = row

    queue_rows = sorted(merged.values(), key=lambda r: int(r.get("id") or 0), reverse=True)[:25]

    if role == DO_ROLE_CREATOR:
        queue_title = "My Action Orders (Draft + Rejected)"
    elif role == DO_ROLE_CUSTOMER_MANAGER:
        queue_title = "My Action Orders (Pending Customer Approval)"
    elif role == DO_ROLE_FINANCE:
        queue_title = "My Action Orders (Submitted + Confirmed)"
    elif role == DO_ROLE_LOGISTICS:
        queue_title = "My Action Orders (Price Agreed / Need Attachment / Customs Updated)"
    elif role == DO_ROLE_APPROVER:
        queue_title = "My Action Orders (All Workflow Steps)"

    queue_empty_text = (
        f"No orders found for your action statuses: {', '.join(action_statuses)}."
        if action_statuses else
        "No action orders found."
    )

    return {
        "action_statuses": action_statuses,
        "action_queue_rows": queue_rows,
        "action_queue_title": queue_title,
        "show_action_queue": show_action_queue,
        "action_queue_empty_text": queue_empty_text,
    }


# ── List ────────────────────────────────────────────────────────

def list_orders(
    status: str | None = None,
    page: int = 1,
    per_page: int = 25,
    search: str | None = None,
) -> tuple[list[dict], int]:
    """
    List delivery orders with filtering + pagination.
    Approvers/finance/logistics/customer_manager see all; creators see only their own.
    """
    do_role = get_do_role()
    if do_role in (DO_ROLE_APPROVER, DO_ROLE_FINANCE, DO_ROLE_LOGISTICS, DO_ROLE_CUSTOMER_MANAGER):
        return get_all_orders(status=status, page=page, per_page=per_page, search=search)

    emp_id = session.get("emp_id")
    if emp_id:
        return get_orders_for_user(emp_id, status=status, page=page, per_page=per_page, search=search)
    return get_all_orders(status=status, page=page, per_page=per_page, search=search)


# ── Detail ──────────────────────────────────────────────────────

def get_order_detail(order_id: int) -> dict | None:
    """Get full order detail including items, attachments, and permissions."""
    order = get_order_by_id(order_id)
    if not order:
        return None
    order["line_items"] = get_order_items(order.get("PO_Number", ""))
    order["attachments"] = get_order_attachments(order_id)
    order["allowed_transitions"] = get_allowed_transitions(order)
    order["can_edit"] = can_edit_order(order)
    order["show_prices"] = can_see_prices()
    order["products"] = get_products()
    order["status_history"] = get_order_status_history(order_id)
    return order


def _get_actor_name() -> str:
    """Build actor display name from session with safe fallbacks."""
    first = (session.get("first_name") or "").strip()
    last = (session.get("last_name") or "").strip()
    full = (f"{first} {last}").strip()
    if full:
        return full
    return (session.get("name") or session.get("username") or session.get("email") or "Unknown User").strip()


def _build_price_signature(order: dict) -> tuple[str, float]:
    """Compute deterministic signature + total amount for current line-item pricing."""
    items = get_order_items(order.get("PO_Number", ""))
    parts: list[str] = []
    total_amount = 0.0

    for item in items:
        product_id = str(item.get("Product_ID") or "").strip()
        qty = float(item.get("Quantity") or 0)
        unit_price = float(item.get("Unit_Price") or 0)
        currency = str(item.get("Currency") or "").strip().upper()
        parts.append(f"{product_id}|{qty:.4f}|{unit_price:.4f}|{currency}")
        total_amount += float(item.get("Total_Amount") or (qty * unit_price))

    payload = "||".join(sorted(parts))
    signature = hashlib.sha256(payload.encode("utf-8")).hexdigest() if payload else ""
    return signature, total_amount


def _log_status_transition(
    order: dict,
    from_status: str,
    to_status: str,
    emp_id: int,
    actor_role: str,
    reject_reason: str | None = None,
    reject_remarks: str | None = None,
    remarks: str | None = None,
) -> None:
    """Persist status transition transaction record. Fail-safe: never break main flow."""
    try:
        price_signature, total_amount = _build_price_signature(order)
        if to_status == "SUBMITTED":
            action_type = "SUBMITTED"
        elif to_status.startswith("REJECTED"):
            action_type = "REJECTED"
        elif to_status in ("PRICE AGREED", "CONFIRMED", "DELIVERED"):
            action_type = "APPROVED"
        else:
            action_type = "STATUS_CHANGE"

        add_order_status_history({
            "order_id": order.get("id"),
            "po_number": order.get("PO_Number", ""),
            "from_status": from_status,
            "to_status": to_status,
            "action_type": action_type,
            "actor_emp_id": emp_id,
            "actor_name": _get_actor_name(),
            "actor_role": actor_role,
            "remarks": remarks or "",
            "price_signature": price_signature,
            "total_amount": round(total_amount, 2),
            "reject_reason": reject_reason or "",
            "reject_remarks": reject_remarks or "",
        })
    except Exception:
        # Keep status flow resilient if history insert fails.
        pass


def _route_resubmission_target(
    order: dict,
    current_target_status: str,
    requested_status: str,
) -> tuple[str, str | None]:
    """Apply business routing for creator re-submissions after rejection."""
    if requested_status != "SUBMITTED":
        return current_target_status, None

    last_reject = get_latest_rejection_status_history(order.get("id"))
    if not last_reject:
        return current_target_status, None

    rejected_by_role = (last_reject.get("actor_role") or "").strip().lower()
    if rejected_by_role == DO_ROLE_FINANCE:
        return "SUBMITTED", "Resubmission routed to Finance (last rejection by Finance)."

    if rejected_by_role == DO_ROLE_LOGISTICS:
        previous_signature = (last_reject.get("price_signature") or "").strip()
        current_signature, current_total_amount = _build_price_signature(order)

        # Primary check: deterministic item-level signature (unit price/qty/currency/product)
        price_changed = bool(previous_signature and current_signature and previous_signature != current_signature)

        # Fallback for old history rows without signature: compare stored total amount.
        if not price_changed and (not previous_signature or not current_signature):
            try:
                previous_total = float(last_reject.get("total_amount") or 0)
            except (TypeError, ValueError):
                previous_total = 0.0
            price_changed = abs(previous_total - float(current_total_amount or 0)) > 0.0001

        if price_changed:
            return "SUBMITTED", "Resubmission routed to Finance because pricing changed after Logistics rejection."

        # No price change: return directly to logistics lane.
        return "PRICE AGREED", "Resubmission routed directly to Logistics (no pricing change)."

    return current_target_status, None


# ── Lookups ─────────────────────────────────────────────────────

def get_form_lookups() -> dict:
    """Fetch all dropdown data needed for create/edit forms."""
    bill_to_list = get_bill_to_list()
    for customer in bill_to_list:
        customer["DerivedMarksNumbers"] = _format_marks_numbers_for_customer(customer)

    return {
        "sales_managers": get_sales_managers(),
        "bill_to_list": bill_to_list,
        "point_of_exit": get_point_of_exit_list(),
        "products": get_products(),
        "delivery_terms": DELIVERY_TERMS,
        "transport_modes": TRANSPORT_MODES,
        "currencies": CURRENCIES,
        "last_po": get_last_po_number(),
    }


def _format_marks_numbers_for_customer(customer: dict) -> str:
    """Format Marks & Numbers for a customer using ownership rules."""
    def _to_text(value, default: str = "") -> str:
        if value is None:
            return default
        return builtins.str(value).strip()

    ownership = _to_text(customer.get("Ownership_Sole_Proprietorship"), "No") or "No"
    if ownership != "No":
        return "N/A"

    sap_code = _to_text(customer.get("SapCodeFromSAP") or customer.get("SapCode"))
    customer_name = _to_text(customer.get("Name"))
    if sap_code and customer_name:
        return f"{sap_code} | {customer_name}"
    return customer_name or sap_code


def derive_marks_numbers_for_bill_to(bill_to_sap_code: str | None) -> str:
    """Derive Marks & Numbers using ownership rules from Bill To customer.

    Rules:
    - Ownership == "No"  -> SAP Code From SAP (or Ahlaan code) + customer name
    - Ownership == "Yes" -> "N/A"
    - Ownership == "N/A" -> "N/A"
    """
    if not bill_to_sap_code:
        return ""

    customer = get_customer_by_sap_code(str(bill_to_sap_code))
    if not customer:
        return ""

    return _format_marks_numbers_for_customer(customer)


# ── Ownership routing ────────────────────────────────────────────

def get_ownership_routing(bill_to_sap: str | None, ship_to_sap: str | None) -> dict:
    """
    Determine workflow routing based on Bill To and Ship To ownership.

    Returns a dict with:
      'needs_customer_approval': bool
      'scenario': 'direct' | 'sole_prop' | 'na_parties' | 'mixed'
      'notification_type': None | 'not_allowed' | 'parties_not_defined'
      'bill_to_ownership': str   (raw value from DB)
      'ship_to_ownership': str   (raw value from DB)
    """
    def _ownership(sap_code: str | None) -> str:
        if not sap_code:
            return "N/A"
        c = get_customer_by_sap_code(str(sap_code))
        if not c:
            return "N/A"
        val = str(c.get("Ownership_Sole_Proprietorship") or "No").strip()
        return val if val else "No"

    bill_o = _ownership(bill_to_sap)
    ship_o = _ownership(ship_to_sap)

    # BillTo=No AND ShipTo=No → direct flow, no notification
    if bill_o == "No" and ship_o == "No":
        return {
            "needs_customer_approval": False,
            "scenario": "direct",
            "notification_type": None,
            "bill_to_ownership": bill_o,
            "ship_to_ownership": ship_o,
        }

    # BillTo=N/A AND ShipTo=N/A → parties not defined
    if bill_o == "N/A" and ship_o == "N/A":
        return {
            "needs_customer_approval": True,
            "scenario": "na_parties",
            "notification_type": "parties_not_defined",
            "bill_to_ownership": bill_o,
            "ship_to_ownership": ship_o,
        }

    # Any Yes or mixed N/A → sole proprietorship / not allowed
    return {
        "needs_customer_approval": True,
        "scenario": "sole_prop",
        "notification_type": "not_allowed",
        "bill_to_ownership": bill_o,
        "ship_to_ownership": ship_o,
    }


# ── Create ──────────────────────────────────────────────────────

def create_new_order(data: dict) -> int:
    """Create a new delivery order. Always starts as DRAFT."""
    data = dict(data)
    data["initial_status"] = "DRAFT"
    return create_order(data)


# ── Update ──────────────────────────────────────────────────────

def update_existing_order(order_id: int, data: dict) -> bool:
    """Update delivery order header."""
    return update_order(order_id, data)


def validate_order_for_submit(order: dict) -> list[str]:
    """
    Validate that an order has all mandatory fields filled before
    it can be submitted.  Returns a list of error messages (empty = OK).
    """
    errors: list[str] = []

    # Must have at least one line item
    po_number = order.get("PO_Number", "")
    items = get_order_items(po_number) if po_number else []
    if not items:
        errors.append("At least one line item is required before submitting.")

    # Required header fields
    required_fields = {
        "Bill_To_SapCode":         "Bill To",
        "Ship_To_SapCode":         "Ship To",
        "Delivery_Terms":          "Delivery Terms",
        "Loading_Date":            "Loading Date",
        "Ship_To_PointOfExit":     "Point of Exit",
        "Ship_To_FinalDestination": "Final Destination",
    }
    for db_field, label in required_fields.items():
        val = order.get(db_field)
        if not val or (isinstance(val, str) and not val.strip()):
            errors.append(f"{label} is required before submitting.")

    # Check restricted words in text fields
    from services.admin_settings_service import check_text_for_restricted_words
    text_fields = {"Ship_To_FinalDestination": "Final Destination"}
    for db_field, label in text_fields.items():
        val = order.get(db_field, "")
        if val and isinstance(val, str):
            blocked = check_text_for_restricted_words(val)
            if blocked:
                errors.append(f"{label} contains blocked word(s): {', '.join(blocked)}")

    return errors


def change_order_status(
    order_id: int,
    new_status: str,
    emp_id: int,
    reject_reason: str | None = None,
    reject_remarks: str | None = None,
) -> tuple[bool, list[str], str]:
    """
    Change order status following the allowed flow AND permission checks.
    Returns (success, error_messages, actual_status_applied).
    actual_status_applied is the status actually saved (may differ from new_status
    when ownership routing intercepts SUBMITTED → PENDING CUSTOMER APPROVAL).
    """
    order = get_order_by_id(order_id)
    if not order:
        return False, ["Order not found."], ""

    requested_status = (new_status or "").strip().upper()
    current = (order.get("Status", "") or "").strip().upper()
    flow = {
        (src or "").strip().upper(): [
            (dst or "").strip().upper() for dst in destinations if (dst or "").strip()
        ]
        for src, destinations in _get_status_flow().items()
    }
    allowed = flow.get(current, [])

    if requested_status not in allowed:
        return False, ["Status transition not allowed."], ""

    # Permission check on the originally-requested status (before any internal redirect).
    if not can_transition(order, requested_status):
        return False, ["You lack permission for this transition."], ""

    new_status = requested_status

    # Ownership routing: creator submitting DRAFT → check if Customer Manager approval needed.
    # Use the already-JOINed ownership fields from the order dict to avoid an extra DB call
    # and to guarantee consistency with what the detail view shows.
    if current == "DRAFT" and new_status == "SUBMITTED":
        bill_o = (order.get("bill_to_ownership_sole_prop") or "").strip()
        ship_o = (order.get("ship_to_ownership_sole_prop") or "").strip()
        if bill_o in ("Yes", "N/A") or ship_o in ("Yes", "N/A"):
            new_status = "PENDING CUSTOMER APPROVAL"

    # Re-submission routing override: if order was rejected previously,
    # route based on rejecting role + price change rule.
    # This intentionally runs after ownership routing so re-submission logic wins.
    reroute_remarks = None
    if requested_status == "SUBMITTED":
        new_status, reroute_remarks = _route_resubmission_target(order, new_status, requested_status)

    # Mandatory-field gate for creator submit requests, even if workflow reroutes
    # internally to customer approval first.
    if requested_status == "SUBMITTED":
        errors = validate_order_for_submit(order)
        if errors:
            return False, errors, ""

    # Use reject reason variant when rejecting
    if needs_reject_reason(new_status) and (reject_reason or reject_remarks):
        ok = update_order_status_with_reason(
            order_id, new_status, emp_id, reject_reason, reject_remarks
        )
    else:
        ok = update_order_status(order_id, new_status, emp_id)

    if ok:
        _log_status_transition(
            order=order,
            from_status=current,
            to_status=new_status,
            emp_id=emp_id,
            actor_role=get_do_role(),
            reject_reason=reject_reason,
            reject_remarks=reject_remarks,
            remarks=reroute_remarks,
        )

    # Send email notification on successful transition
    if ok:
        # CC the order creator + the user performing the action
        from flask import session as flask_session
        cc_emails = []
        creator_email = order.get("creator_email", "")
        if creator_email:
            cc_emails.append(creator_email)
        actor_email = flask_session.get("email", "")
        if actor_email:
            cc_emails.append(actor_email)

        # Attach line_items so the PDF template can render them
        if "line_items" not in order:
            order["line_items"] = get_order_items(order.get("PO_Number", ""))

        send_do_status_email(
            order=order,
            new_status=new_status,
            creator_first_name=order.get("creator_first"),
            reject_reason=reject_reason,
            reject_remarks=reject_remarks,
            extra_cc=cc_emails,
        )

    return ok, [], new_status if ok else ""


# ── Items ───────────────────────────────────────────────────────

def add_item_to_order(data: dict) -> int:
    """Add a line item. Returns new item ID."""
    return add_order_item(data)


def remove_item_from_order(item_id: int) -> bool:
    """Delete a line item."""
    return delete_order_item(item_id)


# ── Attachments ─────────────────────────────────────────────────

def add_attachment(data: dict) -> int:
    """Add an attachment to an order. Returns new attachment ID."""
    return add_order_attachment(data)


def remove_attachment(attachment_id: int) -> bool:
    """Delete an attachment."""
    return delete_order_attachment(attachment_id)


def get_attachment(attachment_id: int) -> dict | None:
    """Get a single attachment with binary content."""
    from repos.delivery_order_repo import get_attachment_by_id
    return get_attachment_by_id(attachment_id)


# ── Post-delivery tracking ─────────────────────────────────────

def save_logistics_fields(order_id: int, data: dict, modified_by: int,
                          new_status: str | None = None) -> bool:
    """Save Fujairah Logistics Team post-delivery fields."""
    return _repo_update_logistics_fields(order_id, data, modified_by, new_status)


def save_sales_fields(order_id: int, data: dict, modified_by: int,
                      new_status: str | None = None) -> bool:
    """Save Sales Team post-delivery fields."""
    return _repo_update_sales_fields(order_id, data, modified_by, new_status)


# ── QR Code data ────────────────────────────────────────────────

def build_qr_payload(order: dict) -> dict:
    """
    Build the QR code JSON payload for a confirmed order.
    Matches the legacy Data Matrix format exactly.
    """
    po_number = (order.get("PO_Number") or "").strip()
    ship_to_sap = (order.get("bill_to_sap_ship") or "").strip()
    bill_to_sap = (order.get("bill_to_sap") or "").strip()
    loading_date = order.get("Loading_Date")

    # Build waybill: remove slashes from PO number
    waybill = po_number.replace("/", "") if po_number else ""

    # Build ASN: waybill + "_" + loading date as YYYYMMDD
    asn = waybill
    if loading_date and waybill:
        try:
            if hasattr(loading_date, "strftime"):
                asn = waybill + "_" + loading_date.strftime("%Y%m%d")
            else:
                # Handle string dates
                date_str = str(loading_date).replace("-", "")[:8]
                if date_str:
                    asn = waybill + "_" + date_str
        except (ValueError, AttributeError, TypeError):
            pass

    return {
        "properties": [
            {"document": po_number or ""},
            {"destination": f"{ship_to_sap}_DST" if ship_to_sap else ""},
            {"soldto": f"{bill_to_sap}_SLD" if bill_to_sap else ""},
            {"stockowner": "Alwahdania"},
            {"dtswaybill": waybill},
            {"dtsasn": asn},
            {"dtsinvoice": ""},
            {"dtsbuyerorder": ""},
        ]
    }
