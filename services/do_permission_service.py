"""
Delivery Order permission service — role-based access control for the DO module.

Role resolution priority:
  1. Per-module role from Intra_Admin_UserModuleRole (admin-assigned)
  2. System admin (GroupID=1) → DO Approver
  3. Fallback → DO Creator

Reject reasons are the 11 predefined options from the legacy system.
"""

import logging
from flask import g, session

logger = logging.getLogger(__name__)

# ── DO Role constants ───────────────────────────────────────────

DO_ROLE_APPROVER          = "do_approver"
DO_ROLE_FINANCE           = "do_finance"
DO_ROLE_LOGISTICS         = "do_logistics"
DO_ROLE_CREATOR           = "do_creator"
DO_ROLE_CUSTOMER_MANAGER  = "do_customer_manager"   # approves ownership-flagged orders

# Management section role constants
DO_MGMT_PRODUCTS = "do_mgmt_products"
DO_MGMT_CUSTOMERS = "do_mgmt_customers"
DO_MGMT_GRMS = "do_mgmt_grms"
DO_MGMT_REPORTS = "do_mgmt_reports"

# All management role keys
DO_MGMT_ROLES = {DO_MGMT_PRODUCTS, DO_MGMT_CUSTOMERS, DO_MGMT_GRMS, DO_MGMT_REPORTS}

# All order-flow role keys
DO_ORDER_ROLES = {
    DO_ROLE_APPROVER, DO_ROLE_FINANCE, DO_ROLE_LOGISTICS,
    DO_ROLE_CREATOR, DO_ROLE_CUSTOMER_MANAGER,
}

# Status that requires Customer Manager approval before Finance sees the order
STATUS_PENDING_CUSTOMER_APPROVAL = "PENDING CUSTOMER APPROVAL"

# ── Predefined reject reasons (legacy parity) ──────────────────

REJECT_REASONS = [
    "Bill to party change",
    "Ship to party change",
    "Loading date change",
    "Product item change",
    "Additional packing requirement",
    "DO Revision",
    "Price Not Agreed",
    "Selling price is less than the cost price",
    "Qty Shortage",
    "Order Cancelled by Sales Manager",
    "Unavailability of Vehicle",
]


# ── Role resolution ─────────────────────────────────────────────

def get_do_role() -> str:
    """
    Determine the current user's DO role.

    Resolution order:
      1. Per-module role from Intra_Admin_UserModuleRole (most specific)
      2. System admin / it_admin → DO Approver
      3. Fallback → DO Creator

    Result is cached on Flask's ``g`` object so the DB is only hit once
    per request regardless of how many permission checks run.
    """
    cached = getattr(g, "_do_role", None)
    if cached is not None:
        return cached

    roles = session.get("roles", []) or []
    if isinstance(roles, str):
        roles = [roles]
    roles_lower = {r.lower() for r in roles}

    resolved = DO_ROLE_CREATOR  # default fallback

    # 1. Check per-module role assignment (admin-configurable)
    emp_id = session.get("emp_id")
    if emp_id:
        try:
            from services.admin_settings_service import get_all_module_roles_for_user
            module_roles = get_all_module_roles_for_user(emp_id)
            do_roles = module_roles.get("delivery_orders", [])
            if do_roles:
                # Priority: approver > finance > logistics > customer_manager > creator
                if DO_ROLE_APPROVER in do_roles:
                    resolved = DO_ROLE_APPROVER
                elif DO_ROLE_FINANCE in do_roles:
                    resolved = DO_ROLE_FINANCE
                elif DO_ROLE_LOGISTICS in do_roles:
                    resolved = DO_ROLE_LOGISTICS
                elif DO_ROLE_CUSTOMER_MANAGER in do_roles:
                    resolved = DO_ROLE_CUSTOMER_MANAGER
                elif DO_ROLE_CREATOR in do_roles:
                    resolved = DO_ROLE_CREATOR

                g._do_role = resolved
                return resolved
        except Exception:
            logger.exception("Error in get_do_role for emp_id=%s", emp_id)

    # 2. System admin → full DO approver
    if "admin" in roles_lower or "it_admin" in roles_lower:
        resolved = DO_ROLE_APPROVER

    g._do_role = resolved
    return resolved


def is_do_admin() -> bool:
    """Check if the user has admin/it_admin role (DO Approver)."""
    return get_do_role() == DO_ROLE_APPROVER


def is_do_finance() -> bool:
    """Check if the user has the finance role (approver → DO Finance)."""
    return get_do_role() == DO_ROLE_FINANCE


def is_do_logistics() -> bool:
    """Check if the user has the logistics role (reviewer → DO Logistics)."""
    return get_do_role() == DO_ROLE_LOGISTICS


def is_do_customer_manager() -> bool:
    """Check if the user has the Customer Manager role."""
    return get_do_role() == DO_ROLE_CUSTOMER_MANAGER


def is_do_creator() -> bool:
    """Check if the user is a regular creator (no special DO roles)."""
    return get_do_role() == DO_ROLE_CREATOR


# ── Management section permissions ──────────────────────────────

def _get_user_do_roles() -> set[str]:
    """
    Return the full set of DO role_keys assigned to the current user
    (from Intra_Admin_UserModuleRole).  Cached on ``g`` for the request.
    """
    cached = getattr(g, "_do_all_roles", None)
    if cached is not None:
        return cached

    roles_set: set[str] = set()
    emp_id = session.get("emp_id")
    if emp_id:
        try:
            from services.admin_settings_service import get_all_module_roles_for_user
            module_roles = get_all_module_roles_for_user(emp_id)
            roles_set = set(module_roles.get("delivery_orders", []))
        except Exception:
            logger.exception("Error fetching DO module roles for emp_id=%s", emp_id)

    # Admins get every role implicitly
    sys_roles = session.get("roles", []) or []
    if isinstance(sys_roles, str):
        sys_roles = [sys_roles]
    sys_lower = {r.lower() for r in sys_roles}
    if "admin" in sys_lower or "it_admin" in sys_lower:
        roles_set.update(DO_ORDER_ROLES | DO_MGMT_ROLES)

    g._do_all_roles = roles_set
    return roles_set


def can_manage_products() -> bool:
    """Check if the user can access the Products management page."""
    r = _get_user_do_roles()
    return DO_MGMT_PRODUCTS in r or DO_ROLE_APPROVER in r


def can_manage_customers() -> bool:
    """Check if the user can access the Customers management page."""
    r = _get_user_do_roles()
    return DO_MGMT_CUSTOMERS in r or DO_ROLE_APPROVER in r


def can_manage_grms() -> bool:
    """Check if the user can access the GRMS management page."""
    r = _get_user_do_roles()
    return DO_MGMT_GRMS in r or DO_ROLE_APPROVER in r


def can_manage_reports() -> bool:
    """Check if the user can access the Reports management page."""
    r = _get_user_do_roles()
    return DO_MGMT_REPORTS in r or DO_ROLE_APPROVER in r


def has_any_management_role() -> bool:
    """Check if the user has at least one management role."""
    return (can_manage_products() or can_manage_customers()
            or can_manage_grms() or can_manage_reports())


def has_any_order_role() -> bool:
    """
    Check if the user has any order-flow role (creator/finance/logistics/approver).
    If the user ONLY has management roles (e.g. only do_mgmt_reports),
    the main order dashboard should be hidden.

    Uses get_do_role() for the primary order-flow role AND checks
    _get_user_do_roles() for explicit assignments.  A user who has
    explicit module roles (from Intra_Admin_UserModuleRole) but NONE
    of them are order-flow roles should NOT see the dashboard.
    """
    r = _get_user_do_roles()

    # If user has explicit DO module roles, check strictly
    if r:
        return bool(r & DO_ORDER_ROLES)

    # No explicit DO module roles at all.
    # Check system-level roles — admins always see the dashboard.
    sys_roles = session.get("roles", []) or []
    if isinstance(sys_roles, str):
        sys_roles = [sys_roles]
    sys_lower = {r.lower() for r in sys_roles}
    if "admin" in sys_lower or "it_admin" in sys_lower:
        return True

    # Legacy user with no explicit module roles and no admin status.
    # Show dashboard (backward compatibility — treated as creator).
    return True

def can_create_order() -> bool:
    """Only creators and approvers can create new orders.

    If the user has explicit DO roles, check for creator/approver.
    If no explicit roles at all (legacy), fall back to allowing creation.
    """
    r = _get_user_do_roles()
    if not r:
        # Legacy user with no explicit module roles — treat as creator
        return True
    return DO_ROLE_CREATOR in r or DO_ROLE_APPROVER in r


def can_edit_order(order: dict) -> bool:
    """
    Only the creator of the order (or an approver) can edit,
    and only when the order is in DRAFT or REJECTED status.
    """
    if order.get("Status") not in ("DRAFT", "REJECTED"):
        return False
    do_role = get_do_role()
    if do_role == DO_ROLE_APPROVER:
        return True
    emp_id = session.get("emp_id")
    return str(order.get("Created_by")) == str(emp_id)


def can_transition(order: dict, new_status: str) -> bool:
    """
    Check if the current user is allowed to perform a particular
    status transition based on their DO role.

    Transition permissions:
      DRAFT → SUBMITTED        : creator (owner) or approver
      DRAFT → CANCELLED        : creator (owner) or approver
      SUBMITTED → PRICE AGREED : finance or approver
      SUBMITTED → NEED ATTACHMENT : finance or approver
      SUBMITTED → REJECTED     : finance or approver
      PRICE AGREED → CONFIRMED : logistics or approver
      PRICE AGREED → CANCELLED : logistics or approver
      CONFIRMED → NEED ATTACHMENT : finance or approver
      NEED ATTACHMENT → CONFIRMED : logistics or approver
      REJECTED → DRAFT         : creator (owner) or approver
    """
    current_status = order.get("Status", "")
    do_role = get_do_role()
    emp_id = session.get("emp_id")
    is_owner = str(order.get("Created_by")) == str(emp_id)

    transition = (current_status, new_status)

    # Creator (owner) transitions
    creator_transitions = {
        ("DRAFT", "SUBMITTED"),
        ("DRAFT", "CANCELLED"),
        ("DRAFT", "PENDING CUSTOMER APPROVAL"),
        ("REJECTED", "DRAFT"),
        ("PENDING CUSTOMER APPROVAL", "DRAFT"),
    }

    # Customer Manager transitions — approve/reject ownership-flagged orders
    customer_manager_transitions = {
        ("PENDING CUSTOMER APPROVAL", "SUBMITTED"),
        ("PENDING CUSTOMER APPROVAL", "REJECTED"),
    }

    # Logistics / approver transitions (confirm after price agreed)
    logistics_transitions = {
        ("PRICE AGREED", "CONFIRMED"),
        ("PRICE AGREED", "CANCELLED"),
        ("NEED ATTACHMENT", "CONFIRMED"),
        ("CONFIRMED", "CUSTOMS DOCUMENT UPDATED"),
    }

    # Finance transitions (price agree, need attachment, reject)
    finance_transitions = {
        ("SUBMITTED", "PRICE AGREED"),
        ("SUBMITTED", "NEED ATTACHMENT"),
        ("SUBMITTED", "REJECTED"),
        ("CONFIRMED", "NEED ATTACHMENT"),
    }

    # Creator transitions for post-delivery (sales team)
    creator_post_delivery = {
        ("CUSTOMS DOCUMENT UPDATED", "DELIVERED"),
    }

    if transition in creator_transitions:
        return is_owner or do_role == DO_ROLE_APPROVER

    if transition in customer_manager_transitions:
        return do_role in (DO_ROLE_CUSTOMER_MANAGER, DO_ROLE_APPROVER)

    if transition in logistics_transitions:
        return do_role in (DO_ROLE_LOGISTICS, DO_ROLE_APPROVER)

    if transition in finance_transitions:
        return do_role in (DO_ROLE_FINANCE, DO_ROLE_APPROVER)

    if transition in creator_post_delivery:
        return do_role in (DO_ROLE_CREATOR, DO_ROLE_APPROVER)

    return False


def get_allowed_transitions(order: dict) -> list[str]:
    """
    Return the list of status transitions the current user is
    allowed to perform on the given order.
    """
    from services.delivery_order_service import STATUS_FLOW

    current = order.get("Status", "")
    possible = STATUS_FLOW.get(current, [])
    return [s for s in possible if can_transition(order, s)]


def get_visible_kpi_statuses() -> list[str]:
    """
    Return which KPI statuses are visible to the current user.
    Approvers and finance see all; creators see a focused subset.
    """
    do_role = get_do_role()
    if do_role in (DO_ROLE_APPROVER, DO_ROLE_FINANCE, DO_ROLE_LOGISTICS):
        return [
            "total", "drafts", "submitted", "price_agreed",
            "confirmed", "customs_updated", "delivered",
            "need_attach", "rejected", "cancelled",
        ]
    # Creators and logistics see a simpler view
    return [
        "total", "drafts", "submitted",
        "confirmed", "customs_updated", "delivered",
        "rejected", "cancelled",
    ]


def can_see_prices() -> bool:
    """
    Check if the current user can see price columns.
    Approvers and finance can always see prices.
    Creators can see prices if explicitly granted in the DB.
    """
    do_role = get_do_role()
    if do_role in (DO_ROLE_APPROVER, DO_ROLE_FINANCE):
        return True
    # For creators, check the pricing permission table
    emp_id = session.get("emp_id")
    if emp_id:
        from repos.delivery_order_repo import check_pricing_permission
        return check_pricing_permission(emp_id)
    return False


def needs_reject_reason(new_status: str) -> bool:
    """Check if a reject reason is required for this transition."""
    return new_status == "REJECTED"


def get_do_context() -> dict:
    """
    Build the full DO permission context to pass to templates.
    Call this in every DO controller route.
    """
    do_role = get_do_role()
    ctx = {
        "do_role": do_role,
        "is_do_admin": do_role == DO_ROLE_APPROVER,
        "is_do_finance": do_role == DO_ROLE_FINANCE,
        "is_do_logistics": do_role == DO_ROLE_LOGISTICS,
        "is_do_customer_manager": do_role == DO_ROLE_CUSTOMER_MANAGER,
        "is_do_creator": do_role == DO_ROLE_CREATOR,
        "can_create": can_create_order(),
        "can_see_prices": can_see_prices(),
        "reject_reasons": REJECT_REASONS,
        # Management section permissions (per-button)
        "can_manage_products": can_manage_products(),
        "can_manage_customers": can_manage_customers(),
        "can_manage_grms": can_manage_grms(),
        "can_manage_reports": can_manage_reports(),
        "has_any_management_role": has_any_management_role(),
        "has_any_order_role": has_any_order_role(),
    }
    return ctx
