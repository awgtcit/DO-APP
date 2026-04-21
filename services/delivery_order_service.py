"""
Delivery Order service — business logic for the Sales/Delivery Order module.
"""

import builtins

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
    add_order_item,
    delete_order_item,
    add_order_attachment,
    delete_order_attachment,
    update_logistics_fields as _repo_update_logistics_fields,
    update_sales_fields as _repo_update_sales_fields,
)
from services.do_permission_service import (
    get_do_role,
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
    return order


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

    current = order.get("Status", "")
    flow = _get_status_flow()
    allowed = flow.get(current, [])

    if new_status not in allowed:
        return False, ["Status transition not allowed."], ""

    # Ownership routing: creator submitting DRAFT → check if Customer Manager approval needed.
    # Use the already-JOINed ownership fields from the order dict to avoid an extra DB call
    # and to guarantee consistency with what the detail view shows.
    if current == "DRAFT" and new_status == "SUBMITTED":
        bill_o = (order.get("bill_to_ownership_sole_prop") or "").strip()
        ship_o = (order.get("ship_to_ownership_sole_prop") or "").strip()
        if bill_o in ("Yes", "N/A") or ship_o in ("Yes", "N/A"):
            new_status = "PENDING CUSTOMER APPROVAL"

    # Permission check
    if not can_transition(order, new_status):
        return False, ["You lack permission for this transition."], ""

    # Mandatory-field gate for SUBMITTED
    if new_status == "SUBMITTED":
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
