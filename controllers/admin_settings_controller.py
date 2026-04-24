"""
Admin controller — all /admin routes.
Merges settings (modules, restricted words, workflow) and
Auth-sourced user listing into a single admin panel.
Protected by @role_required("admin", "it_admin").
"""

import logging
import os

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for,
    jsonify, current_app,
)
from werkzeug.routing import BuildError

from auth.middleware import login_required, role_required
from services import admin_settings_service as svc
from services import email_admin_service
from rules.admin_settings_rules import (
    validate_restricted_word,
    validate_workflow_status,
    validate_workflow_transition,
)
from sdk import auth_client
from repos.delivery_order_repo import get_order_by_id, get_order_items
from services.do_email_service import send_do_status_email

logger = logging.getLogger(__name__)

admin_settings_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="../templates/admin_settings",
)


@admin_settings_bp.app_context_processor
def _admin_embed_ctx():
    """Inject embed-mode variables into all templates."""
    embed = (
        request.args.get('embed') == '1'
        or request.form.get('embed') == '1'
        or session.get('embed_mode', False)
    )
    return dict(
        base_template='base_embed.html' if embed else 'base.html',
        embed_mode=embed,
        embed_token=getattr(g, 'embed_session_token', ''),
    )


# ═══════════════════════════════════════════════════════════════
#  DASHBOARD / LANDING
# ═══════════════════════════════════════════════════════════════

@admin_settings_bp.route("/")
@login_required
@role_required("admin", "it_admin")
def index():
    # Defensive: avoid hard failure if an optional admin endpoint is unavailable.
    try:
        database_url = url_for("admin.database")
    except BuildError:
        database_url = None
    return render_template("admin_settings/index.html", database_url=database_url)


# ═══════════════════════════════════════════════════════════════
#  USERS — Auth-sourced (read-only, assigned to this app)
# ═══════════════════════════════════════════════════════════════

@admin_settings_bp.route("/users")
@login_required
@role_required("admin", "it_admin")
def users():
    """Show users assigned to this application via Auth Platform."""
    app_id = current_app.config.get('AUTH_APP_APPLICATION_ID', '')
    page = request.args.get('page', 1, type=int)
    users_list, meta = auth_client.get_app_users(app_id, page=page, per_page=30)
    if users_list is None:
        users_list = []
        meta = {}
        flash("Could not load users from Auth Platform.", "warning")
    return render_template("admin_settings/users.html",
                           users=users_list, meta=meta, page=page)


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
        return redirect(url_for("admin.restricted_words"))

    words = svc.list_restricted_words()
    return render_template("admin_settings/restricted_words.html", words=words)


@admin_settings_bp.route("/restricted-words/<int:word_id>/delete", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def restricted_word_delete(word_id):
    svc.delete_restricted_word(word_id)
    flash("Word removed from restricted list.", "success")
    return redirect(url_for("admin.restricted_words"))


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
    return redirect(url_for("admin.modules"))


@admin_settings_bp.route("/modules/<int:module_id>/access", methods=["GET", "POST"])
@login_required
@role_required("admin", "it_admin")
def module_access(module_id):
    mod = svc.get_module(module_id)
    if not mod:
        flash("Module not found.", "danger")
        return redirect(url_for("admin.modules"))

    app_id = current_app.config.get('AUTH_APP_APPLICATION_ID', '')

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
            user_emp_id = request.form.get("emp_id", "").strip()
            user_enabled = request.form.get("user_enabled") == "1"
            if user_emp_id:
                resolved_emp_id = svc.resolve_or_create_local_emp_id(
                    app_id,
                    user_emp_id,
                    create_if_missing=True,
                )
                if resolved_emp_id is None:
                    flash("Unable to resolve the selected user to a local employee record.", "danger")
                else:
                    svc.set_module_user_access(module_id, resolved_emp_id, user_enabled)
                    flash("User access updated.", "success")

        elif action == "assign_role":
            user_emp_id = request.form.get("emp_id", "").strip()
            role_key = request.form.get("role_key", "").strip()
            if user_emp_id and role_key:
                resolved_emp_id = svc.resolve_or_create_local_emp_id(
                    app_id,
                    user_emp_id,
                    create_if_missing=True,
                )
                if resolved_emp_id is None:
                    flash("Unable to resolve the selected user to a local employee record.", "danger")
                else:
                    assigned_by = session.get("emp_id") or 0
                    svc.assign_user_module_role(
                        module_id, resolved_emp_id, role_key, assigned_by
                    )
                    flash("Role assigned.", "success")

        elif action == "revoke_role":
            user_emp_id = request.form.get("emp_id", "").strip()
            role_key = request.form.get("role_key", "").strip()
            if user_emp_id and role_key:
                resolved_emp_id = svc.resolve_or_create_local_emp_id(
                    app_id,
                    user_emp_id,
                    create_if_missing=False,
                )
                if resolved_emp_id is None:
                    flash("Unable to resolve the selected user to a local employee record.", "danger")
                else:
                    svc.revoke_user_module_role(module_id, resolved_emp_id, role_key)
                    flash("Role revoked.", "success")

        elif action == "set_user_roles":
            user_emp_id = request.form.get("emp_id", "").strip()
            available = svc.get_available_roles_for_module(mod["module_key"])
            selected = [
                rk for rk in available
                if request.form.get(f"role_{rk}") == "1"
            ]
            if user_emp_id:
                resolved_emp_id = svc.resolve_or_create_local_emp_id(
                    app_id,
                    user_emp_id,
                    create_if_missing=True,
                )
                if resolved_emp_id is None:
                    flash("Unable to resolve the selected user to a local employee record.", "danger")
                else:
                    assigned_by = session.get("emp_id") or 0
                    svc.set_user_module_roles(
                        module_id, resolved_emp_id, selected, assigned_by
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

        return redirect(url_for("admin.module_access", module_id=module_id))

    all_groups = svc.get_all_access_groups()
    group_access = svc.get_module_group_access(module_id)
    group_access_map = {ga["group_id"]: ga["is_enabled"] for ga in group_access}
    user_access = []
    try:
        from repos.admin_settings_repo import get_module_user_access
        user_access = get_module_user_access(module_id)
    except Exception:
        pass

    # Fetch users from Auth Platform (cached in service layer)
    all_users = svc.get_auth_users(app_id)

    # Per-module roles
    available_roles = svc.get_available_roles_for_module(mod["module_key"])
    custom_roles = svc.get_custom_roles(mod["module_key"])
    builtin_role_keys = set(svc.MODULE_ROLES.get(mod["module_key"], {}).keys())
    user_role_assignments = svc.get_user_module_roles(module_id)
    all_users, user_role_assignments = svc.enrich_module_role_users(all_users, user_role_assignments)

    # Build role_users_map: {role_key: [user_assignment_dicts]}
    role_users_map: dict[str, list[dict]] = {rk: [] for rk in available_roles}
    for ura in user_role_assignments:
        rk = ura["role_key"]
        if rk in role_users_map:
            role_users_map[rk].append(ura)

    # Set of emp_ids already assigned to each role (for the "add" dropdown)
    role_assigned_ids: dict[str, set[str]] = {
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
    transition_conditions = svc.get_workflow_transition_conditions(module_key)
    return render_template(
        "admin_settings/workflow.html",
        module_key=module_key,
        workflow_modules=svc.WORKFLOW_MODULES,
        statuses=statuses,
        transitions=transitions,
        available_roles=available_roles,
        transition_conditions=transition_conditions,
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
    return redirect(url_for("admin.workflow", module=module_key))


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
    return redirect(url_for("admin.workflow", module=module_key))


@admin_settings_bp.route("/workflow/status/<int:status_id>/delete", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def workflow_status_delete(status_id):
    module_key = request.form.get("module_key", "delivery_orders")
    svc.delete_workflow_status(status_id)
    flash("Status and related transitions deleted.", "success")
    return redirect(url_for("admin.workflow", module=module_key))


@admin_settings_bp.route("/workflow/transition/add", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def workflow_transition_add():
    module_key = request.form.get("module_key", "delivery_orders")
    data = {
        "from_status": request.form.get("from_status", "").strip(),
        "to_status": request.form.get("to_status", "").strip(),
        "required_role": request.form.get("required_role", "").strip(),
        "condition_key": request.form.get("condition_key", "always").strip() or "always",
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
    return redirect(url_for("admin.workflow", module=module_key))


@admin_settings_bp.route("/workflow/transition/<int:transition_id>/edit", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def workflow_transition_edit(transition_id):
    module_key = request.form.get("module_key", "delivery_orders")
    required_role = request.form.get("required_role", "").strip()
    condition_key = request.form.get("condition_key", "always").strip() or "always"
    if required_role:
        svc.update_workflow_transition_role(transition_id, required_role, condition_key)
        flash("Transition updated.", "success")
    else:
        flash("Role is required.", "danger")
    return redirect(url_for("admin.workflow", module=module_key))


@admin_settings_bp.route("/workflow/transition/<int:transition_id>/delete", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def workflow_transition_delete(transition_id):
    module_key = request.form.get("module_key", "delivery_orders")
    svc.delete_workflow_transition(transition_id)
    flash("Transition removed.", "success")
    return redirect(url_for("admin.workflow", module=module_key))


# ═══════════════════════════════════════════════════════════════
#  EMAIL CONFIGURATION (SMTP + WORKFLOW EMAIL)
# ═══════════════════════════════════════════════════════════════

@admin_settings_bp.route("/email-config")
@login_required
@role_required("admin", "it_admin")
def email_config():
    module_key = request.args.get("module", "delivery_orders")
    status_key = (request.args.get("status", "") or "").strip().upper()
    statuses = svc.get_workflow_statuses(module_key)
    if not status_key and statuses:
        confirmed = next((s for s in statuses if (s.get("status_key") or "").upper() == "CONFIRMED"), None)
        status_key = (confirmed or statuses[0]).get("status_key") or ""
    users = email_admin_service.get_recipient_users()
    actor = session.get("emp_id") or 0

    try:
        if module_key == "delivery_orders":
            email_admin_service.ensure_default_do_confirmation_config(actor)
        smtp_configs = email_admin_service.get_smtp_configs()
        settings = email_admin_service.list_workflow_email_settings(module_key)
        selected_setting = (
            email_admin_service.get_workflow_email_setting(module_key, status_key)
            if status_key else None
        )
    except Exception as exc:
        logger.exception("Email configuration load failed")
        flash(f"Email configuration storage is not ready: {exc}", "warning")
        smtp_configs = []
        settings = []
        selected_setting = None

    active_smtp = next((x for x in smtp_configs if x.get("is_active")), smtp_configs[0] if smtp_configs else None)
    return render_template(
        "admin_settings/email_config.html",
        module_key=module_key,
        workflow_modules=email_admin_service.WORKFLOW_EMAIL_MODULES,
        statuses=statuses,
        settings=settings,
        selected_setting=selected_setting,
        status_key=status_key,
        smtp_configs=smtp_configs,
        active_smtp=active_smtp,
        users=users,
    )


@admin_settings_bp.route("/email-config/smtp/save", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def email_config_smtp_save():
    actor = session.get("emp_id") or 0
    ok, errors, _ = email_admin_service.save_smtp_config(request.form, actor)
    if not ok:
        for err in errors:
            flash(err, "danger")
    else:
        flash("SMTP configuration saved.", "success")
    return redirect(url_for("admin.email_config", module="delivery_orders", status="CONFIRMED"))


@admin_settings_bp.route("/email-config/smtp/test", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def email_config_smtp_test():
    actor = session.get("emp_id") or 0
    config_id = request.form.get("config_id", type=int) or 0
    test_email = (request.form.get("test_email") or "").strip()
    ok, message = email_admin_service.test_smtp_config(config_id, test_email, actor)
    flash(message, "success" if ok else "danger")
    return redirect(url_for("admin.email_config"))


@admin_settings_bp.route("/email-config/workflow/save", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def email_config_workflow_save():
    actor = session.get("emp_id") or 0
    ok, errors, setting_id = email_admin_service.save_workflow_email_setting(request.form, actor)
    module_key = (request.form.get("module_key") or "delivery_orders").strip()
    status_key = (request.form.get("status_key") or "").strip().upper()
    if not ok:
        for err in errors:
            flash(err, "danger")
    else:
        flash("Workflow email settings saved.", "success")

    # Optional attachment upload along with save
    file_obj = request.files.get("attachment_file")
    if ok and setting_id and file_obj and file_obj.filename:
        is_editable = request.form.get("attachment_is_editable") == "1"
        att_ok, att_msg = email_admin_service.save_attachment(file_obj, int(setting_id), is_editable, actor)
        flash(att_msg, "success" if att_ok else "danger")

    return redirect(url_for("admin.email_config", module=module_key, status=status_key))


@admin_settings_bp.route("/email-config/workflow/attachment/<int:attachment_id>/delete", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def email_config_attachment_delete(attachment_id: int):
    actor = session.get("emp_id") or 0
    module_key = (request.form.get("module_key") or "delivery_orders").strip()
    status_key = (request.form.get("status_key") or "").strip().upper()
    ok, message = email_admin_service.delete_attachment(attachment_id, actor)
    flash(message, "success" if ok else "danger")
    return redirect(url_for("admin.email_config", module=module_key, status=status_key))


@admin_settings_bp.route("/email-config/workflow/preview", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def email_config_workflow_preview():
    subject_template = (request.form.get("subject_template") or "").strip()
    body_template = (request.form.get("body_template") or "").strip()
    sample_context = {
        "do_number": "AWTFZC/Apr/26/DO6062",
        "customer_name": "Sample Customer",
        "date": "2026-04-22",
        "status": (request.form.get("status_key") or "SUBMITTED").strip().upper(),
        "created_by": session.get("user_name") or "Creator",
        "approved_by": "Approver",
        "order_link": request.host_url.rstrip("/") + url_for("delivery_orders.order_list"),
        "reject_reason": "",
        "reject_remarks": "",
    }
    preview_subject = email_admin_service.render_template_text(subject_template, sample_context)
    preview_body = email_admin_service.render_template_text(body_template, sample_context)
    return jsonify({"subject": preview_subject, "body": preview_body})


@admin_settings_bp.route("/email-config/workflow/test-send", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def email_config_workflow_test_send():
    module_key = (request.form.get("module_key") or "delivery_orders").strip()
    status_key = (request.form.get("status_key") or "").strip().upper()
    order_id = request.form.get("order_id", type=int)

    if module_key != "delivery_orders":
        flash("Workflow test send currently supports Delivery Orders only.", "warning")
        return redirect(url_for("admin.email_config", module=module_key, status=status_key))

    if not status_key:
        flash("Please select a workflow status before sending a test email.", "danger")
        return redirect(url_for("admin.email_config", module=module_key))

    if not order_id:
        flash("Please provide a valid Delivery Order ID.", "danger")
        return redirect(url_for("admin.email_config", module=module_key, status=status_key))

    order = get_order_by_id(order_id)
    if not order:
        flash(f"Delivery Order with ID {order_id} was not found.", "danger")
        return redirect(url_for("admin.email_config", module=module_key, status=status_key))

    po_number = (order.get("PO_Number") or "").strip()
    if not po_number:
        flash("Selected Delivery Order has no PO number and cannot be used for email testing.", "danger")
        return redirect(url_for("admin.email_config", module=module_key, status=status_key))

    order["line_items"] = get_order_items(po_number)

    cc_emails = []
    creator_email = (order.get("creator_email") or "").strip()
    if creator_email:
        cc_emails.append(creator_email)
    actor_email = (session.get("email") or "").strip()
    if actor_email:
        cc_emails.append(actor_email)

    diagnostics: dict = {}
    ok = send_do_status_email(
        order=order,
        new_status=status_key,
        creator_first_name=order.get("creator_first"),
        extra_cc=cc_emails,
        run_async=False,
        diagnostics=diagnostics,
    )

    if ok:
        attachment_msg = "No attachment expected for this status."
        if diagnostics.get("attachment_expected"):
            if diagnostics.get("attachment_added"):
                attachment_msg = "PDF attachment generated and included."
            else:
                attachment_msg = "Attachment expected, but PDF could not be generated."

        source_msg = (
            "workflow config"
            if diagnostics.get("workflow_config_used")
            else "no workflow config"
        )

        flash(
            (
                f"Workflow test email sent for DO {po_number} ({status_key}). "
                f"Source={source_msg}. "
                f"TO={len(diagnostics.get('to') or [])}, "
                f"CC={len(diagnostics.get('cc') or [])}, "
                f"BCC={len(diagnostics.get('bcc') or [])}. "
                f"{attachment_msg}"
            ),
            "success",
        )
    else:
        flash(
            (
                f"Workflow test email failed for DO {po_number} ({status_key}). "
                f"Reason: {diagnostics.get('error') or 'Please check SMTP and logs.'}"
            ),
            "danger",
        )

    return redirect(url_for("admin.email_config", module=module_key, status=status_key))


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


# ═══════════════════════════════════════════════════════════════
#  ACCESS CONTROL — Auth Platform (Users / Roles / Matrix)
# ═══════════════════════════════════════════════════════════════

def _auth_app_id():
    """Return the application_id for Auth-App API calls."""
    return current_app.config.get('AUTH_APP_APPLICATION_ID', '')


@admin_settings_bp.route("/access-control")
@login_required
@role_required("admin", "it_admin")
def access_control():
    """Main Access Control page with Users / Roles / Permission Matrix tabs."""
    tab = request.args.get('tab', 'users')
    app_id = _auth_app_id()

    users_list = []
    users_meta = {}
    roles = []
    matrix_data = {}
    categories = {}
    all_perms = []

    if tab == 'users':
        page = request.args.get('page', 1, type=int)
        data, meta = auth_client.get_app_users(app_id, page=page, per_page=30)
        if data is not None:
            users_list = data
            users_meta = meta or {}
        else:
            flash("Could not load users from Auth Platform.", "warning")

    elif tab == 'roles':
        roles = auth_client.get_app_roles(app_id)

    elif tab == 'matrix':
        roles = auth_client.get_app_roles(app_id)
        all_perms = auth_client.get_all_permissions(application_id=app_id)
        # Fetch role permissions in parallel to avoid O(n) sequential calls
        from concurrent.futures import ThreadPoolExecutor
        def _fetch_rp(role):
            rp = auth_client.get_role_permissions(role['id'])
            return role['id'], [p['id'] for p in rp]
        with ThreadPoolExecutor(max_workers=min(len(roles), 8)) as pool:
            for rid, pids in pool.map(_fetch_rp, roles):
                matrix_data[rid] = pids
        for p in all_perms:
            cat = p.get('category', 'Other')
            categories.setdefault(cat, []).append(p)

    return render_template(
        "admin_settings/access_control.html",
        tab=tab,
        users=users_list,
        meta=users_meta,
        page=request.args.get('page', 1, type=int),
        roles=roles,
        matrix=matrix_data,
        categories=categories,
    )


@admin_settings_bp.route("/access-control/users/<user_id>/roles")
@login_required
@role_required("admin", "it_admin")
def ac_user_roles(user_id):
    """Show user role management page."""
    app_id = _auth_app_id()
    user_roles = auth_client.get_user_roles(user_id, application_id=app_id)
    all_roles = auth_client.get_app_roles(app_id)
    assigned_codes = {r['role_code'] for r in user_roles}
    user_info = _find_user_by_id(app_id, user_id)

    return render_template(
        "admin_settings/ac_user_roles.html",
        user_id=user_id,
        user_info=user_info,
        user_roles=user_roles,
        all_roles=all_roles,
        assigned_codes=assigned_codes,
    )


@admin_settings_bp.route("/access-control/users/<user_id>/roles", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def ac_update_user_roles(user_id):
    """Sync the selected role codes for a user via Auth-App."""
    app_id = _auth_app_id()
    role_codes = request.form.getlist('role_codes')
    result = auth_client.sync_user_roles(user_id, app_id, role_codes)
    if result.get('success'):
        flash('User roles updated.', 'success')
    else:
        flash(f"Failed to update roles: {result.get('message', 'Unknown error')}", 'danger')
    return redirect(url_for('admin.access_control', tab='users'))


@admin_settings_bp.route("/access-control/roles/create", methods=["GET", "POST"])
@login_required
@role_required("admin", "it_admin")
def ac_create_role():
    """Create a new role via Auth-App."""
    import re as re_mod
    if request.method == "POST":
        app_id = _auth_app_id()
        name = (request.form.get('role_name') or '').strip()
        code = (request.form.get('role_code') or '').strip().upper()
        description = (request.form.get('role_description') or '').strip()

        if not name or not code:
            flash('Role name and code are required.', 'danger')
            return redirect(url_for('admin.ac_create_role'))

        if not re_mod.match(r'^DO_[A-Z0-9_]{2,30}$', code):
            flash('Role code must start with DO_ followed by 2-30 uppercase letters/digits/underscores.', 'danger')
            return redirect(url_for('admin.ac_create_role'))

        result = auth_client.create_role(app_id, code, name, description)
        if result.get('success'):
            flash(f'Role "{name}" created successfully.', 'success')
        else:
            flash(f"Failed to create role: {result.get('message', 'Unknown error')}", 'danger')
        return redirect(url_for('admin.access_control', tab='roles'))

    return render_template("admin_settings/ac_create_role.html")


@admin_settings_bp.route("/access-control/roles/<role_id>/permissions")
@login_required
@role_required("admin", "it_admin")
def ac_role_permissions(role_id):
    """Show role permissions page with organized CRUD + Special layout."""
    app_id = _auth_app_id()
    role_perms = auth_client.get_role_permissions(role_id)
    all_perms = auth_client.get_all_permissions(application_id=app_id)
    assigned_ids = {p['id'] for p in role_perms}

    all_roles = auth_client.get_app_roles(app_id)
    role_name = next((r['name'] for r in all_roles if r['id'] == role_id), 'Role')

    # Organize permissions by category
    pages = _organize_perms_by_page(all_perms, assigned_ids)

    return render_template(
        "admin_settings/ac_role_permissions.html",
        role_id=role_id,
        role_name=role_name,
        pages=pages,
    )


@admin_settings_bp.route("/access-control/roles/<role_id>/permissions", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def ac_update_role_permissions(role_id):
    """Sync permissions for a role (full replace)."""
    app_id = _auth_app_id()
    permission_ids = request.form.getlist('permission_ids')
    result = auth_client.map_role_permissions(role_id, permission_ids, application_id=app_id)
    if result.get('success'):
        flash('Role permissions updated.', 'success')
    else:
        flash(f"Failed to update permissions: {result.get('message', 'Unknown error')}", 'danger')
    return redirect(url_for('admin.access_control', tab='roles'))


@admin_settings_bp.route("/access-control/refresh-session", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def ac_refresh_session():
    """Re-fetch current user's permissions from Auth-App and update session."""
    app_id = _auth_app_id()
    user_id = session.get('sso_user', {}).get('id')
    if not user_id:
        flash('No user in session.', 'danger')
        return redirect(url_for('admin.access_control'))
    fresh_perms = auth_client.refresh_session_permissions(user_id, app_id)
    if fresh_perms:
        session['sso_permissions'] = fresh_perms
        flash(f'Permissions refreshed ({len(fresh_perms)} permissions loaded).', 'success')
    else:
        flash('Failed to refresh permissions.', 'danger')
    return redirect(url_for('admin.access_control'))


# ═══════════════════════════════════════════════════════════════
#  DATABASE CONNECTION MANAGER
# ═══════════════════════════════════════════════════════════════

@admin_settings_bp.route("/database")
@login_required
@role_required("admin", "it_admin")
def database():
    from services.db_config_service import get_current_config, ALL_TABLES
    current = get_current_config()
    return render_template(
        "admin_settings/db_config.html",
        current=current,
        all_tables=ALL_TABLES,
    )


@admin_settings_bp.route("/database/test", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def database_test():
    from services.db_config_service import test_connection
    data = request.get_json(force=True) or {}
    cfg = {
        "server": data.get("server", "").strip(),
        "database": data.get("database", "").strip(),
        "user": data.get("user", "").strip(),
        "password": data.get("password", ""),
        "driver": data.get("driver", "").strip() or "{ODBC Driver 17 for SQL Server}",
    }
    if not cfg["server"] or not cfg["database"] or not cfg["user"]:
        return jsonify({"ok": False, "error": "Server, database and user are required."})
    result = test_connection(cfg)
    if not result.get("ok"):
        logger.warning(
            "Database test failed for server=%s db=%s user=%s: %s",
            cfg.get("server"), cfg.get("database"), cfg.get("user"), result.get("error", ""),
        )
        return jsonify({"ok": False, "error": "Unable to connect or prepare database with the provided settings."})
    return jsonify(result)


@admin_settings_bp.route("/database/migrate-and-connect", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def database_migrate_and_connect():
    from services.db_config_service import ensure_database_exists, migrate_tables, save_and_switch
    data = request.get_json(force=True) or {}
    cfg = {
        "server": data.get("server", "").strip(),
        "database": data.get("database", "").strip(),
        "user": data.get("user", "").strip(),
        "password": data.get("password", ""),
        "driver": data.get("driver", "").strip() or "{ODBC Driver 17 for SQL Server}",
    }
    tables = data.get("tables") or None
    include_data = bool(data.get("include_data", True))
    copy_mode = (data.get("copy_mode") or "masters_only").strip().lower()

    ensure_result = ensure_database_exists(cfg)
    if not ensure_result.get("ok"):
        logger.warning(
            "Database prepare failed (migrate-and-connect) for server=%s db=%s user=%s: %s",
            cfg.get("server"), cfg.get("database"), cfg.get("user"), ensure_result.get("error", ""),
        )
        return jsonify({"ok": False, "error": "Unable to create or access target database with the provided settings."})

    results = migrate_tables(cfg, tables=tables, include_data=include_data, copy_mode=copy_mode)
    save_and_switch(cfg)
    logger.info("DB config switched to server=%s db=%s by user=%s",
                cfg["server"], cfg["database"], session.get("email"))
    return jsonify({"ok": True, "results": results, "db_created": bool(ensure_result.get("created"))})


@admin_settings_bp.route("/database/connect-only", methods=["POST"])
@login_required
@role_required("admin", "it_admin")
def database_connect_only():
    from services.db_config_service import ensure_database_exists, save_and_switch
    data = request.get_json(force=True) or {}
    cfg = {
        "server": data.get("server", "").strip(),
        "database": data.get("database", "").strip(),
        "user": data.get("user", "").strip(),
        "password": data.get("password", ""),
        "driver": data.get("driver", "").strip() or "{ODBC Driver 17 for SQL Server}",
    }
    if not cfg["server"] or not cfg["database"] or not cfg["user"]:
        return jsonify({"ok": False, "error": "Server, database and user are required."})

    ensure_result = ensure_database_exists(cfg)
    if not ensure_result.get("ok"):
        logger.warning(
            "Database prepare failed (connect-only) for server=%s db=%s user=%s: %s",
            cfg.get("server"), cfg.get("database"), cfg.get("user"), ensure_result.get("error", ""),
        )
        return jsonify({"ok": False, "error": "Unable to create or access target database with the provided settings."})

    save_and_switch(cfg)
    logger.info("DB config switched (no migration) to server=%s db=%s by user=%s",
                cfg["server"], cfg["database"], session.get("email"))
    return jsonify({"ok": True, "db_created": bool(ensure_result.get("created"))})


# ── Helpers ───────────────────────────────────────────────────

def _find_user_by_id(app_id, user_id):
    """Look up a single user's info from the Auth Platform."""
    return svc.find_auth_user(app_id, user_id) or {}


# ── Permission grouping helper ───────────────────────────────

_CRUD_OPS = {'VIEW', 'CREATE', 'EDIT', 'UPDATE', 'DELETE'}

_SPECIAL_OP_LABELS = {
    'APPROVE': 'Approve', 'EXPORT': 'Export', 'DOWNLOAD': 'Download',
    'GENERATE': 'Generate', 'SUBMIT': 'Submit', 'RUN': 'Run',
    'ENTER': 'Enter', 'CALCULATE': 'Calculate', 'PANEL': 'Panel',
    'SETTINGS': 'Settings', 'USERS': 'Users', 'MASTERS': 'Masters',
}


def _organize_perms_by_page(all_perms, assigned_ids):
    """Organize permissions by category, splitting CRUD and special ops."""
    pages = {}
    for p in all_perms:
        cat = p.get('category', 'OTHER')
        parts = p.get('code', '').split('.', 1)
        op = parts[1] if len(parts) > 1 else parts[0]

        if cat not in pages:
            pages[cat] = {
                'category': cat,
                'name': cat.replace('_', ' ').title(),
                'crud': [],
                'special': [],
            }

        perm_entry = {
            'id': p['id'],
            'code': p.get('code', ''),
            'name': p.get('name', ''),
            'op': op,
            'display_name': _SPECIAL_OP_LABELS.get(op, op.replace('_', ' ').title()),
            'assigned': p['id'] in assigned_ids,
        }
        if op in _CRUD_OPS:
            pages[cat]['crud'].append(perm_entry)
        else:
            pages[cat]['special'].append(perm_entry)

    return sorted(pages.values(), key=lambda x: x['name'])
