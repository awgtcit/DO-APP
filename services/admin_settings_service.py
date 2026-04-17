"""
Admin Settings service — business logic layer.
Controller → Service → Repo
"""

import re

from repos import admin_settings_repo as repo


# ═══════════════════════════════════════════════════════════════
#  USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════

def list_users() -> list[dict]:
    return repo.get_all_users_full()


def get_user(emp_id: int) -> dict | None:
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


def update_user(emp_id: int, data: dict) -> None:
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


def delete_user(emp_id: int) -> None:
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


def set_module_user_access(module_id: int, emp_id: int, is_enabled: bool) -> None:
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
        "do_creator":       "Creator",
        "do_finance":       "Finance",
        "do_logistics":     "Logistics",
        "do_approver":      "Approver",
        "do_mgmt_products":  "Manage Products",
        "do_mgmt_customers": "Manage Customers",
        "do_mgmt_grms":      "Manage GRMS",
        "do_mgmt_reports":   "Manage Reports",
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


def get_user_roles_for_module(emp_id: int, module_id: int) -> list[str]:
    """Get role keys for a user in a specific module."""
    return repo.get_user_roles_for_module(emp_id, module_id)


def get_all_module_roles_for_user(emp_id: int) -> dict[str, list[str]]:
    """Get all module roles for a user. Returns {module_key: [role_keys]}."""
    return repo.get_all_module_roles_for_user(emp_id)


def assign_user_module_role(module_id: int, emp_id: int,
                            role_key: str, assigned_by: int) -> None:
    """Assign a role to a user for a module."""
    repo.assign_user_module_role(module_id, emp_id, role_key, assigned_by)


def revoke_user_module_role(module_id: int, emp_id: int,
                            role_key: str) -> None:
    """Remove a role from a user for a module."""
    repo.revoke_user_module_role(module_id, emp_id, role_key)


def set_user_module_roles(module_id: int, emp_id: int,
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


def get_workflow_statuses(module_key: str) -> list[dict]:
    return repo.get_workflow_statuses(module_key)


def get_workflow_transitions(module_key: str) -> list[dict]:
    return repo.get_workflow_transitions(module_key)


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
    return repo.add_workflow_transition(
        module_key=module_key,
        from_status=data["from_status"],
        to_status=data["to_status"],
        required_role=data.get("required_role") or None,
    )


def update_workflow_transition_role(transition_id: int, required_role: str) -> None:
    repo.update_workflow_transition_role(transition_id, required_role)


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
        "DRAFT":           ["SUBMITTED", "CANCELLED"],
        "SUBMITTED":       ["PRICE AGREED", "NEED ATTACHMENT", "REJECTED"],
        "PRICE AGREED":    ["CONFIRMED", "CANCELLED"],
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
