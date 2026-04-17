"""
Admin Settings controller — all /admin/settings routes.
Protected by @role_required("admin", "it_admin").
"""

from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for,
    jsonify,
)

from auth.middleware import login_required, role_required
from services import admin_settings_service as svc
from rules.admin_settings_rules import (
    validate_user,
    validate_password_reset,
    validate_restricted_word,
    validate_workflow_status,
    validate_workflow_transition,
)

admin_settings_bp = Blueprint(
    "admin_settings",
    __name__,
    url_prefix="/admin/settings",
    template_folder="../templates/admin_settings",
)


# ═══════════════════════════════════════════════════════════════
#  DASHBOARD / LANDING
# ═══════════════════════════════════════════════════════════════

@admin_settings_bp.route("/")
@login_required
@role_required("admin", "it_admin")
def index():
    return render_template("admin_settings/index.html")


# ═══════════════════════════════════════════════════════════════
#  USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@admin_settings_bp.route("/users")
@login_required
@role_required("admin", "it_admin")
def users():
    all_users = svc.list_users()
    return render_template("admin_settings/users.html", users=all_users)


@admin_settings_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "it_admin")
def user_create():
    departments = svc.get_departments()
    designations = svc.get_designations()

    if request.method == "POST":
        data = {
            "first_name": request.form.get("first_name", "").strip(),
            "last_name": request.form.get("last_name", "").strip(),
            "email": request.form.get("email", "").strip(),
            "username": request.form.get("username", "").strip(),
            "password": request.form.get("password", ""),
            "department_id": request.form.get("department_id"),
            "designation_id": request.form.get("designation_id"),
            "group_id": request.form.get("group_id", "0"),
        }
        errors = validate_user(data, is_new=True)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "admin_settings/user_form.html",
                mode="create", data=data,
                departments=departments, designations=designations,
            )
        try:
            new_id = svc.create_user(data)
            flash(f"User created successfully (ID: {new_id}).", "success")
            return redirect(url_for("admin_settings.users"))
        except Exception as exc:
            flash(f"Error creating user: {exc}", "danger")
            return render_template(
                "admin_settings/user_form.html",
                mode="create", data=data,
                departments=departments, designations=designations,
            )

    return render_template(
        "admin_settings/user_form.html",
        mode="create", data={},
        departments=departments, designations=designations,
    )


@admin_settings_bp.route("/users/<int:emp_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin", "it_admin")
def user_edit(emp_id):
    user = svc.get_user(emp_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("admin_settings.users"))

    departments = svc.get_departments()
    designations = svc.get_designations()

    if request.method == "POST":
        data = {
            "first_name": request.form.get("first_name", "").strip(),
            "last_name": request.form.get("last_name", "").strip(),
            "email": request.form.get("email", "").strip(),
            "username": request.form.get("username", "").strip(),
            "department_id": request.form.get("department_id"),
            "designation_id": request.form.get("designation_id"),
            "group_id": request.form.get("group_id", "0"),
        }
        errors = validate_user(data, is_new=False)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "admin_settings/user_form.html",
                mode="edit", data=data, user=user,
                departments=departments, designations=designations,
            )
        try:
            svc.update_user(emp_id, data)
            flash("User updated successfully.", "success")
            return redirect(url_for("admin_settings.users"))
        except Exception as exc:
            flash(f"Error updating user: {exc}", "danger")
            return render_template(
                "admin_settings/user_form.html",
                mode="edit", data=data, user=user,
                departments=departments, designations=designations,
            )

    data = {
        "first_name": user.get("FirstName", ""),
        "last_name": user.get("LastName", ""),
        "email": user.get("EmailAddress", ""),
        "username": user.get("CredUsername", ""),
        "department_id": user.get("DeparmentID"),
        "designation_id": user.get("DesignationID"),
        "group_id": user.get("GroupID", 0),
    }
    return render_template(
        "admin_settings/user_form.html",
        mode="edit", data=data, user=user,
        departments=departments, designations=designations,
    )


@admin_settings_bp.route("/users/<int:emp_id>/reset-password", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def user_reset_password(emp_id):
    new_password = request.form.get("new_password", "")
    errors = validate_password_reset(new_password)
    if errors:
        for e in errors:
            flash(e, "danger")
        return redirect(url_for("admin_settings.user_edit", emp_id=emp_id))

    svc.reset_password(emp_id, new_password)
    flash("Password reset successfully.", "success")
    return redirect(url_for("admin_settings.user_edit", emp_id=emp_id))


@admin_settings_bp.route("/users/<int:emp_id>/delete", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def user_delete(emp_id):
    try:
        svc.delete_user(emp_id)
        flash("User deleted successfully.", "success")
    except Exception as exc:
        flash(f"Error deleting user: {exc}", "danger")
    return redirect(url_for("admin_settings.users"))


# ── User Permissions ──────────────────────────────────────────

@admin_settings_bp.route("/users/<int:emp_id>/permissions", methods=["GET", "POST"])
@login_required
@role_required("admin", "it_admin")
def user_permissions(emp_id):
    user = svc.get_user(emp_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("admin_settings.users"))

    if request.method == "POST":
        perm_data = {
            "it_admin": request.form.get("it_admin"),
            "uploader": request.form.get("uploader"),
            "approver": request.form.get("approver"),
            "reviewer1": request.form.get("reviewer1"),
            "reviewer2": request.form.get("reviewer2"),
        }
        svc.save_user_permissions(emp_id, perm_data)

        # Save access groups
        group_ids = request.form.getlist("access_groups", type=int)
        svc.save_user_access_groups(emp_id, group_ids)

        flash("Permissions updated successfully.", "success")
        return redirect(url_for("admin_settings.user_permissions", emp_id=emp_id))

    permissions = svc.get_user_permissions(emp_id)
    user_groups = svc.get_user_access_groups(emp_id)
    all_groups = svc.get_all_access_groups()

    return render_template(
        "admin_settings/user_permissions.html",
        user=user, permissions=permissions,
        user_groups=user_groups, all_groups=all_groups,
    )


# ═══════════════════════════════════════════════════════════════
#  RESTRICTED WORDS
# ═══════════════════════════════════════════════════════════════

@admin_settings_bp.route("/restricted-words", methods=["GET", "POST"])
@login_required
@role_required("admin", "it_admin")
def restricted_words():
    if request.method == "POST":
        word = request.form.get("word", "").strip()
        errors = validate_restricted_word(word)
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            try:
                svc.add_restricted_word(word, session.get("emp_id", 0))
                flash(f"Word '{word}' added to restricted list.", "success")
            except Exception as exc:
                if "UQ_RestrictedWord" in str(exc):
                    flash(f"Word '{word}' is already in the restricted list.", "warning")
                else:
                    flash(f"Error adding word: {exc}", "danger")
        return redirect(url_for("admin_settings.restricted_words"))

    words = svc.list_restricted_words()
    return render_template("admin_settings/restricted_words.html", words=words)


@admin_settings_bp.route("/restricted-words/<int:word_id>/delete", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def restricted_word_delete(word_id):
    svc.delete_restricted_word(word_id)
    flash("Word removed from restricted list.", "success")
    return redirect(url_for("admin_settings.restricted_words"))


# ═══════════════════════════════════════════════════════════════
#  MODULE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@admin_settings_bp.route("/modules")
@login_required
@role_required("admin", "it_admin")
def modules():
    all_modules = svc.list_modules()
    return render_template("admin_settings/modules.html", modules=all_modules)


@admin_settings_bp.route("/modules/<int:module_id>/toggle", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def module_toggle(module_id):
    is_enabled = request.form.get("is_enabled") == "1"
    svc.toggle_module(module_id, is_enabled)
    mod = svc.get_module(module_id)
    name = mod["display_name"] if mod else "Module"
    flash(f"{name} {'enabled' if is_enabled else 'disabled'}.", "success")
    return redirect(url_for("admin_settings.modules"))


@admin_settings_bp.route("/modules/<int:module_id>/access", methods=["GET", "POST"])
@login_required
@role_required("admin", "it_admin")
def module_access(module_id):
    mod = svc.get_module(module_id)
    if not mod:
        flash("Module not found.", "danger")
        return redirect(url_for("admin_settings.modules"))

    if request.method == "POST":
        action = request.form.get("action")

        if action == "save_groups":
            all_groups = svc.get_all_access_groups()
            group_settings = []
            for g in all_groups:
                gid = g["id"]
                enabled = request.form.get(f"group_{gid}") == "1"
                group_settings.append({"group_id": gid, "is_enabled": enabled})
            svc.save_module_group_access(module_id, group_settings)
            flash("Group access updated.", "success")

        elif action == "save_user":
            user_emp_id = request.form.get("emp_id", type=int)
            user_enabled = request.form.get("user_enabled") == "1"
            if user_emp_id:
                svc.set_module_user_access(module_id, user_emp_id, user_enabled)
                flash("User access updated.", "success")

        elif action == "assign_role":
            user_emp_id = request.form.get("emp_id", type=int)
            role_key = request.form.get("role_key", "").strip()
            if user_emp_id and role_key:
                assigned_by = session.get("emp_id") or 0
                svc.assign_user_module_role(
                    module_id, user_emp_id, role_key, assigned_by
                )
                flash(f"Role assigned.", "success")

        elif action == "revoke_role":
            user_emp_id = request.form.get("emp_id", type=int)
            role_key = request.form.get("role_key", "").strip()
            if user_emp_id and role_key:
                svc.revoke_user_module_role(module_id, user_emp_id, role_key)
                flash("Role revoked.", "success")

        elif action == "set_user_roles":
            user_emp_id = request.form.get("emp_id", type=int)
            available = svc.get_available_roles_for_module(mod["module_key"])
            selected = [
                rk for rk in available
                if request.form.get(f"role_{rk}") == "1"
            ]
            if user_emp_id:
                assigned_by = session.get("emp_id") or 0
                svc.set_user_module_roles(
                    module_id, user_emp_id, selected, assigned_by
                )
                flash("User roles updated.", "success")

        elif action == "add_role":
            role_key = request.form.get("role_key", "").strip().lower().replace(" ", "_")
            display_label = request.form.get("display_label", "").strip()
            if role_key and display_label:
                try:
                    created_by = session.get("emp_id") or 0
                    svc.add_custom_role(mod["module_key"], role_key, display_label, created_by)
                    flash(f"Role '{display_label}' added.", "success")
                except Exception as exc:
                    flash(f"Error adding role: {exc}", "danger")
            else:
                flash("Role key and label are required.", "danger")

        elif action == "delete_role":
            role_id = request.form.get("role_config_id", type=int)
            if role_id:
                svc.delete_custom_role(role_id)
                flash("Custom role removed.", "success")

        return redirect(url_for("admin_settings.module_access", module_id=module_id))

    all_groups = svc.get_all_access_groups()
    group_access = svc.get_module_group_access(module_id)
    group_access_map = {ga["group_id"]: ga["is_enabled"] for ga in group_access}
    user_access = []
    try:
        from repos.admin_settings_repo import get_module_user_access
        user_access = get_module_user_access(module_id)
    except Exception:
        pass
    all_users = svc.list_users()

    # Per-module roles
    available_roles = svc.get_available_roles_for_module(mod["module_key"])
    custom_roles = svc.get_custom_roles(mod["module_key"])
    builtin_role_keys = set(svc.MODULE_ROLES.get(mod["module_key"], {}).keys())
    user_role_assignments = svc.get_user_module_roles(module_id)

    # Build role_users_map: {role_key: [user_assignment_dicts]}
    role_users_map: dict[str, list[dict]] = {rk: [] for rk in available_roles}
    for ura in user_role_assignments:
        rk = ura["role_key"]
        if rk in role_users_map:
            role_users_map[rk].append(ura)

    # Set of emp_ids already assigned to each role (for the "add" dropdown)
    role_assigned_ids: dict[str, set[int]] = {
        rk: {u["emp_id"] for u in users}
        for rk, users in role_users_map.items()
    }

    return render_template(
        "admin_settings/module_access.html",
        module=mod, all_groups=all_groups,
        group_access_map=group_access_map,
        user_access=user_access, all_users=all_users,
        available_roles=available_roles,
        custom_roles=custom_roles,
        builtin_role_keys=builtin_role_keys,
        role_users_map=role_users_map,
        role_assigned_ids=role_assigned_ids,
    )


# ═══════════════════════════════════════════════════════════════
#  WORKFLOW MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@admin_settings_bp.route("/workflow")
@login_required
@role_required("admin", "it_admin")
def workflow():
    module_key = request.args.get("module", "delivery_orders")
    statuses = svc.get_workflow_statuses(module_key)
    transitions = svc.get_workflow_transitions(module_key)
    available_roles = svc.get_available_roles_for_module(module_key)
    return render_template(
        "admin_settings/workflow.html",
        module_key=module_key,
        workflow_modules=svc.WORKFLOW_MODULES,
        statuses=statuses,
        transitions=transitions,
        available_roles=available_roles,
    )


@admin_settings_bp.route("/workflow/status/add", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def workflow_status_add():
    module_key = request.form.get("module_key", "delivery_orders")
    data = {
        "status_key": request.form.get("status_key", "").strip().upper(),
        "display_name": request.form.get("display_name", "").strip(),
        "sort_order": request.form.get("sort_order", "0"),
        "is_terminal": request.form.get("is_terminal"),
    }
    errors = validate_workflow_status(data)
    if errors:
        for e in errors:
            flash(e, "danger")
    else:
        try:
            svc.add_workflow_status(module_key, data)
            flash("Status added.", "success")
        except Exception as exc:
            flash(f"Error: {exc}", "danger")
    return redirect(url_for("admin_settings.workflow", module=module_key))


@admin_settings_bp.route("/workflow/status/<int:status_id>/edit", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def workflow_status_edit(status_id):
    module_key = request.form.get("module_key", "delivery_orders")
    data = {
        "display_name": request.form.get("display_name", "").strip(),
        "sort_order": request.form.get("sort_order", "0"),
        "is_terminal": request.form.get("is_terminal"),
    }
    svc.update_workflow_status(status_id, data)
    flash("Status updated.", "success")
    return redirect(url_for("admin_settings.workflow", module=module_key))


@admin_settings_bp.route("/workflow/status/<int:status_id>/delete", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def workflow_status_delete(status_id):
    module_key = request.form.get("module_key", "delivery_orders")
    svc.delete_workflow_status(status_id)
    flash("Status and related transitions deleted.", "success")
    return redirect(url_for("admin_settings.workflow", module=module_key))


@admin_settings_bp.route("/workflow/transition/add", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def workflow_transition_add():
    module_key = request.form.get("module_key", "delivery_orders")
    data = {
        "from_status": request.form.get("from_status", "").strip(),
        "to_status": request.form.get("to_status", "").strip(),
        "required_role": request.form.get("required_role", "").strip(),
    }
    errors = validate_workflow_transition(data)
    if errors:
        for e in errors:
            flash(e, "danger")
    else:
        try:
            svc.add_workflow_transition(module_key, data)
            flash("Transition added.", "success")
        except Exception as exc:
            flash(f"Error: {exc}", "danger")
    return redirect(url_for("admin_settings.workflow", module=module_key))


@admin_settings_bp.route("/workflow/transition/<int:transition_id>/edit", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def workflow_transition_edit(transition_id):
    module_key = request.form.get("module_key", "delivery_orders")
    required_role = request.form.get("required_role", "").strip()
    if required_role:
        svc.update_workflow_transition_role(transition_id, required_role)
        flash("Transition role updated.", "success")
    else:
        flash("Role is required.", "danger")
    return redirect(url_for("admin_settings.workflow", module=module_key))


@admin_settings_bp.route("/workflow/transition/<int:transition_id>/delete", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def workflow_transition_delete(transition_id):
    module_key = request.form.get("module_key", "delivery_orders")
    svc.delete_workflow_transition(transition_id)
    flash("Transition removed.", "success")
    return redirect(url_for("admin_settings.workflow", module=module_key))


# ═══════════════════════════════════════════════════════════════
#  API: Restricted word check (for AJAX validation)
# ═══════════════════════════════════════════════════════════════

@admin_settings_bp.route("/api/check-words", methods=["POST"])
@login_required
def api_check_words():
    """Real-time restricted word check for form inputs."""
    text = request.json.get("text", "") if request.is_json else ""
    found = svc.check_text_for_restricted_words(text)
    return jsonify({"blocked": found})


@admin_settings_bp.route("/api/restricted-words-list")
@login_required
def api_restricted_words_list():
    """Return all restricted words as a JSON array (for client-side filtering)."""
    from repos.admin_settings_repo import get_all_restricted_words_set
    words = sorted(get_all_restricted_words_set())
    return jsonify({"words": words})
