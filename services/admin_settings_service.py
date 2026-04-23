"""
Admin Settings service — business logic layer.
Controller → Service → Repo
"""

import re
import time

from repos import admin_settings_repo as repo


# ═══════════════════════════════════════════════════════════════
#  AUTH-SOURCED USERS (cached, replaces local user list)
# ═══════════════════════════════════════════════════════════════

_auth_users_cache: dict = {'data': None, 'ts': 0}
_AUTH_USERS_TTL = 60  # seconds


def _normalize_emp_id(value) -> str | None:
    """Normalize Auth/local employee IDs to a comparable string form."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_email(value) -> str:
    return (value or "").strip().lower()


def _build_local_user_index(local_users: list[dict]) -> dict[str, dict]:
    by_email: dict[str, dict] = {}
    for user in local_users:
        email = _normalize_email(user.get("EmailAddress") or user.get("CredEmail"))
        if email and email not in by_email:
            by_email[email] = user
    return by_email


def clear_auth_users_cache() -> None:
    _auth_users_cache['data'] = None
    _auth_users_cache['ts'] = 0


def _auth_user_identifiers(auth_user: dict) -> set[str]:
    identifiers = {
        _normalize_emp_id(auth_user.get('emp_id')),
        _normalize_emp_id(auth_user.get('local_emp_id')),
        _normalize_emp_id(auth_user.get('auth_emp_id')),
    }
    return {identifier for identifier in identifiers if identifier}


def find_auth_user(app_id: str, user_id: int | str) -> dict | None:
    """Find an Auth user by local or Auth-side identifier."""
    target_id = _normalize_emp_id(user_id)
    if not target_id:
        return None

    for auth_user in get_auth_users(app_id):
        if target_id in _auth_user_identifiers(auth_user):
            return dict(auth_user)
    return None


def resolve_or_create_local_emp_id_from_auth_user(auth_user: dict,
                                                  create_if_missing: bool = False) -> int | None:
    """Resolve an Auth payload to the local numeric EmpID used by admin tables."""
    email = _normalize_email(auth_user.get('email'))
    if email:
        local_user = repo.get_user_by_email(email)
        if local_user and local_user.get('EmpID') is not None:
            return int(local_user['EmpID'])

    local_emp_id = _normalize_emp_id(auth_user.get('local_emp_id'))
    if local_emp_id and local_emp_id.isdigit():
        return int(local_emp_id)

    if not create_if_missing or not email:
        return None

    created_emp_id = repo.ensure_auth_shadow_user(
        first_name=auth_user.get('first_name', ''),
        last_name=auth_user.get('last_name', ''),
        email=auth_user.get('email', ''),
        group_id=int(auth_user.get('group_id') or 10),
    )
    clear_auth_users_cache()
    return created_emp_id


def resolve_or_create_local_emp_id(app_id: str, user_id: int | str,
                                   create_if_missing: bool = False) -> int | None:
    """Resolve a posted user identifier to the local numeric EmpID."""
    normalized_id = _normalize_emp_id(user_id)
    if normalized_id and normalized_id.isdigit():
        return int(normalized_id)

    auth_user = find_auth_user(app_id, user_id)
    if not auth_user:
        return None
    return resolve_or_create_local_emp_id_from_auth_user(
        auth_user,
        create_if_missing=create_if_missing,
    )


def get_auth_users(app_id: str) -> list[dict]:
    """Return Auth Platform users mapped to {emp_id, first_name, last_name, email}.
    Cached for 60 s to avoid hitting the API on every page load."""
    now = time.time()
    if _auth_users_cache['data'] is not None and now - _auth_users_cache['ts'] < _AUTH_USERS_TTL:
        return _auth_users_cache['data']

    from sdk import auth_client
    raw, _ = auth_client.get_app_users(app_id, page=1, per_page=500)
    local_by_email = _build_local_user_index(repo.get_all_users_full())
    users = []
    for au in (raw or []):
        auth_emp_id = _normalize_emp_id(
            au.get('employee_id') or au.get('employee_code') or au.get('emp_id')
        )
        email = au.get('email', '')
        local_user = local_by_email.get(_normalize_email(email))
        local_emp_id = _normalize_emp_id(local_user.get('EmpID')) if local_user else None
        users.append({
            'emp_id': local_emp_id or auth_emp_id or None,
            'local_emp_id': local_emp_id,
            'auth_emp_id': auth_emp_id,
            'first_name': au.get('first_name', ''),
            'last_name': au.get('last_name', ''),
            'email': email,
            'group_id': au.get('group_id'),
        })
    _auth_users_cache['data'] = users
    _auth_users_cache['ts'] = now
    return users


def enrich_module_role_users(all_users: list[dict], user_role_assignments: list[dict]) -> tuple[list[dict], list[dict]]:
    """Normalize user IDs and enrich role assignments with Auth user info."""
    normalized_users: list[dict] = []
    for auth_user in all_users:
        item = dict(auth_user)
        item['emp_id'] = _normalize_emp_id(item.get('emp_id'))
        item['local_emp_id'] = _normalize_emp_id(item.get('local_emp_id'))
        item['auth_emp_id'] = _normalize_emp_id(item.get('auth_emp_id'))
        normalized_users.append(item)

    auth_by_emp: dict[str, dict] = {}
    for auth_user in normalized_users:
        for identifier in _auth_user_identifiers(auth_user):
            auth_by_emp[identifier] = auth_user

    normalized_assignments: list[dict] = []
    for assignment in user_role_assignments:
        item = dict(assignment)
        item['emp_id'] = _normalize_emp_id(item.get('emp_id'))
        if not item.get('user_name'):
            auth_user = auth_by_emp.get(item.get('emp_id'), {})
            fallback_name = f"Emp #{item['emp_id']}" if item.get('emp_id') else 'Unknown User'
            item['user_name'] = f"{auth_user.get('first_name', '')} {auth_user.get('last_name', '')}".strip() or fallback_name
            item['user_email'] = auth_user.get('email', '')
        normalized_assignments.append(item)

    return normalized_users, normalized_assignments


# ═══════════════════════════════════════════════════════════════
#  USER MANAGEMENT (legacy, kept for internal repo lookups)
# ═══════════════════════════════════════════════════════════════

def list_users() -> list[dict]:
    return repo.get_all_users_full()


def get_user(emp_id: int | str) -> dict | None:
    return repo.get_user_by_empid(emp_id)


def create_user(data: dict) -> int:
    return repo.create_user(
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=data["email"],
        department_id=int(data["department_id"]),
        designation_id=int(data.get("designation_id") or 0),
        group_id=int(data.get("group_id") or 0),
        username=data["username"],
        password=data["password"],
    )


def update_user(emp_id: int | str, data: dict) -> None:
    repo.update_user(
        emp_id=emp_id,
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=data["email"],
        department_id=int(data["department_id"]),
        designation_id=int(data.get("designation_id") or 0),
        group_id=int(data.get("group_id") or 0),
        username=data["username"],
    )


def reset_password(emp_id: int, new_password: str) -> None:
    repo.reset_password(emp_id, new_password)


def delete_user(emp_id: int | str) -> None:
    repo.delete_user(emp_id)


def get_departments() -> list[dict]:
    return repo.get_departments()


def get_designations() -> list[dict]:
    return repo.get_designations()


# ── Permissions ────────────────────────────────────────────────

def get_user_permissions(emp_id: int) -> dict:
    return repo.get_user_permissions(emp_id)


def save_user_permissions(emp_id: int, data: dict) -> None:
    repo.upsert_user_permissions(
        emp_id=emp_id,
        it_admin=int(bool(data.get("it_admin"))),
        uploader=int(bool(data.get("uploader"))),
        approver=int(bool(data.get("approver"))),
        reviewer1=int(bool(data.get("reviewer1"))),
        reviewer2=int(bool(data.get("reviewer2"))),
    )


def get_user_access_groups(emp_id: int) -> list[int]:
    return repo.get_user_access_groups(emp_id)


def save_user_access_groups(emp_id: int, group_ids: list[int]) -> None:
    repo.set_user_access_groups(emp_id, group_ids)


def get_all_access_groups() -> list[dict]:
    return repo.get_all_access_groups()


# ═══════════════════════════════════════════════════════════════
#  RESTRICTED WORDS
# ═══════════════════════════════════════════════════════════════

def list_restricted_words() -> list[dict]:
    return repo.get_restricted_words()


def add_restricted_word(word: str, added_by: int) -> int:
    return repo.add_restricted_word(word, added_by)


def delete_restricted_word(word_id: int) -> None:
    repo.delete_restricted_word(word_id)


def check_text_for_restricted_words(text: str) -> list[str]:
    """
    Check any text input against restricted words.
    Returns list of found restricted words.
    """
    if not text:
        return []
    blocked = repo.get_all_restricted_words_set()
    if not blocked:
        return []
    words_in_text = set(re.findall(r'\b\w+\b', text.lower()))
    return sorted(words_in_text & blocked)


# ═══════════════════════════════════════════════════════════════
#  MODULE CONFIGURATION
# ═══════════════════════════════════════════════════════════════

def list_modules() -> list[dict]:
    return repo.get_all_modules()


def toggle_module(module_id: int, is_enabled: bool) -> None:
    repo.toggle_module(module_id, is_enabled)


def get_module(module_id: int) -> dict | None:
    return repo.get_module_by_id(module_id)


def get_module_group_access(module_id: int) -> list[dict]:
    return repo.get_module_group_access(module_id)


def save_module_group_access(module_id: int, group_settings: list[dict]) -> None:
    repo.set_module_group_access(module_id, group_settings)


def set_module_user_access(module_id: int, emp_id: int | str, is_enabled: bool) -> None:
    repo.set_module_user_access(module_id, emp_id, is_enabled)


def get_visible_modules(emp_id: int, user_group_ids: list[int]) -> list[dict]:
    """Get modules visible to a specific user (3-tier resolution)."""
    return repo.get_visible_modules_for_user(emp_id, user_group_ids)


# ═══════════════════════════════════════════════════════════════
#  PER-MODULE USER ROLES
# ═══════════════════════════════════════════════════════════════

# Available roles per module — keyed by module_key.
# Each entry: {role_key: display_label}.
MODULE_ROLES = {
    "delivery_orders": {
        "do_creator":         "Creator",
        "do_finance":         "Finance",
        "do_logistics":       "Logistics",
        "do_approver":        "Approver",
        "do_customer_manager": "Customer Manager",
        "do_mgmt_products":   "Manage Products",
        "do_mgmt_customers":  "Manage Customers",
        "do_mgmt_grms":       "Manage GRMS",
        "do_mgmt_reports":    "Manage Reports",
    },
    "dms": {
        "dms_uploader":  "Uploader",
        "dms_approver":  "Approver",
        "dms_reviewer":  "Reviewer",
    },
    "it_support": {
        "its_creator": "Creator",
        "its_admin":   "Admin",
    },
}


def get_available_roles_for_module(module_key: str) -> dict[str, str]:
    """Return {role_key: display_label} for a module (hardcoded + custom)."""
    roles = dict(MODULE_ROLES.get(module_key, {}))
    # Merge custom DB-defined roles
    custom = repo.get_custom_module_roles(module_key)
    for cr in custom:
        roles[cr["role_key"]] = cr["display_label"]
    return roles


def add_custom_role(module_key: str, role_key: str,
                    display_label: str, created_by: int) -> int:
    """Add a custom role for a module."""
    return repo.add_custom_module_role(module_key, role_key, display_label, created_by)


def delete_custom_role(role_id: int) -> None:
    """Delete a custom role."""
    repo.delete_custom_module_role(role_id)


def get_custom_roles(module_key: str) -> list[dict]:
    """Get custom roles for a module."""
    return repo.get_custom_module_roles(module_key)


def get_user_module_roles(module_id: int) -> list[dict]:
    """Get all user-role assignments for a module."""
    return repo.get_user_module_roles(module_id)


def get_user_roles_for_module(emp_id: int | str, module_id: int) -> list[str]:
    """Get role keys for a user in a specific module."""
    return repo.get_user_roles_for_module(emp_id, module_id)


def get_all_module_roles_for_user(emp_id: int | str) -> dict[str, list[str]]:
    """Get all module roles for a user. Returns {module_key: [role_keys]}."""
    return repo.get_all_module_roles_for_user(emp_id)


def assign_user_module_role(module_id: int, emp_id: int | str,
                            role_key: str, assigned_by: int) -> None:
    """Assign a role to a user for a module."""
    repo.assign_user_module_role(module_id, emp_id, role_key, assigned_by)


def revoke_user_module_role(module_id: int, emp_id: int | str,
                            role_key: str) -> None:
    """Remove a role from a user for a module."""
    repo.revoke_user_module_role(module_id, emp_id, role_key)


def set_user_module_roles(module_id: int, emp_id: int | str,
                          role_keys: list[str], assigned_by: int) -> None:
    """Replace all roles for a user in a module."""
    repo.set_user_module_roles(module_id, emp_id, role_keys, assigned_by)


# ═══════════════════════════════════════════════════════════════
#  WORKFLOW MANAGEMENT
# ═══════════════════════════════════════════════════════════════

WORKFLOW_MODULES = {
    "delivery_orders": "Delivery Orders",
    "dms":             "Document Management",
    "it_support":      "IT Support",
}

WORKFLOW_CONDITIONS = {
    "delivery_orders": {
        "always": "Always",
        "standard_submit": "Finance lane submit (initial submit, finance rejection, or logistics price change)",
        "ownership_required": "Ownership route required (Bill/Ship ownership is Yes or N/A)",
        "rejected_by_finance": "Resubmission after Finance rejection",
        "from_rejected_by_logistics": "From REJECTED BY LOGISTICS",
        "rejected_by_logistics_no_price_change": "Resubmission after Logistics rejection with no price change",
        "rejected_by_logistics_with_price_change": "Resubmission after Logistics rejection with price change",
    },
}


def _decode_transition_required_role(value: str | None) -> tuple[str, str]:
    raw = (value or "").strip()
    if not raw:
        return "", "always"
    if "|" in raw:
        role_key, condition_key = raw.split("|", 1)
        return role_key.strip(), (condition_key.strip() or "always")
    return raw, "always"


def _encode_transition_required_role(role_key: str, condition_key: str | None) -> str:
    rk = (role_key or "").strip()
    ck = (condition_key or "always").strip() or "always"
    if not rk:
        return ""
    if ck == "always":
        return rk
    return f"{rk}|{ck}"


def get_workflow_statuses(module_key: str) -> list[dict]:
    return repo.get_workflow_statuses(module_key)


def get_workflow_transitions(module_key: str) -> list[dict]:
    rows = repo.get_workflow_transitions(module_key)
    role_labels = get_available_roles_for_module(module_key)
    condition_labels = WORKFLOW_CONDITIONS.get(module_key, {"always": "Always"})

    enriched: list[dict] = []
    for row in rows:
        item = dict(row)
        role_key, condition_key = _decode_transition_required_role(item.get("required_role"))
        item["required_role_key"] = role_key
        item["condition_key"] = condition_key
        item["required_role_label"] = role_labels.get(role_key, role_key or "—")
        item["condition_label"] = condition_labels.get(condition_key, condition_key)
        enriched.append(item)
    return enriched


def get_workflow_transition_conditions(module_key: str) -> dict[str, str]:
    return dict(WORKFLOW_CONDITIONS.get(module_key, {"always": "Always"}))


def add_workflow_status(module_key: str, data: dict) -> int:
    return repo.add_workflow_status(
        module_key=module_key,
        status_key=data["status_key"],
        display_name=data["display_name"],
        sort_order=int(data.get("sort_order", 0)),
        is_terminal=bool(data.get("is_terminal")),
    )


def update_workflow_status(status_id: int, data: dict) -> None:
    repo.update_workflow_status(
        status_id=status_id,
        display_name=data["display_name"],
        sort_order=int(data.get("sort_order", 0)),
        is_terminal=bool(data.get("is_terminal")),
    )


def delete_workflow_status(status_id: int) -> None:
    repo.delete_workflow_status(status_id)


def add_workflow_transition(module_key: str, data: dict) -> int:
    encoded_role = _encode_transition_required_role(
        data.get("required_role") or "",
        data.get("condition_key") or "always",
    )
    return repo.add_workflow_transition(
        module_key=module_key,
        from_status=data["from_status"],
        to_status=data["to_status"],
        required_role=encoded_role or None,
    )


def update_workflow_transition_role(transition_id: int, required_role: str,
                                    condition_key: str = "always") -> None:
    encoded_role = _encode_transition_required_role(required_role, condition_key)
    repo.update_workflow_transition_role(transition_id, encoded_role)


def delete_workflow_transition(transition_id: int) -> None:
    repo.delete_workflow_transition(transition_id)


def get_status_flow(module_key: str) -> dict[str, list[str]]:
    """Get STATUS_FLOW dict from DB with fallback to hardcoded."""
    flow = repo.get_workflow_flow_dict(module_key)
    if flow:
        return flow
    # Fallback to hardcoded defaults
    return _HARDCODED_FLOWS.get(module_key, {})


_HARDCODED_FLOWS = {
    "delivery_orders": {
        "DRAFT":           ["SUBMITTED", "PRICE AGREED", "PENDING CUSTOMER APPROVAL", "CANCELLED"],
        "PENDING CUSTOMER APPROVAL": ["SUBMITTED", "REJECTED", "DRAFT"],
        "SUBMITTED":       ["PRICE AGREED", "NEED ATTACHMENT", "REJECTED"],
        "PRICE AGREED":    ["CONFIRMED", "REJECTED", "CANCELLED"],
        "CONFIRMED":       ["NEED ATTACHMENT", "CUSTOMS DOCUMENT UPDATED"],
        "CUSTOMS DOCUMENT UPDATED": ["DELIVERED"],
        "DELIVERED":       [],
        "NEED ATTACHMENT": ["CONFIRMED"],
        "REJECTED":        ["DRAFT"],
        "CANCELLED":       [],
    },
    "dms": {
        "1": ["2", "9"],
        "2": ["3", "4"],
        "3": ["7", "8"],
        "4": ["1"],
        "7": [],
        "8": ["1"],
        "9": [],
    },
    "it_support": {
        "open":        ["in_progress", "closed"],
        "in_progress": ["open", "closed"],
        "closed":      ["open"],
    },
}
