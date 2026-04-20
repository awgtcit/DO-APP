"""
Auth controller — login, logout, ISP acceptance.
Supports SSO via Auth-App launch tokens AND direct LDAP/DB login.
"""

import logging

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from services.auth_service import login, check_isp, accept_isp
from repos.user_repo import get_user_roles

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET"], endpoint="login")
def login_page():
    if session.get("email"):
        return redirect(url_for("dashboard.home"))
    return render_template("auth/login.html")


@auth_bp.route("/login", methods=["POST"], endpoint="login_post")
def login_post():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    client_ip = request.remote_addr or ""

    # Try Auth-App centralized login first (if configured)
    from config import Config
    if Config.AUTH_API_KEY and Config.AUTH_APP_CODE:
        try:
            from sdk.auth_client import app_login, validate_token
            app_result = app_login(username, password, Config.AUTH_APP_CODE)
            launch_token = app_result.get('launch_token')
            if launch_token:
                # Validate the token to get user info, roles, permissions
                token_data = validate_token(launch_token)
                if token_data:
                    from sdk.session_middleware import _bridge_sso_to_legacy, _populate_g
                    sso_roles = [r['code'] for r in token_data.get('roles', [])]
                    session['sso_user'] = token_data['user']
                    session['sso_roles'] = sso_roles
                    session['sso_permissions'] = token_data.get('permissions', [])
                    session['sso_token'] = launch_token
                    session['sso_authenticated'] = True
                    session.permanent = True

                    # Bridge to DO-APP legacy session
                    _bridge_sso_to_legacy(token_data, sso_roles)
                    _populate_g(token_data['user'], sso_roles,
                                token_data.get('permissions', []))

                    logger.info("Auth-App login: %s", username)

                    # ISP gate
                    if not check_isp(session.get("email", username)):
                        return redirect(url_for("auth.isp_accept"))

                    flash(f"Welcome back, {session.get('user_name', '')}!", "success")
                    return redirect(url_for("delivery_orders.dashboard"))
        except Exception as exc:
            logger.warning("Auth-App login failed, falling back to LDAP/DB: %s", exc)

    # Fallback: local LDAP/DB authentication
    result = login(username, password, client_ip)

    if not result.success:
        for err in result.errors:
            flash(err, "danger")
        return render_template("auth/login.html", username=username)

    # Populate session
    user = result.user
    session.permanent = True
    session["email"] = user["email"]
    session["emp_id"] = user["emp_id"]
    session["user_name"] = f"{user['first_name']} {user['last_name']}".strip()
    session["department_id"] = user.get("department_id")
    session["group_id"] = user.get("group_id")
    session["roles"] = get_user_roles(user["emp_id"], user.get("group_id"))

    # ISP gate
    if not check_isp(user["email"]):
        return redirect(url_for("auth.isp_accept"))

    flash(f"Welcome back, {session['user_name']}!", "success")
    return redirect(url_for("delivery_orders.dashboard"))


@auth_bp.route("/isp", methods=["GET"])
def isp_accept():
    if not session.get("email"):
        return redirect(url_for("auth.login"))
    return render_template("auth/isp_accept.html")


@auth_bp.route("/isp", methods=["POST"], endpoint="isp_accept_post")
def isp_accept_post():
    email = session.get("email")
    emp_id = session.get("emp_id", 0)
    if not email:
        return redirect(url_for("auth.login"))

    errors = accept_isp(email, emp_id, request.remote_addr or "")
    if errors:
        for err in errors:
            flash(err, "danger")
        return render_template("auth/isp_accept.html")

    flash("Policy accepted. Welcome!", "success")
    return redirect(url_for("delivery_orders.dashboard"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
