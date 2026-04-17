"""
Auth controller — login, logout, ISP acceptance.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from services.auth_service import login, check_isp, accept_isp
from repos.user_repo import get_user_roles

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
